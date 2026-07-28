"""
Redis-backed room storage. GameRoom objects are serialized to JSON on
write, deserialized back into real GameRoom objects on read — this is what
lets sockets/ code keep calling room.advance_turn() etc. exactly as before,
while the actual storage is Redis instead of an in-memory dict.

Key pattern: "room:{room_code}" -> JSON string of GameRoom.to_dict()
"""
import json
import os
from contextlib import contextmanager

import redis

from game.state import GameRoom, generate_room_code

try:
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        _redis_client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
    else:
        _redis_client = redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            decode_responses=True,
            socket_connect_timeout=2,
        )
    _redis_client.ping()
except Exception:
    import fakeredis
    print("Warning: Redis server not found. Falling back to in-memory fakeredis.")
    _redis_client = fakeredis.FakeRedis(decode_responses=True)

ROOM_TTL_SECONDS = 6 * 60 * 60  # 6 hours -- auto-expire abandoned/finished rooms


def _key(room_code: str) -> str:
    return f"room:{room_code}"


def create_room(host_name: str, mode: str, max_players: int,
                 turn_timer_seconds: int, round_limit: int | None = None) -> GameRoom:
    room = GameRoom(
        host_name=host_name,
        mode=mode,
        max_players=max_players,
        turn_timer_seconds=turn_timer_seconds,
        round_limit=round_limit,
    )

    while _redis_client.exists(_key(room.room_code)):
        room.room_code = generate_room_code()

    _save(room)
    return room


def get_room(room_code: str) -> GameRoom | None:
    raw = _redis_client.get(_key(room_code))
    if raw is None:
        return None
    return GameRoom.from_dict(json.loads(raw))


def remove_room(room_code: str) -> None:
    _redis_client.delete(_key(room_code))


def _save(room: GameRoom) -> None:
    _redis_client.set(_key(room.room_code), json.dumps(room.to_dict()), ex=ROOM_TTL_SECONDS)


@contextmanager
def room_session(room_code: str):
    """
    Loads a room, yields it for mutation, saves it back automatically when
    the `with` block exits -- even on early return or an exception (in
    which case it still saves whatever state was reached, matching how the
    old in-memory version behaved, where a mutation was "live" the instant
    it happened regardless of control flow).

    Usage in a handler:
        with room_registry.room_session(room_code) as room:
            if room is None:
                emit("error", ...)
                return
            room.submit_word(...)
            # no explicit save needed -- happens automatically here
    """
    room = get_room(room_code)
    try:
        yield room
    finally:
        if room is not None:
            _save(room)


def set_json(key: str, data: dict, ex: int | None = None) -> None:
    _redis_client.set(key, json.dumps(data), ex=ex)


def get_json(key: str) -> dict | None:
    raw = _redis_client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


def set_val(key: str, val: str, ex: int | None = None) -> None:
    _redis_client.set(key, val, ex=ex)


def get_val(key: str) -> str | None:
    return _redis_client.get(key)


def delete_key(key: str) -> None:
    _redis_client.delete(key)


def _reset_for_tests() -> None:
    for pattern in ("room:*", "steal_offer:*", "rejoin_vote:*", "active_challenge:*"):
        for key in _redis_client.keys(pattern):
            _redis_client.delete(key)