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
    room.turn_resolved = False
    room.guess_submissions.clear()
    current = room.get_current_player()
    room.current_turn_started_at = time.time()

    socketio.emit("turn_start", {
        "player_id": current.player_id,
        "server_timestamp": int(room.current_turn_started_at * 1000),
        "duration_seconds": room.turn_timer_seconds,
        "round_number": room.current_round,
        "required_letter":room.required_letter,
    }, room=room.room_code,namespace="/")

    active = room.active_players
    if len(active) >= 3 and room.previous_word is not None:
        options = build_guess_options(room.previous_word)
        room.current_guess_options = options
        eligible = [
            p for p in active
            if p.player_id != current.player_id
            and p.player_id != room.previous_turn_player_id
        ]
        expires_at = int((room.current_turn_started_at + room.turn_timer_seconds) * 1000)
        for player in eligible:
            sid = registry.get_sid_for_player(player.player_id)
            if sid:
                socketio.emit("guess_options", {
                    "options": options,
                    "expires_at": expires_at,
                }, room=sid)

    socketio.start_background_task(
        _turn_timeout_watch, room.room_code, current.player_id, room.turn_timer_seconds
    )


def _turn_timeout_watch(room_code: str, expected_player_id: str, duration: float) -> None:
    socketio.sleep(duration)
    try:
        with room_registry.room_session(room_code) as room:
            if room is None or room.turn_resolved:
                return

            current = room.get_current_player()
            if current is None or current.player_id != expected_player_id:
                return

            room.turn_resolved = True
            room.handle_turn_timeout(expected_player_id)
            room.previous_word = None
            room.previous_turn_player_id = None

            player = room.get_player(expected_player_id)
            if player:
                socketio.emit("life_lost", {
                    "player_id":expected_player_id,
                    "new_lives":player.lives,
                    "reason":"timeout",
                },room=room_code,namespace="/")
                
            if player and player.is_eliminated:
                socketio.emit("player_eliminated", {
                    "player_id": expected_player_id,
                    "reason": "timeout",
                }, room=room_code)

            _finish_turn(room)
    except Exception as e:
        print(f"Error in turn timeout watch: {e}")


@socketio.on("word_submit")
@rate_limited(max_calls=5, per_seconds=5)
def handle_word_submit(data):
    entry = registry.get_player_for_sid(request.sid)
    if entry is None:
        return {"accepted": False, "reason_if_rejected": "not_authorized"}

    room_code, player_id = entry
    with room_registry.room_session(room_code) as room:
        if room is None:
            return {"accepted": False, "reason_if_rejected": "out_of_turn"}

        if room.turn_resolved:
            return {"accepted": False, "reason_if_rejected": "invalid_phase"}

        time_remaining = room.turn_timer_seconds - (time.time() - room.current_turn_started_at)
        try:
            result = room.submit_word(player_id, data["word"], time_remaining, validate_word)
        except Exception as e:
            print(f"Error submitting word: {e}")
            return {"accepted": False, "reason_if_rejected": "not_a_word"}

        if not result["accepted"]:
            if result.get("reason_if_rejected") == "already_used_penalty":
                room.turn_resolved = True
                room.previous_word = None
                room.previous_turn_player_id = None
                
                socketio.emit("life_lost", {
                    "player_id": player_id,
                    "new_lives": result["new_lives"],
                    "reason": "duplicate_word_penalty",
                }, room=room_code)
                
                if result["is_eliminated"]:
                    socketio.emit("player_eliminated", {
                        "player_id": player_id,
                        "reason": "duplicate_word_penalty",
                    }, room=room_code)
                
                # Emit the updated private player state snapshot
                player = room.get_player(player_id)
                if player:
                    socketio.emit("player_state_update", player.to_private_dict(), room=request.sid)

                _finish_turn(room)
            return result

        room.turn_resolved = True
        player = room.get_player(player_id)

        room.previous_word = data["word"].strip().lower()
        room.previous_turn_player_id = player_id

        socketio.emit("turn_resolved", {
            "player_id": player_id,
            "word_length": result["word_length"],
            "score_gained": result["score_gained"],
            "new_total_score": player.score,
            "new_lives": player.lives,
        }, room=room_code)

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
