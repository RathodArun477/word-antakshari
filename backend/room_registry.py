"""
Redis-backed room storage.

GameRoom objects are serialized to JSON on write and deserialized back into
real GameRoom objects on read.

Concurrency model
-----------------
All mutations of an existing room must go through room_session().

room_session() provides a per-room distributed Redis lock:

    acquire room lock
        ↓
    load latest room state
        ↓
    yield mutable GameRoom
        ↓
    verify lock ownership
        ↓
    save room state
        ↓
    release room lock

This prevents the classic lost-update race where two workers independently
load the same GameRoom, mutate different fields, and then overwrite one
another's changes.

The Redis lock has a lease which is automatically renewed while the room
session is active. Therefore the lease is primarily a crash-recovery
mechanism, not a maximum duration for normal room mutations.
"""

import json
import os
import threading
from contextlib import contextmanager

import redis

from game.state import GameRoom, generate_room_code


# ---------------------------------------------------------------------------
# Redis connection
# ---------------------------------------------------------------------------

try:
    redis_url = os.environ.get("REDIS_URL")

    if redis_url:
        _redis_client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
        )
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


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOM_TTL_SECONDS = 6 * 60 * 60

# Redis lock lease.
#
# This is NOT intended to limit a room_session() to 60 seconds. The lock is
# extended periodically while the owning session is active.
ROOM_LOCK_LEASE_SECONDS = 60

# Must be significantly smaller than the lease so temporary scheduling delays
# do not normally cause ownership loss.
ROOM_LOCK_RENEW_INTERVAL_SECONDS = 20

# Maximum amount of time a caller waits for another worker to finish mutating
# the same room.
ROOM_LOCK_WAIT_SECONDS = 15


# ---------------------------------------------------------------------------
# Redis lock
# ---------------------------------------------------------------------------

class _RoomLock:
    """
    Redis-backed distributed lock with automatic lease renewal.

    thread_local=False is intentional.

    The lease-renewal heartbeat runs in a separate Python thread from the
    thread that owns room_session(), so the Redis lock token must be shared
    between those threads.
    """

    def __init__(self, room_code: str):
        self.room_code = room_code

        self._lock = _redis_client.lock(
            name=f"room_lock:{room_code}",
            timeout=ROOM_LOCK_LEASE_SECONDS,
            blocking_timeout=ROOM_LOCK_WAIT_SECONDS,
            thread_local=False,
            raise_on_release_error=False,
        )

        self._stop_heartbeat = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

        self._ownership_lost = False
        self._heartbeat_exception: BaseException | None = None

    # ------------------------------------------------------------------
    # Acquire
    # ------------------------------------------------------------------

    def acquire(self) -> None:
        acquired = self._lock.acquire()

        if not acquired:
            raise TimeoutError(
                f"Could not acquire room lock for {self.room_code} "
                f"within {ROOM_LOCK_WAIT_SECONDS} seconds"
            )

        self._heartbeat_thread = threading.Thread(
            target=self._renew_loop,
            name=f"room-lock-heartbeat-{self.room_code}",
            daemon=True,
        )

        self._heartbeat_thread.start()

    # ------------------------------------------------------------------
    # Lease renewal
    # ------------------------------------------------------------------

    def _renew_loop(self) -> None:
        while not self._stop_heartbeat.wait(
            ROOM_LOCK_RENEW_INTERVAL_SECONDS
        ):
            try:
                renewed = self._lock.extend(
                    ROOM_LOCK_LEASE_SECONDS,
                    replace_ttl=True,
                )

                if not renewed:
                    self._ownership_lost = True
                    return

            except BaseException as exc:
                self._ownership_lost = True
                self._heartbeat_exception = exc
                return

    # ------------------------------------------------------------------
    # Ownership verification
    # ------------------------------------------------------------------

    def ensure_owned(self) -> None:
        """
        Verify that this worker can safely persist the room.

        A stale worker MUST NOT write its in-memory GameRoom after losing the
        Redis lock, because another worker may already have changed the room.
        """
        if self._ownership_lost:
            if self._heartbeat_exception is not None:
                raise RuntimeError(
                    f"Lost Redis lock ownership for room {self.room_code}"
                ) from self._heartbeat_exception

            raise RuntimeError(
                f"Lost Redis lock ownership for room {self.room_code}"
            )

        if not self._lock.owned():
            raise RuntimeError(
                f"Lost Redis lock ownership for room {self.room_code}"
            )

    # ------------------------------------------------------------------
    # Release
    # ------------------------------------------------------------------

    def release(self) -> None:
        self._stop_heartbeat.set()

        heartbeat = self._heartbeat_thread

        if (
            heartbeat is not None
            and heartbeat.is_alive()
            and heartbeat is not threading.current_thread()
        ):
            heartbeat.join(
                timeout=max(
                    1.0,
                    min(
                        ROOM_LOCK_RENEW_INTERVAL_SECONDS,
                        ROOM_LOCK_LEASE_SECONDS,
                    ),
                )
            )

        self._heartbeat_thread = None

        # We intentionally suppress release errors.

        # If the lease was already lost, redis-py can report a release error.
        # At that point there is nothing useful left to release, and masking
        # the original application exception would make debugging harder.
        try:
            self._lock.release()
        except Exception:
            pass


