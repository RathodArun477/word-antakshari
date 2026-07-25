"""
Steal challenge minigame flow: start -> go signal -> submit -> resolve.
reaction_race is built; other challenge types plug into the same
start_challenge/resolve_challenge pattern later.
"""
import time

from flask import request
from flask_socketio import emit

from app import socketio
import room_registry
from sockets import registry
from game import challenges, powerups
from sockets.rate_limit import rate_limited

def _get_challenge(room_code: str) -> challenges.ActiveChallenge | None:
    data = room_registry.get_json(f"active_challenge:{room_code}")
    if data is None:
        return None
    return challenges.ActiveChallenge.from_dict(data)


def _save_challenge(challenge: challenges.ActiveChallenge) -> None:
    room_registry.set_json(f"active_challenge:{challenge.room_code}", challenge.to_dict(), ex=300)


def _pop_challenge(room_code: str) -> challenges.ActiveChallenge | None:
    key = f"active_challenge:{room_code}"
    data = room_registry.get_json(key)
    if data is None:
        return None
    room_registry.delete_key(key)
    return challenges.ActiveChallenge.from_dict(data)


def start_challenge(room_code: str, challenger_id: str, target_id: str, challenge_type: str) -> None:
    challenge = challenges.ActiveChallenge(challenge_type, challenger_id, target_id, room_code)

    if challenge_type == "reaction_race":
        prompt_data, delay = challenges.generate_reaction_race()
        challenge.prompt_data = prompt_data
        _save_challenge(challenge)

        for pid in (challenger_id, target_id):
            sid = registry.get_sid_for_player(pid)
            if sid:
                socketio.emit("challenge_start", {
                    "challenge_type": challenge_type,
                    "prompt_data": prompt_data,
                }, room=sid)

        socketio.start_background_task(_fire_go_signal, room_code, delay)

    elif challenge_type == "unscramble":
        prompt_data, answer = challenges.generate_unscramble()
        challenge.prompt_data = prompt_data
        challenge.answer = answer
        challenge.go_at = time.time()   # no reaction delay -- starts immediately
        _save_challenge(challenge)

        for pid in (challenger_id, target_id):
            sid = registry.get_sid_for_player(pid)
            if sid:
                socketio.emit("challenge_start", {
                    "challenge_type": challenge_type,
                    "prompt_data": prompt_data,
                }, room=sid)

        socketio.start_background_task(_resolve_after_timeout, room_code, 15.0)

    elif challenge_type == "fastest_word":
        prompt_data, _letter = challenges.generate_fastest_word()
        challenge.prompt_data = prompt_data
        challenge.go_at = time.time()
        _save_challenge(challenge)

        for pid in (challenger_id, target_id):
            sid = registry.get_sid_for_player(pid)
            if sid:
                socketio.emit("challenge_start",{
                    "challenge_type" : challenge_type,
                    "prompt_data": prompt_data
                },room=sid)
        socketio.start_background_task(_resolve_after_timeout,room_code,15.0)

    elif challenge_type == "math_flash":
        prompt_data,answer = challenges.generate_math_flash()
        challenge.prompt_data = prompt_data
        challenge.answer = answer
        challenge.go_at = time.time()
        _save_challenge(challenge)

        for pid in (challenger_id,target_id):
            sid = registry.get_sid_for_player(pid)
            if sid:
                socketio.emit("challenge_start",{
                    "challenge_type":challenge_type,
                    "prompt_data":prompt_data,
                },room=sid)
        socketio.start_background_task(_resolve_after_timeout,room_code,15.0)

    else:
        # fastest_word / math_flash come next -- fail safe rather than
        # leave both clients hanging on an unbuilt challenge.
        sid = registry.get_sid_for_player(challenger_id)
        if sid:
            socketio.emit("error", {"code": "NOT_AUTHORIZED", "message": "challenge_type_not_yet_supported"}, room=sid)


def _fire_go_signal(room_code: str, delay: float) -> None:
    socketio.sleep(delay)

    challenge = _get_challenge(room_code)
    if challenge is None or challenge.resolved:
        return

    challenge.go_at = time.time()
    _save_challenge(challenge)
    for pid in (challenge.challenger_id, challenge.target_id):
        sid = registry.get_sid_for_player(pid)
        if sid:
            socketio.emit("challenge_go", {}, room=sid)

    socketio.start_background_task(_resolve_after_timeout, room_code, 3.0)


def _resolve_after_timeout(room_code: str, wait_seconds: float) -> None:
    socketio.sleep(wait_seconds)
    _resolve_challenge(room_code)


@socketio.on("challenge_submit")
def handle_challenge_submit(data=None):
    entry = registry.get_player_for_sid(request.sid)
    if entry is None:
        return
    room_code, player_id = entry

    challenge = _get_challenge(room_code)
    if challenge is None or challenge.resolved:
        return
    if player_id not in (challenge.challenger_id, challenge.target_id):
        return

    value = (data or {}).get("value")
    received_at = time.time()

    if challenge.challenge_type == "reaction_race":
        is_win = challenges.check_reaction_race_win(challenge, received_at)
    elif challenge.challenge_type == "unscramble":
        is_win = challenges.check_unscramble_win(challenge, value)
    elif challenge.challenge_type == "fastest_word":
        is_win = challenges.check_fastest_word_win(challenge, value)
    elif challenge.challenge_type == "math_flash":
        is_win = challenges.check_math_flash_win(challenge, value)
    else:
        is_win = False

    if is_win:
        _resolve_challenge(room_code, winner_id=player_id)
    # Wrong/invalid submission -> ignored entirely. Player (or the other
    # player) can keep trying until someone gets it right, or the timeout
    # fires and the target wins by default.


def _resolve_challenge(room_code: str, winner_id: str | None = None) -> None:
    challenge = _pop_challenge(room_code)
    if challenge is None or challenge.resolved:
        return
    challenge.resolved = True

    room = room_registry.get_room(room_code)
    if room is None:
        return

    # No winner passed in means this was triggered by the timeout with
    # nobody having answered correctly -- target wins by default.
    if winner_id is None:
        winner_id = challenge.target_id

    with room_registry.room_session(room_code) as room:
        challenger = room.get_player(challenge.challenger_id)
        target = room.get_player(challenge.target_id)
        challenger_won = (winner_id == challenge.challenger_id)

        result = powerups.resolve_steal_challenge(challenger, target, challenger_won)
        socketio.emit("steal_challenge_result", result, room=room_code, namespace="/")
        
        if result["life_transferred"]:
            loser = target if challenger_won else challenger
            socketio.emit("life_lost", {
                "player_id": loser.player_id,
                "new_lives": loser.lives,
                "reason": "steal_lost",
            }, room=room_code, namespace="/")

            if loser.is_eliminated:
                socketio.emit("player_eliminated", {
                    "player_id": loser.player_id,
                    "reason": "steal_lost",
                }, room=room_code)

                from game import rules
                end_result = rules.check_win_condition(room)
                if end_result is not None:
                    socketio.emit("game_ended", end_result, room=room_code)
                    room_registry.remove_room(room_code)