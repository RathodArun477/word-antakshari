"""
Guessing phase: receiving a player's guess and resolving it.
Correctness is checked here (comparing against the room's stored
previous_word), then rules.process_guess handles streak/score updates.
"""
from flask import request
from flask_socketio import emit

import room_registry
from sockets import registry
from game import rules
from app import socketio
from sockets.rate_limit import rate_limited


@socketio.on("guess_submit")
@rate_limited(max_calls=5,per_seconds=5)
def handle_guess_submit(data):
    entry = registry.get_player_for_sid(request.sid)
    if entry is None:
        return

    room_code, player_id = entry
    with room_registry.room_session(room_code) as room:
        if room is None:
            socketio.emit("error", {"code": "ROOM_NOT_FOUND", "message": "Room not found"},to=request.sid)
            return

        player = room.get_player(player_id)
        current = room.get_current_player()

        # Validate eligibility: not the current turn player, not the previous
        # turn's player, not eliminated, and the turn must not already be resolved.
        if player is None or player.is_eliminated:
            socketio.emit("error", {"code": "NOT_AUTHORIZED", "message": "Not an active player"}, room=request.sid)
            return
        if current and player_id == current.player_id:
            socketio.emit("error", {"code": "OUT_OF_TURN", "message": "Current turn player cannot guess"}, room=request.sid)
            return
        if player_id == room.previous_turn_player_id:
            socketio.emit("error", {"code": "OUT_OF_TURN", "message": "Previous turn player cannot guess their own word"}, room=request.sid)
            return
        if room.turn_resolved:
            socketio.emit("error", {"code": "INVALID_PHASE", "message": "Guessing window has closed"}, room=request.sid)
            return
        if room.previous_word is None:
            socketio.emit("error", {"code": "INVALID_PHASE", "message": "No word to guess this turn"}, room=request.sid)
            return

        if player_id in room.guess_submissions:
            socketio.emit(
                "error",
                {
                    "code":"ALREADY_GUESSED",
                    "message":"You have already guessed this turn",
                },
                to=request.sid,
            )
            return

        # We need the exact options list the player was shown, to map their
        # index back to a word. Since options were generated fresh per-turn and
        # not stored on the room, we regenerate deterministically isn't safe
        # (randomized) -- so the room needs to cache the options it sent.
        # See note below the code.
        guess_index = data.get("guess_index")
        if isinstance(guess_index,bool) or not isinstance(guess_index,int):
            socketio.emit(
                "error",
                {
                    "code":"INVALID_GUESS_INDEX",
                    "message":"Guess index must be an integer",
                },
                to=request.sid,
            )
            return
        if not 0 <= guess_index < len(room.current_guess_options):
            socketio.emit(
                "error",
                {
                    "code":"INVALID_GUESS_INDEX",
                    "message":"Guess index is outside the available options",
                },
                to=request.sid,
            )
            return
        room.guess_submissions.add(player_id)

        guessed_word = room.current_guess_options[guess_index]
        correct = (guessed_word == room.previous_word)

        result = rules.process_guess(player, correct)

        # Emit the updated private player state snapshot
        socketio.emit("player_state_update", player.to_private_dict(), room=request.sid)
        socketio.emit("room_state_update", room.to_public_snapshot(), room=room.room_code)

        socketio.emit("guess_result", {
            "correct": correct,
            "streak_count": result["streak_count"],
            "points_delta": result["points_delta"],
        }, room=request.sid)