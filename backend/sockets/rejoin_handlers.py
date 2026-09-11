"""
Rejoin flow: an eliminated player requests to rejoin, active players vote
(majority, 15s timeout, not unanimous), and the result is applied.
Rounds mode only — rules.request_rejoin already re-validates this itself.
"""
from flask import request
from flask_socketio import emit

from app import socketio
import room_registry
from sockets import registry
from game import rules




@socketio.on("rejoin_request")
def handle_rejoin_request(data=None):
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

        result = rules.request_rejoin(room, player)
        if not result["success"]:
            socketio.emit("error", {"code": "NOT_AUTHORIZED", "message": result["reason"]}, room=request.sid)
            return

        vote_key = f"rejoin_vote:{room_code}"
        if room_registry.get_json(vote_key) is not None:
            socketio.emit("error", {"code": "NOT_AUTHORIZED", "message": "vote_already_in_progress"}, room=request.sid)
            return

        room_registry.set_json(vote_key, {"requester_id": player_id, "votes": {}}, ex=300)

        from config import REJOIN_VOTE_TIMEOUT_SECONDS
        import time
        expires_at = int((time.time() + REJOIN_VOTE_TIMEOUT_SECONDS) * 1000)

        for active_player in room.active_players:
            sid = registry.get_sid_for_player(active_player.player_id)
            if sid:
                socketio.emit("rejoin_vote_start", {
                    "requesting_player_id": player_id,
                    "expires_at": expires_at,
                    "duration_seconds": REJOIN_VOTE_TIMEOUT_SECONDS,
                }, room=sid)

    socketio.start_background_task(_vote_timeout_watch, room_code, REJOIN_VOTE_TIMEOUT_SECONDS)


@socketio.on("rejoin_vote_cast")
def handle_rejoin_vote_cast(data):
    entry = registry.get_player_for_sid(request.sid)
    if entry is None:
        return
    room_code, player_id = entry

    vote_key = f"rejoin_vote:{room_code}"
    vote_state = room_registry.get_json(vote_key)
    if vote_state is None:
        socketio.emit("error", {"code": "INVALID_PHASE", "message": "no_vote_in_progress"}, room=request.sid)
        return

    # One vote per player, enforced here — re-voting just overwrites their
    # own entry rather than being rejected, which is fine since it's still
    # exactly one vote counted per player_id at tally time.
    vote_state["votes"][player_id] = data["vote"]
    room_registry.set_json(vote_key, vote_state, ex=300)


def _vote_timeout_watch(room_code: str, duration: float) -> None:
    socketio.sleep(duration)
    _resolve_vote(room_code)


def _resolve_vote(room_code: str) -> None:
    vote_key = f"rejoin_vote:{room_code}"
    vote_state = room_registry.get_json(vote_key)
    if vote_state is None:
        return  # already resolved (e.g. everyone voted early -- see note below)
    room_registry.delete_key(vote_key)

    with room_registry.room_session(room_code) as room:
        if room is None:
            return

        eligible_count = len(room.active_players)
        approved = rules.tally_rejoin_vote(vote_state["votes"], eligible_count)

        requester = room.get_player(vote_state["requester_id"])
        new_score = None
        if approved and requester is not None:
            old_score = requester.score
            new_score = rules.apply_rejoin(requester)
            deducted_points = old_score - new_score

            # Distribute deducted points to Yes-voters
            yes_voters = [pid for pid, val in vote_state["votes"].items() if val]
            if yes_voters and deducted_points > 0:
                share = int(deducted_points / len(yes_voters))
                for pid in yes_voters:
                    voter = room.get_player(pid)
                    if voter:
                        voter.score += share

        socketio.emit("rejoin_result", {
            "player_id": vote_state["requester_id"],
            "approved": approved,
            "new_score_if_approved": new_score,
            "room_state": room.to_public_snapshot() if room else None,
        }, room=room_code)