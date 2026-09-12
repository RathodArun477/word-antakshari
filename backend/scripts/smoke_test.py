"""
Manual smoke test using flask_socketio's test client — no real server/port
needed. Run with: python smoke_test.py
"""
from app import create_app, socketio

app = create_app()

alice = socketio.test_client(app)
bob = socketio.test_client(app)

print("--- Alice creates room ---")
alice.emit("create_room", {
    "host_name": "Alice",
    "mode": "endless",
    "max_players": 8,
    "turn_timer_seconds": 30,
})
for event in alice.get_received():
    print(event)

# Pull the room_code and Alice's player_id out of what she received.
alice_events = {e["name"]: e["args"][0] for e in alice.get_received()}
# (get_received() drains the queue, so re-fetch by emitting again won't work —
#  instead capture on first call. See note below code.)

print("\n--- Bob joins ---")
# room_code needs to come from the room_created event printed above —
# copy it in manually for this first test run.
room_code = input("Paste the room_code printed above: ").strip()

bob.emit("join_room", {"room_code": room_code, "player_name": "Bob"})
for event in bob.get_received():
    print(event)

print("\n--- Alice starts the game ---")
alice.emit("start_game", {})
for event in alice.get_received():
    print(event)
for event in bob.get_received():
    print(event)

print("\n--- Submit a word (try both clients, only the current turn player should succeed) ---")
alice.emit("word_submit", {"word": "python"})
print("Alice's word_submit response:", alice.get_received())

bob.emit("word_submit", {"word": "python"})
print("Bob's word_submit response:", bob.get_received())