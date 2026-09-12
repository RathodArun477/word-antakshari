import pytest

from app import create_app, socketio
import room_registry
from sockets import registry


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture(autouse=True)
def reset_global_state():
    yield
    room_registry._reset_for_tests()
    registry._reset_for_tests()

    from sockets.rate_limit import _reset_for_tests as reset_rate_limits
    reset_rate_limits()


def create_two_player_room(app, mode="endless", round_limit=None):
    alice = socketio.test_client(app)
    bob = socketio.test_client(app)

    payload = {
        "host_name": "Alice",
        "mode": mode,
        "max_players": 8,
        "turn_timer_seconds": 30,
    }
    if round_limit is not None:
        payload["round_limit"] = round_limit

    alice.emit("create_room", payload)
    events = alice.get_received()
    room_code = events[0]["args"][0]["room_code"]

    bob.emit("join_room", {"room_code": room_code, "player_name": "Bob"})
    bob_events = bob.get_received()
    alice.get_received()

    bob_player_id_value = next(
        e["args"][0]["player_state"]["player_id"]
        for e in bob_events if e["name"] == "reconnect_success"
    )

    return alice, bob, room_code, bob_player_id_value


def test_room_creation_and_join(app):
    alice, bob, room_code,bob_id = create_two_player_room(app)
    assert len(room_code) == 6


def test_game_start_and_first_turn(app):
    alice, bob, room_code,bob_id = create_two_player_room(app)

    alice.emit("start_game", {})
    events = alice.get_received()
    event_names = [e["name"] for e in events]

    assert "game_started" in event_names
    assert "turn_start" in event_names

    turn_start = next(e for e in events if e["name"] == "turn_start")
    assert turn_start["args"][0]["round_number"] == 1


def test_word_submission_scores_and_advances_turn(app):
    alice, bob, room_code,bob_id = create_two_player_room(app)
    alice.emit("start_game", {})
    alice.get_received()
    bob.get_received()

    ack = alice.emit("word_submit", {"word": "python"}, callback=True)
    assert ack["accepted"] is True
    assert ack["word_length"] == 6
    assert ack["score_gained"] >= 60  # length*10 floor, plus time bonus on top

    events = alice.get_received()
    turn_resolved = next(e for e in events if e["name"] == "turn_resolved")
    assert turn_resolved["args"][0]["new_total_score"] == ack["score_gained"]

    turn_start = next(e for e in events if e["name"] == "turn_start")
    assert turn_start["args"][0]["player_id"] != turn_resolved["args"][0]["player_id"]
    assert turn_start["args"][0]["round_number"] == 1  # no wrap yet


def test_duplicate_word_rejected(app):
    alice, bob, room_code,bob_id = create_two_player_room(app)
    alice.emit("start_game", {})
    alice.get_received()
    bob.get_received()

    alice.emit("word_submit", {"word": "python"}, callback=True)
    alice.get_received()
    bob.get_received()

    # It's Bob's turn now — he tries the same word Alice already used.
    ack = bob.emit("word_submit", {"word": "python"}, callback=True)
    assert ack["accepted"] is False
    assert ack["reason_if_rejected"] == "already_used_warning"

    # Bob tries a second duplicate and incurs a life deduction penalty
    ack2 = bob.emit("word_submit", {"word": "python"}, callback=True)
    assert ack2["accepted"] is False
    assert ack2["reason_if_rejected"] == "already_used_penalty"


def test_word_submit_rejects_out_of_turn(app):
    alice, bob, room_code,bob_id = create_two_player_room(app)
    alice.emit("start_game", {})
    alice.get_received()
    bob.get_received()

    # It's Alice's turn — Bob tries to submit anyway.
    ack = bob.emit("word_submit", {"word": "backend"}, callback=True)
    assert ack["accepted"] is False
    assert ack["reason_if_rejected"] == "out_of_turn"

def test_math_flash_steal_challenge_end_to_end(app, monkeypatch):
    alice, bob, room_code, bob_id = create_two_player_room(app)
    alice.emit("start_game", {})
    alice.get_received()
    bob.get_received()

    # Force a predictable problem: 5 + 3 = 8
    import game.challenges as challenges_module
    values = iter([5, 3])
    monkeypatch.setattr(challenges_module.random, "randint", lambda a, b: next(values))
    monkeypatch.setattr(challenges_module.random, "choice", lambda seq: "+")

    alice.emit("use_steal", {"target_player_id": bob_id})
    alice_events = alice.get_received()
    assert any(e["name"] == "error" for e in alice_events) is False

    bob_events = bob.get_received()
    offer = next(e for e in bob_events if e["name"] == "steal_challenge_offer")
    assert offer["args"][0]["challenger_id"]

    bob.emit("steal_challenge_response", {"accept": True, "challenge_type_if_accepted": "math_flash"})

    bob_events = bob.get_received()
    alice_events = alice.get_received()

    start_event = next(e for e in bob_events if e["name"] == "challenge_start")
    assert start_event["args"][0]["prompt_data"]["expression"] == "5 + 3"

    bob.emit("challenge_submit", {"value": 8})
    alice.emit("challenge_submit", {"value": 999})

    bob_events = bob.get_received()
    alice_events = alice.get_received()

    result = next(
        (e for e in (bob_events + alice_events) if e["name"] == "steal_challenge_result"),
        None,
    )
    assert result is not None
    assert result["args"][0]["winner_id"] == bob_id
    assert result["args"][0]["life_transferred"] is True


