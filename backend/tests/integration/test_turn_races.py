import pytest

from app import socketio
import room_registry


def create_two_player_room(app):
    alice = socketio.test_client(app)
    bob = socketio.test_client(app)

    alice.emit("create_room", {
        "host_name": "Alice",
        "mode": "endless",
        "max_players": 8,
        "turn_timer_seconds": 30,
    })

    room_code = alice.get_received()[0]["args"][0]["room_code"]

    bob.emit("join_room", {
        "room_code": room_code,
        "player_name": "Bob",
    })
    bob.get_received()
    alice.get_received()

    return alice, bob, room_code

def current_turn_id(room_code):
    with room_registry.room_session(room_code) as room:
        return room.current_turn_id

def current_turn(room_code):
    with room_registry.room_session(room_code) as room:
        return (
            room.current_turn_id,
            room.current_turn_deadline_at,
            room.get_current_player().player_id,
        )


def test_timeout_watcher_cannot_resolve_completed_turn(app, monkeypatch):
    alice, bob, room_code = create_two_player_room(app)

    alice.emit("start_game", {})
    alice.get_received()
    bob.get_received()

    turn_id, deadline_at, alice_id = current_turn(room_code)

    ack = alice.emit(
        "word_submit",
        {"word": "python", "turn_id": turn_id},
        callback=True,
    )
    assert ack["accepted"] is True

    new_turn_id, _, bob_id = current_turn(room_code)
    assert new_turn_id != turn_id
    assert bob_id != alice_id

    import sockets.turn_handlers as turn_handlers
    monkeypatch.setattr(turn_handlers.socketio, "sleep", lambda _: None)

    turn_handlers._turn_timeout_watch(
        room_code,
        turn_id,
        deadline_at,
        alice_id,
    )

    with room_registry.room_session(room_code) as room:
        assert room.current_turn_id == new_turn_id
        assert room.get_current_player().player_id == bob_id
        assert room.turn_resolved is False


def test_timeout_watcher_ignores_wrong_turn_id(app, monkeypatch):
    alice, bob, room_code = create_two_player_room(app)

    alice.emit("start_game", {})
    alice.get_received()
    bob.get_received()

    turn_id, deadline_at, alice_id = current_turn(room_code)

    with room_registry.room_session(room_code) as room:
        room.turn_resolved = True
        room.advance_turn()

    _, _, bob_id = current_turn(room_code)

    import sockets.turn_handlers as turn_handlers
    monkeypatch.setattr(turn_handlers.socketio, "sleep", lambda _: None)

    turn_handlers._turn_timeout_watch(
        room_code,
        turn_id,
        deadline_at,
        alice_id,
    )

    with room_registry.room_session(room_code) as room:
        assert room.get_current_player().player_id == bob_id


def test_skip_rejects_stale_turn_id(app):
    alice, bob, room_code = create_two_player_room(app)

    alice.emit("start_game", {})
    alice.get_received()
    bob.get_received()

    first_turn_id = current_turn_id(room_code)

    alice.emit("use_skip", {"turn_id": first_turn_id})

    events = alice.get_received()
    second_turn_start = next(
        event for event in events
        if event["name"] == "turn_start"
    )
    second_turn_id = second_turn_start["args"][0]["turn_id"]

    assert second_turn_id != first_turn_id
    assert current_turn_id(room_code) == second_turn_id

    # Alice is no longer the current player, so this stale turn ID must fail.
    alice.emit("use_skip", {"turn_id": first_turn_id})

    error_events = alice.get_received()
    assert any(event["name"] == "error" for event in error_events)

    with room_registry.room_session(room_code) as room:
        assert room.current_turn_id == second_turn_id
        assert room.turn_resolved is False

def test_current_player_leaving_advances_exactly_once(app):
    alice, bob, charlie, room_code = create_three_player_room(app)

    alice.emit("start_game", {})
    alice.get_received()
    bob.get_received()
    charlie.get_received()

    first_turn_id, _, alice_id = current_turn(room_code)

    alice.emit("leave_room", {})

    with room_registry.room_session(room_code) as room:
        assert room.current_turn_id != first_turn_id
        assert room.get_current_player().player_id != alice_id
        assert room.turn_resolved is False


def create_three_player_room(app):
    alice = socketio.test_client(app)
    bob = socketio.test_client(app)
    charlie = socketio.test_client(app)

    alice.emit("create_room", {
        "host_name": "Alice",
        "mode": "endless",
        "max_players": 8,
        "turn_timer_seconds": 30,
    })

    events = alice.get_received()
    room_code = events[0]["args"][0]["room_code"]

    bob.emit("join_room", {
        "room_code": room_code,
        "player_name": "Bob",
    })
    bob.get_received()
    alice.get_received()

    charlie.emit("join_room", {
        "room_code": room_code,
        "player_name": "Charlie",
    })
    charlie.get_received()
    alice.get_received()
    bob.get_received()

    return alice, bob, charlie, room_code