"""
Connection lifecycle: create_room, join_room, reconnect, disconnect.
This is the thin translation layer — it never contains game rules itself,
only: receive event -> validate -> call into game/room_registry -> emit result.
"""

from flask import request
from flask_socketio import emit, join_room as sio_join_room, leave_room as sio_leave_room

from app import socketio
import room_registry
from config import RECONNECT_GRACE_SECONDS
from game.enums import PlayerConnectionState, RoomState
from sockets import registry
from sockets.rate_limit import rate_limited, clear_history_for_sid

@socketio.on("create_room")
@rate_limited(max_calls=3, per_seconds=10)
def handle_create_room(data):
    try:
        room = room_registry.create_room(
            host_name=data["host_name"],
            mode=data["mode"],
            max_players=data["max_players"],
            turn_timer_seconds=data["turn_timer_seconds"],
            round_limit=data.get("round_limit"),
        )
    except ValueError as e:
        socketio.emit("error", {"code": "INVALID_ROOM_CONFIG", "message": str(e)}, to=request.sid)
        return

    with room_registry.room_session(room.room_code) as room:
        player = room.add_player(data["host_name"])
        sio_join_room(room.room_code)
        registry.register(request.sid, room.room_code, player.player_id)

        socketio.emit("room_created", {"room_code": room.room_code, "room_state": "waiting"}, to=request.sid)
        socketio.emit("reconnect_success", {
            "room_state": room.to_public_snapshot(),
            "player_state": player.to_private_dict(),
        }, to=request.sid)


@socketio.on("join_room")
@rate_limited(max_calls=3, per_seconds=10)
def handle_join_room(data):
    with room_registry.room_session(data["room_code"]) as room:
        if room is None:
            socketio.emit("error", {"code": "ROOM_NOT_FOUND", "message": "No room with that code"}, to=request.sid)
            return

        try:
            player = room.add_player(data["player_name"])
        except ValueError as e:
            socketio.emit("error", {"code": "ROOM_FULL", "message": str(e)}, to=request.sid)
            return

        sio_join_room(room.room_code)
        registry.register(request.sid, room.room_code, player.player_id)

        socketio.emit("player_joined", {
            "player_id": player.player_id,
            "player_name": player.name,
            "current_player_count": len(room.players),
            "player": player.to_public_dict(is_host=(player.player_id == room.host_player_id)),
        }, room=room.room_code)

        socketio.emit("reconnect_success", {
            "room_state": room.to_public_snapshot(),
            "player_state": player.to_private_dict(),
        }, to=request.sid)


@socketio.on("reconnect")
def handle_reconnect(data):
    with room_registry.room_session(data["room_code"]) as room:
        if room is None:
            socketio.emit("error", {"code": "ROOM_NOT_FOUND", "message": "No room with that code"}, to=request.sid)
            return

        player = next(
            (p for p in room.players.values() if p.session_token == data["session_token"]),
            None,
        )
        if player is None:
            socketio.emit("error", {"code": "NOT_AUTHORIZED", "message": "Invalid session token"}, to=request.sid)
            return

        player.connection_state = PlayerConnectionState.CONNECTED
        sio_join_room(room.room_code)
        registry.register(request.sid, room.room_code, player.player_id)

        socketio.emit("reconnect_success", {
            "room_state": room.to_public_snapshot(),
            "player_state": player.to_private_dict(),
        }, to=request.sid)

def _resolve_turn_for_removed_player(room, player_id):
    if not room.is_current_turn(player_id):
        return

    turn_id = room.current_turn_id
    if not room.resolve_turn(turn_id):
        return

    room.previous_word = None
    room.previous_turn_player_id = None

    from sockets.turn_handlers import _finish_turn
    _finish_turn(room)