def test_skip_powerup(app):
    alice, bob, room_code, bob_id = create_two_player_room(app)
    alice.emit("start_game", {})
    alice.get_received()
    bob.get_received()

    alice.emit("use_skip", {})
    events = alice.get_received()
    assert any(e["name"] == "skip_used" for e in events)

    turn_start = next(e for e in events if e["name"] == "turn_start")
    assert turn_start["args"][0]["player_id"] == bob_id


def test_double_score_powerup(app):
    alice, bob, room_code, bob_id = create_two_player_room(app)
    alice.emit("start_game", {})
    alice.get_received()
    
    alice.emit("word_submit", {"word": "python"})
    events = alice.get_received()
    turn_resolved = next(e for e in events if e["name"] == "turn_resolved")
    score_before = turn_resolved["args"][0]["new_total_score"]
    assert score_before > 0

    with room_registry.room_session(room_code) as room:
        alice_player = next(p for p in room.players.values() if p.player_id != bob_id)
        alice_player.has_double_score = True

    alice.emit("use_double_score", {})
    events = alice.get_received()
    double_event = next(e for e in events if e["name"] == "double_score_activated")
    assert double_event["args"][0]["new_total_score"] == score_before * 2


def test_rejoin_voting(app):
    alice, bob, room_code, bob_id = create_two_player_room(app, mode="rounds", round_limit=3)
    alice.emit("start_game", {})
    alice.get_received()
    bob.get_received()

    with room_registry.room_session(room_code) as room:
        p_bob = room.get_player(bob_id)
        p_bob.lives = 0
        p_bob.is_eliminated = True

    bob.emit("rejoin_request", {})
    events = alice.get_received()
    vote_start = next(e for e in events if e["name"] == "rejoin_vote_start")
    assert vote_start["args"][0]["requesting_player_id"] == bob_id

    alice.emit("rejoin_vote_cast", {"vote": True})
    
    from sockets.rejoin_handlers import _resolve_vote
    _resolve_vote(room_code)

    events = alice.get_received()
    result_event = next(e for e in events if e["name"] == "rejoin_result")
    assert result_event["args"][0]["approved"] is True
    assert result_event["args"][0]["player_id"] == bob_id
    with room_registry.room_session(room_code) as room:
        p_bob_latest = room.get_player(bob_id)
        assert p_bob_latest.lives == 1


def test_letter_chaining(app):
    alice, bob, room_code, bob_id = create_two_player_room(app)
    alice.emit("start_game", {})
    events = alice.get_received()
    turn_start = next(e for e in events if e["name"] == "turn_start")
    req_letter = turn_start["args"][0]["required_letter"]

    word_map = {
        'a': 'apple', 'b': 'banana', 'c': 'cherry', 'd': 'doggy', 'e': 'elephant',
        'f': 'flower', 'g': 'grape', 'h': 'house', 'i': 'island', 'j': 'jelly',
        'k': 'kitten', 'l': 'lemon', 'm': 'monkey', 'n': 'number', 'o': 'orange',
        'p': 'python', 'q': 'queen', 'r': 'rabbit', 's': 'summer', 't': 'turtle',
        'u': 'umbrella', 'v': 'violin', 'w': 'winter', 'x': 'xylophone', 'y': 'yellow',
        'z': 'zebra'
    }
    word = word_map[req_letter.lower()]
    
    ack = alice.emit("word_submit", {"word": word}, callback=True)
    assert ack["accepted"] is True
    
    events = alice.get_received()
    next_turn_start = next(e for e in events if e["name"] == "turn_start")
    assert next_turn_start["args"][0]["required_letter"] == word[-1]


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

    bob.emit("join_room", {"room_code": room_code, "player_name": "Bob"})
    bob_events = bob.get_received()
    alice.get_received()
    bob_id = next(
        e["args"][0]["player_state"]["player_id"]
        for e in bob_events if e["name"] == "reconnect_success"
    )

    charlie.emit("join_room", {"room_code": room_code, "player_name": "Charlie"})
    charlie_events = charlie.get_received()
    alice.get_received()
    bob.get_received()
    charlie_id = next(
        e["args"][0]["player_state"]["player_id"]
        for e in charlie_events if e["name"] == "reconnect_success"
    )

    return alice, bob, charlie, room_code, bob_id, charlie_id


def test_guess_streak_and_penalty(app):
    alice, bob, charlie, room_code, bob_id, charlie_id = create_three_player_room(app)
    alice.emit("start_game", {})
    alice.get_received()
    bob.get_received()
    charlie.get_received()

    with room_registry.room_session(room_code) as room:
        room.required_letter = "p"

    alice.emit("word_submit", {"word": "python"})
    alice.get_received()
    bob.get_received()
    charlie_events = charlie.get_received()
    guess_opts_event = next(e for e in charlie_events if e["name"] == "guess_options")
    options = guess_opts_event["args"][0]["options"]
    
    correct_index = options.index("python")
    charlie.emit("guess_submit", {"guess_index": correct_index})
    
    charlie_events = charlie.get_received()
    guess_res = next(e for e in charlie_events if e["name"] == "guess_result")
    assert guess_res["args"][0]["correct"] is True
    assert guess_res["args"][0]["streak_count"] == 1

    charlie.emit("guess_submit",{"guess_index": correct_index})

    second_guess_events = charlie.get_received()

    assert any(
        event["name"] == "error"
        and event["args"][0]["code"] == "ALREADY_GUESSED"
        for event in second_guess_events
    )