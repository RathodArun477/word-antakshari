"""
Powerup activation: skip, double-score activation, and the steal challenge
flow (offer -> accept/reject -> result). The actual challenge minigames
(fastest_word, unscramble, etc.) live in challenge_handlers.py — this file
handles the offer/response/outcome plumbing, not the minigames themselves.
"""
from flask import request
from flask_socketio import emit

from app import socketio
import room_registry
from sockets import registry
from game import powerups
from game.state import generate_random_letter

@socketio.on("use_skip")
def handle_use_skip(data=None):
    entry = registry.get_player_for_sid(request.sid)
    if entry is None:
        return
    if not isinstance(data, dict):
        return

    room_code, player_id = entry
    submitted_turn_id = data.get("turn_id")

    with room_registry.room_session(room_code) as room:
        if room is None:
            return

        player = room.get_player(player_id)
        if player is None:
            return

        if not isinstance(submitted_turn_id, str) or not submitted_turn_id:
            socketio.emit(
                "error",
                {"code": "INVALID_PHASE", "message": "invalid_turn_id"},
                room=request.sid,
            )
            return

        if not room.is_active_turn(submitted_turn_id):
            socketio.emit(
                "error",
                {"code": "INVALID_PHASE", "message": "stale_or_invalid_turn"},
                room=request.sid,
            )
            return

        if not room.is_current_turn(player.player_id):
            socketio.emit(
                "error",
                {"code": "OUT_OF_TURN", "message": "Not your turn"},
                room=request.sid,
            )
            return

        result = powerups.use_skip(player)
        if not result["success"]:
            socketio.emit(
                "error",
                {"code": "NOT_AUTHORIZED", "message": result["reason"]},
                room=request.sid,
            )
            return

        if not room.resolve_turn(submitted_turn_id):
            socketio.emit(
                "error",
                {"code": "INVALID_PHASE", "message": "turn_already_resolved"},
                room=request.sid,
            )
            return

        room.required_letter = generate_random_letter()
        room.previous_word = None
        room.previous_turn_player_id = None

        socketio.emit(
            "skip_used",
            {
                "player_id": player.player_id,
                "turn_id": submitted_turn_id,
            },
            room=room.room_code,
        )

        from sockets.turn_handlers import _finish_turn
        _finish_turn(room)

@socketio.on("use_double_score")
def handle_use_double_score(data=None):
    entry = registry.get_player_for_sid(request.sid)
    if entry is None:
        return
    room_code, player_id = entry

    with room_registry.room_session(room_code) as room:
        if room is None:
            return
        player = room.get_player(player_id)
        if player is None:
            return

        result = powerups.use_double_score(player)
        if not result["success"]:
            socketio.emit("error", {"code": "NOT_AUTHORIZED", "message": result["reason"]}, to=request.sid)
            return

        socketio.emit("double_score_activated", {
            "player_id": player.player_id,
            "new_total_score": player.score,
        }, room=room.room_code, namespace="/")

@socketio.on("use_steal")
def handle_use_steal(data):
    entry = registry.get_player_for_sid(request.sid)
    if entry is None:
        return
    room_code, player_id = entry

    with room_registry.room_session(room_code) as room:
        if room is None:
            return
        challenger = room.get_player(player_id)
        if challenger is None:
            return

        target = room.get_player(data["target_player_id"])
        if target is None:
            socketio.emit("error", {"code": "NOT_AUTHORIZED", "message": "invalid_target"}, room=request.sid)
            return

        result = powerups.initiate_steal(challenger, target)
        if not result["success"]:
            socketio.emit("error", {"code": "NOT_AUTHORIZED", "message": result["reason"]}, room=request.sid)
            return

        room_registry.set_val(f"steal_offer:{target.player_id}", challenger.player_id, ex=300)

        target_sid = registry.get_sid_for_player(target.player_id)
        if target_sid:
            socketio.emit("steal_challenge_offer", {
                "challenger_id": challenger.player_id,
                "available_challenges": [
                    "fastest_word", "unscramble", "longest_word_sprint",
                    "reaction_race", "math_flash",
                ],
            }, room=target_sid)


@socketio.on("steal_challenge_response")
def handle_steal_challenge_response(data):
    entry = registry.get_player_for_sid(request.sid)
    if entry is None:
        return
    room_code, player_id = entry

    with room_registry.room_session(room_code) as room:
        if room is None:
            return
        target = room.get_player(player_id)
        if target is None:
            return

        challenger_key = f"steal_offer:{target.player_id}"
        challenger_id = room_registry.get_val(challenger_key)
        if challenger_id is not None:
            room_registry.delete_key(challenger_key)
        
        if challenger_id is None:
            socketio.emit("error", {"code": "INVALID_PHASE", "message": "no_pending_steal_offer"}, room=request.sid)
            return

        if not data["accept"]:
            result = powerups.reject_steal(target)
            socketio.emit("steal_rejected", {
                "challenger_id": challenger_id,
                "rejecter_id": target.player_id,
                "penalty_applied": result["penalty_applied"],
                "points_lost": result["points_lost"],
            }, room=room.room_code)
            socketio.emit("player_state_update", target.to_private_dict(), to=request.sid)
            socketio.emit("room_state_update", room.to_public_snapshot(), room=room.room_code)
            return

        from sockets.challenge_handlers import start_challenge
        start_challenge(room.room_code, challenger_id, target.player_id, data["challenge_type_if_accepted"])