@socketio.on("leave_room")
def handle_leave_room(data=None):
    entry = registry.unregister_sid(request.sid)
    clear_history_for_sid(request.sid)
    if entry is None:
        return

    room_code, player_id = entry
    with room_registry.room_session(room_code) as room:
        if room is None:
            return

        player = room.get_player(player_id)
        if player is None:
            return

        if room.state == RoomState.WAITING:
            room.remove_player(player_id)
            host_player_id = room.host_player_id
            if player_id == room.host_player_id:
                if room.players:
                    room.host_player_id = list(room.players.keys())[0]
                    host_player_id = room.host_player_id
                else:
                    room.host_player_id = None
                    host_player_id = None
            
            sio_leave_room(room_code)
            socketio.emit("player_left", {
                "player_id": player_id,
                "host_player_id": host_player_id,
            }, room=room_code)
        else:
            player.connection_state = PlayerConnectionState.KICKED
            player.is_eliminated = True
            sio_leave_room(room_code)
            
            socketio.emit("player_kicked", {
                "player_id": player_id,
                "reason": "grace_period_expired",
            }, room=room_code)

            if room.state == RoomState.FINISHED:
                return

            from game import rules
            end_result = rules.check_win_condition(room)
            if end_result is not None:
                room.state = RoomState.FINISHED
                socketio.emit("game_ended", end_result, room=room_code)
                return

            if room.is_current_turn(player_id):
                _resolve_turn_for_removed_player(room,player_id)


@socketio.on("disconnect")
def handle_disconnect():
    entry = registry.unregister_sid(request.sid)
    clear_history_for_sid(request.sid)
    if entry is None:
        return

    room_code, player_id = entry
    with room_registry.room_session(room_code) as room:
        if room is None:
            return

        player = room.get_player(player_id)
        if player is None or player.is_eliminated:
            return

        player.connection_state = PlayerConnectionState.GRACE_PERIOD
        sio_leave_room(room_code)

        import time
        grace_ends_at = int((time.time() + RECONNECT_GRACE_SECONDS) * 1000)
        socketio.emit("player_disconnected", {
            "player_id": player_id,
            "grace_period_ends_at": grace_ends_at,
        }, room=room_code)

    socketio.start_background_task(_grace_period_watch, room_code, player_id)


def _grace_period_watch(room_code: str, player_id: str):
    socketio.sleep(RECONNECT_GRACE_SECONDS)

    with room_registry.room_session(room_code) as room:
        if room is None:
            return

        player = room.get_player(player_id)
        if player is None:
            return

        # Still disconnected after the grace window -> kick.
        if player.connection_state == PlayerConnectionState.GRACE_PERIOD:
            player.connection_state = PlayerConnectionState.KICKED
            player.is_eliminated = True

            socketio.emit("player_kicked", {
                "player_id": player_id,
                "reason": "grace_period_expired",
            }, room=room_code)

            if room.state == RoomState.FINISHED:
                return

            from game import rules
            end_result = rules.check_win_condition(room)
            if end_result is not None:
                room.state = RoomState.FINISHED
                socketio.emit("game_ended", end_result, room=room_code)

            if room.is_current_turn(player_id):
                _resolve_turn_for_removed_player(room,player_id)
                return


@socketio.on("submit_feedback")
def handle_submit_feedback(data):
    import json
    import os
    print(f"Feedback received: {data}")
    
    # Save feedback to both root feedback.json and backend/feedback.json
    try:
        # connection_handlers.py is located at backend/sockets/connection_handlers.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(current_dir)
        root_dir = os.path.dirname(backend_dir)

        root_feedback_path = os.path.join(root_dir, "feedback.json")
        backend_feedback_path = os.path.join(backend_dir, "feedback.json")

        for filepath in [root_feedback_path, backend_feedback_path]:
            feedbacks = []
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        feedbacks = json.load(f)
                        if not isinstance(feedbacks, list):
                            feedbacks = []
                except Exception:
                    feedbacks = []
            
            feedbacks.append(data)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(feedbacks, f, indent=2)

    except Exception as e:
        print(f"Error saving feedback: {e}")