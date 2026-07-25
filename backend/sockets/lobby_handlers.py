"""
Host-triggered game start. Separate from connection_handlers since this is
about transitioning a room from WAITING to IN_PROGRESS, not joining/leaving.
"""
from flask import request
from flask_socketio import emit

from app import socketio
import room_registry
from sockets import registry


@socketio.on("start_game")
def handle_start_game(data=None):
    entry = registry.get_player_for_sid(request.sid)
    if entry is None:
        return
    room_code, player_id = entry
    with room_registry.room_session(room_code) as room:
        if room is None:
            socketio.emit("error", {"code": "ROOM_NOT_FOUND", "message": "Room not found"}, room=request.sid)
            return

        if player_id != room.host_player_id:
            socketio.emit("error", {"code": "NOT_AUTHORIZED", "message": "Only the host can start the game"}, room=request.sid)
            return

        if not room.can_start():
            socketio.emit("error", {"code": "INVALID_ROOM_CONFIG", "message": "Not enough players or already started"}, room=request.sid)
            return

        room.start_game()

        socketio.emit("game_started", {
            "turn_order": room.turn_order,
            "round_limit": room.round_limit,
            "first_player_id": room.get_current_player().player_id,
        }, room=room.room_code)

        from sockets.turn_handlers import start_turn
        start_turn(room)


@socketio.on("update_room_settings")
def handle_update_room_settings(data):
    entry = registry.get_player_for_sid(request.sid)
    if entry is None:
        return
    room_code, player_id = entry
    with room_registry.room_session(room_code) as room:
        if room is None:
            socketio.emit("error", {"code": "ROOM_NOT_FOUND", "message": "Room not found"}, room=request.sid)
            return

        if player_id != room.host_player_id:
            socketio.emit("error", {"code": "NOT_AUTHORIZED", "message": "Only the host can change settings"}, room=request.sid)
            return

        if room.state.name != "WAITING":
            socketio.emit("error", {"code": "INVALID_STATE", "message": "Cannot change settings after match started"}, room=request.sid)
            return

        mode = data.get("mode")
        turn_timer_seconds = data.get("turn_timer_seconds")
        round_limit = data.get("round_limit")

        if mode not in ("endless", "rounds"):
            socketio.emit("error", {"code": "INVALID_MODE", "message": "Invalid game mode"}, room=request.sid)
            return

        if turn_timer_seconds is None or not (5 <= turn_timer_seconds <= 300):
            socketio.emit("error", {"code": "INVALID_TIMER", "message": "Turn timer must be between 5 and 300 seconds"}, room=request.sid)
            return

        if mode == "rounds":
            if round_limit is None or not (3 <= round_limit <= 12):
                socketio.emit("error", {"code": "INVALID_ROUND_LIMIT", "message": "Round limit must be between 3 and 12"}, room=request.sid)
                return
            room.round_limit = round_limit
        else:
            room.round_limit = None

        room.mode = mode
        room.turn_timer_seconds = turn_timer_seconds
        room.rejoin_enabled = (mode == "rounds")

        # Broadcast the updated snapshot to all players in the room
        socketio.emit("room_settings_updated", room.to_public_snapshot(), room=room.room_code)