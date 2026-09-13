import pytest

from app import create_app
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

