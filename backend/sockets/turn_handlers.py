"""
Turn flow: starting turns, word submission, timeout handling, and the
transition into the next turn (including win-condition checks).
"""
import time
from flask import request
from flask_socketio import emit

from app import socketio
import room_registry
from sockets import registry
from game import rules, powerups
from game.decoys import build_guess_options
from game.validation import validate_word
from sockets.rate_limit import rate_limited

def start_turn(room) -> None:
    current = room.get_current_player()
    if current is None:
        raise RuntimeError("Cannot start a turn without a current player")

    started_at = time.time()
    deadline_at = started_at + room.turn_timer_seconds
    turn_id = room.new_turn_id()
    room.activate_turn(turn_id, started_at, deadline_at)
    room.guess_submissions.clear()

    socketio.emit(
        "turn_start",
        {
            "turn_id": turn_id,
            "player_id": current.player_id,
            "started_at": int(started_at * 1000),
            "deadline_at": int(deadline_at * 1000),
            "server_timestamp": int(started_at * 1000),
            "duration_seconds": room.turn_timer_seconds,
            "round_number": room.current_round,
            "required_letter": room.required_letter,
        },
        room=room.room_code,
        namespace="/",
    )
    active = room.active_players
    if len(active) >= 3 and room.previous_word is not None:
        options = build_guess_options(room.previous_word)
        room.current_guess_options = options

        for player in active:
            if player.player_id == current.player_id:
                continue
            if player.player_id == room.previous_turn_player_id:
                continue

            sid = registry.get_sid_for_player(player.player_id)
            if sid:
                socketio.emit(
                    "guess_options",
                    {
                        "turn_id": turn_id,
                        "options": options,
                        "expires_at": int(deadline_at * 1000),
                    },
                    room=sid,
                )
    socketio.start_background_task(
        _turn_timeout_watch,
        room.room_code,
        turn_id,
        deadline_at,
        current.player_id,
    )

def _turn_timeout_watch(room_code: str,expected_turn_id: str,deadline_at: float,expected_player_id: str) -> None:
    remaining = deadline_at - time.time()
    if remaining > 0:
        socketio.sleep(remaining)

    try:
        with room_registry.room_session(room_code) as room:
            if room is None:
                return

            if not room.is_active_turn(expected_turn_id):
                return

            if room.current_turn_deadline_at is None:
                return

            if time.time() < room.current_turn_deadline_at:
                return

            if not room.resolve_turn(expected_turn_id):
                return

            current = room.get_current_player()
            if current is None or current.player_id != expected_player_id:
                return

            room.handle_turn_timeout(expected_player_id)
            room.previous_word = None
            room.previous_turn_player_id = None

            player = room.get_player(expected_player_id)
            if player:
                socketio.emit(
                    "life_lost",
                    {
                        "player_id": expected_player_id,
                        "new_lives": player.lives,
                        "reason": "timeout",
                    },
                    room=room_code,
                    namespace="/",
                )

            if player and player.is_eliminated:
                socketio.emit(
                    "player_eliminated",
                    {
                        "player_id": expected_player_id,
                        "reason": "timeout",
                    },
                    room=room_code,
                )

            _finish_turn(room)
    except Exception as e:
        print(f"Error in turn timeout watch: {e}")

@socketio.on("word_submit")
@rate_limited(max_calls=5, per_seconds=5)
def handle_word_submit(data):
    entry = registry.get_player_for_sid(request.sid)
    if entry is None:
        return {"accepted": False, "reason_if_rejected": "not_authorized"}

    if not isinstance(data, dict):
        return {"accepted": False, "reason_if_rejected": "invalid_phase"}

    room_code, player_id = entry
    submitted_turn_id = data.get("turn_id")
    word = data.get("word")

    if not isinstance(submitted_turn_id, str) or not submitted_turn_id:
        return {"accepted": False, "reason_if_rejected": "invalid_phase"}

    if not isinstance(word, str):
        return {"accepted": False, "reason_if_rejected": "not_a_word"}

    with room_registry.room_session(room_code) as room:
        if room is None:
            return {"accepted": False, "reason_if_rejected": "out_of_turn"}

        if not room.is_active_turn(submitted_turn_id):
            return {"accepted": False, "reason_if_rejected": "invalid_phase"}
        if room.get_current_player() is None:
            return {"accepted": False, "reason_if_rejected": "out_of_turn"}

        if room.get_current_player().player_id != player_id:
            return {"accepted": False, "reason_if_rejected": "out_of_turn"}

        if room.current_turn_deadline_at is None:
            return {"accepted": False, "reason_if_rejected": "invalid_phase"}

        if time.time() >= room.current_turn_deadline_at:
            return {"accepted": False, "reason_if_rejected": "turn_expired"}

        try:
            result = room.submit_word(
                player_id,
                word,
                room.current_turn_deadline_at,
                validate_word,
            )
        except Exception as e:
            print(f"Error submitting word: {e}")
            return {"accepted": False, "reason_if_rejected": "not_a_word"}

        if not result["accepted"]:
            if result.get("reason_if_rejected") == "already_used_penalty":
                if not room.resolve_turn(submitted_turn_id):
                    return {"accepted": False, "reason_if_rejected": "invalid_phase"}

                room.previous_word = None
                room.previous_turn_player_id = None

                socketio.emit(
                    "life_lost",
                    {
                        "player_id": player_id,
                        "new_lives": result["new_lives"],
                        "reason": "duplicate_word_penalty",
                    },
                    room=room_code,
                )

                if result["is_eliminated"]:
                    socketio.emit(
                        "player_eliminated",
                        {
                            "player_id": player_id,
                            "reason": "duplicate_word_penalty",
                        },
                        room=room_code,
                    )

                player = room.get_player(player_id)
                if player:
                    socketio.emit(
                        "player_state_update",
                        player.to_private_dict(),
                        room=request.sid,
                    )

                _finish_turn(room)

            return result

        if not room.resolve_turn(submitted_turn_id):
            return {"accepted": False, "reason_if_rejected": "invalid_phase"}

        player = room.get_player(player_id)
        if player is None:
            return {"accepted": False, "reason_if_rejected": "not_authorized"}

        room.previous_word = word.strip().lower()
        room.previous_turn_player_id = player_id

        socketio.emit(
            "turn_resolved",
            {
                "turn_id": submitted_turn_id,
                "player_id": player_id,
                "word_length": result["word_length"],
                "score_gained": result["score_gained"],
                "new_total_score": player.score,
                "new_lives": player.lives,
            },
            room=room_code,
        )

        _finish_turn(room)
        return result

def _finish_turn(room) -> None:
    # First check gameplay-ending conditions that take precedence,
    # such as only one active player remaining.
    end_result = rules.check_win_condition(room)

    if end_result is not None:
        from game.enums import RoomState

        room.state = RoomState.FINISHED

        socketio.emit(
            "game_ended",
            end_result,
            room=room.room_code,
        )
        return

    # In rounds mode, stop immediately after the final eligible turn
    # of the configured final round. Do not advance into another round.
    end_result = rules.check_round_limit_condition(room)

    if end_result is not None:
        from game.enums import RoomState

        room.state = RoomState.FINISHED

        socketio.emit(
            "game_ended",
            end_result,
            room=room.room_code,
        )
        return

    room.advance_turn()
    start_turn(room)
