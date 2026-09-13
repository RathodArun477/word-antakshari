import threading
import time

import pytest

import room_registry


@pytest.fixture(autouse=True)
def reset_rooms():
    room_registry._reset_for_tests()
    yield
    room_registry._reset_for_tests()


def create_room():
    return room_registry.create_room(
        host_name="Alice",
        mode="endless",
        max_players=8,
        turn_timer_seconds=30,
    )


def join_threads(threads, timeout=3):
    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=timeout)

    assert all(not thread.is_alive() for thread in threads)


def test_same_room_sessions_are_serialized():
    room = create_room()

    barrier = threading.Barrier(2)

    active = 0
    maximum_active = 0
    state_lock = threading.Lock()
    errors = []

    def worker():
        nonlocal active
        nonlocal maximum_active

        try:
            barrier.wait(timeout=2)

            with room_registry.room_session(room.room_code) as current:
                assert current is not None

                with state_lock:
                    active += 1
                    maximum_active = max(maximum_active, active)

                time.sleep(0.15)

                with state_lock:
                    active -= 1

        except BaseException as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=worker),
        threading.Thread(target=worker),
    ]

    join_threads(threads)

    assert errors == []
    assert maximum_active == 1


def test_different_rooms_do_not_block_each_other():
    room_a = create_room()
    room_b = create_room()

    barrier = threading.Barrier(2)
    errors = []

    def worker(room_code):
        try:
            with room_registry.room_session(room_code) as current:
                assert current is not None

                barrier.wait(timeout=2)
                time.sleep(0.10)

        except BaseException as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(room_a.room_code,)),
        threading.Thread(target=worker, args=(room_b.room_code,)),
    ]

    started = time.monotonic()
    join_threads(threads)
    elapsed = time.monotonic() - started

    assert errors == []
    assert elapsed < 0.18


def test_concurrent_mutations_are_not_lost():
    room = create_room()

    barrier = threading.Barrier(2)
    errors = []

    def add_player(name):
        try:
            barrier.wait(timeout=2)

            with room_registry.room_session(room.room_code) as current:
                assert current is not None
                current.add_player(name)

        except BaseException as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=add_player, args=("Alice",)),
        threading.Thread(target=add_player, args=("Bob",)),
    ]

    join_threads(threads)

    assert errors == []

    latest = room_registry.get_room(room.room_code)

    assert latest is not None
    assert len(latest.players) == 2
    assert {player.name for player in latest.players.values()} == {
        "Alice",
        "Bob",
    }


def test_room_session_saves_state_before_reraising_exception():
    room = create_room()

    with pytest.raises(RuntimeError, match="boom"):
        with room_registry.room_session(room.room_code) as current:
            assert current is not None

            current.add_player("Alice")

            raise RuntimeError("boom")

    latest = room_registry.get_room(room.room_code)

    assert latest is not None
    assert len(latest.players) == 1
    assert next(iter(latest.players.values())).name == "Alice"


def test_lock_is_released_after_exception():
    room = create_room()

    with pytest.raises(RuntimeError):
        with room_registry.room_session(room.room_code):
            raise RuntimeError("intentional")

    with room_registry.room_session(room.room_code) as current:
        assert current is not None


def test_missing_room_does_not_leave_lock_held():
    room = create_room()
    room_code = room.room_code

    room_registry.remove_room(room_code)

    assert room_registry.get_room(room_code) is None

    with room_registry.room_session(room_code) as current:
        assert current is None


def test_remove_room_uses_same_lock_boundary():
    room = create_room()
    room_code = room.room_code

    with room_registry.room_session(room_code) as current:
        assert current is not None
        current.add_player("Alice")

    room_registry.remove_room(room_code)

    assert room_registry.get_room(room_code) is None


def test_room_creation_produces_unique_codes_under_concurrency():
    rooms = []
    errors = []
    state_lock = threading.Lock()

    def create():
        try:
            room = create_room()

            with state_lock:
                rooms.append(room)

        except BaseException as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=create)
        for _ in range(20)
    ]

    join_threads(threads)

    assert errors == []
    assert len(rooms) == 20
    assert len({room.room_code for room in rooms}) == 20


def test_long_room_session_does_not_allow_same_room_reentry():
    room = create_room()

    entered = threading.Event()
    second_entered = threading.Event()
    errors = []

    def first():
        try:
            with room_registry.room_session(room.room_code) as current:
                assert current is not None

                entered.set()
                time.sleep(0.30)

        except BaseException as exc:
            errors.append(exc)

    def second():
        try:
            entered.wait(timeout=2)

            with room_registry.room_session(room.room_code) as current:
                assert current is not None
                second_entered.set()

        except BaseException as exc:
            errors.append(exc)

    first_thread = threading.Thread(target=first)
    second_thread = threading.Thread(target=second)

    first_thread.start()
    second_thread.start()

    time.sleep(0.10)

    assert second_entered.is_set() is False

    first_thread.join(timeout=3)
    second_thread.join(timeout=3)

    assert errors == []
    assert second_entered.is_set() is True