@contextmanager
def _room_lock(room_code: str):
    lock = _RoomLock(room_code)
    lock.acquire()

    try:
        yield lock
    finally:
        lock.release()


# ---------------------------------------------------------------------------
# Room key helpers
# ---------------------------------------------------------------------------

def _key(room_code: str) -> str:
    return f"room:{room_code}"


# ---------------------------------------------------------------------------
# Room creation
# ---------------------------------------------------------------------------

def create_room(
    host_name: str,
    mode: str,
    max_players: int,
    turn_timer_seconds: int,
    round_limit: int | None = None,
) -> GameRoom:
    """
    Create and persist a room using atomic Redis SET NX semantics.

    This avoids the old:

        EXISTS → generate → SAVE

    race.
    """

    for _ in range(100):
        room = GameRoom(
            host_name=host_name,
            mode=mode,
            max_players=max_players,
            turn_timer_seconds=turn_timer_seconds,
            round_limit=round_limit,
        )

        created = _redis_client.set(
            _key(room.room_code),
            json.dumps(room.to_dict()),
            nx=True,
            ex=ROOM_TTL_SECONDS,
        )

        if created:
            return room

        # The generated room code collided. Generate another on the next
        # iteration.
        room.room_code = generate_room_code()

    raise RuntimeError("Unable to allocate a unique room code")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_room(room_code: str) -> GameRoom | None:
    """
    Return a snapshot of a room.

    This is intentionally read-only and does not acquire the mutation lock.

    Any operation that needs:

        read → mutate → write

    MUST use room_session().
    """
    raw = _redis_client.get(_key(room_code))

    if raw is None:
        return None

    return GameRoom.from_dict(json.loads(raw))


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def _save(room: GameRoom) -> None:
    """
    Persist a GameRoom.

    Callers are responsible for holding the appropriate room lock.
    """
    _redis_client.set(
        _key(room.room_code),
        json.dumps(room.to_dict()),
        ex=ROOM_TTL_SECONDS,
    )


# ---------------------------------------------------------------------------
# Atomic room session
# ---------------------------------------------------------------------------

@contextmanager
def room_session(room_code: str):
    """
    Atomically load, mutate and save one room.

    Lock acquisition happens BEFORE GET.

    That ordering is critical:

        worker A: acquire → GET
        worker B: waits

    instead of:

        worker A: GET
        worker B: GET
        worker A: SAVE
        worker B: SAVE  ← overwrites worker A
    """

    with _room_lock(room_code) as lock:
        room = get_room(room_code)

        try:
            yield room

        except BaseException:
            # Preserve the historical behavior of this project: mutations
            # reached before an exception are persisted before re-raising.
            #
            # But never write stale state after losing the room lock.
            if room is not None:
                lock.ensure_owned()
                _save(room)

            raise

        else:
            if room is not None:
                lock.ensure_owned()
                _save(room)


# ---------------------------------------------------------------------------
# Room deletion
# ---------------------------------------------------------------------------

def remove_room(room_code: str) -> None:
    """
    Delete a room under the same room-level synchronization boundary.

    This prevents:

        room_session:
            GET room
            ...

        remove_room:
            DELETE room

        room_session:
            SAVE room

    from accidentally resurrecting a deleted room.
    """
    with _room_lock(room_code):
        _redis_client.delete(_key(room_code))


# ---------------------------------------------------------------------------
# Generic Redis helpers
# ---------------------------------------------------------------------------

def set_json(key: str, data: dict, ex: int | None = None) -> None:
    _redis_client.set(
        key,
        json.dumps(data),
        ex=ex,
    )


def get_json(key: str) -> dict | None:
    raw = _redis_client.get(key)

    if raw is None:
        return None

    return json.loads(raw)


def set_val(key: str, val: str, ex: int | None = None) -> None:
    _redis_client.set(
        key,
        val,
        ex=ex,
    )


def get_val(key: str) -> str | None:
    return _redis_client.get(key)


def delete_key(key: str) -> None:
    _redis_client.delete(key)


# ---------------------------------------------------------------------------
# Test cleanup
# ---------------------------------------------------------------------------

def _reset_for_tests() -> None:
    """
    Remove test data.

    This includes room locks because abandoned lock keys from a failed test
    must never contaminate the next test.
    """
    for pattern in (
        "room:*",
        "room_lock:*",
        "steal_offer:*",
        "rejoin_vote:*",
        "active_challenge:*",
    ):
        for key in _redis_client.keys(pattern):
            _redis_client.delete(key)