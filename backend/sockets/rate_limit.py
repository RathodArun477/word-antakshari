"""
Simple sliding-window rate limiting per socket connection, applied as a
decorator on individual event handlers. In-memory — same caveat as
room_registry and sockets/registry: fine for now, would need to move to
Redis alongside them for true multi-worker scaling.
"""
import time
import functools

from flask import request
from flask_socketio import emit

# sid -> {event_name: [timestamps]}
_call_history: dict[str, dict[str, list[float]]] = {}


def rate_limited(max_calls: int, per_seconds: float):
    """
    Decorator factory. Usage:
        @socketio.on("word_submit")
        @rate_limited(max_calls=3, per_seconds=5)
        def handle_word_submit(data):
            ...
    Must be applied BELOW @socketio.on(...) so it wraps the actual handler,
    not the registration.
    """
    def decorator(handler):
        @functools.wraps(handler)
        def wrapped(*args, **kwargs):
            sid = request.sid
            event_name = handler.__name__
            now = time.time()

            history = _call_history.setdefault(sid, {}).setdefault(event_name, [])
            # Drop timestamps outside the window before checking/adding.
            cutoff = now - per_seconds
            while history and history[0] < cutoff:
                history.pop(0)

            if len(history) >= max_calls:
                emit("error", {
                    "code": "RATE_LIMITED",
                    "message": f"Too many {event_name} calls — slow down",
                }, room=sid)
                return None

            history.append(now)
            return handler(*args, **kwargs)

        return wrapped
    return decorator


def clear_history_for_sid(sid: str) -> None:
    """Call this from the disconnect handler to avoid unbounded memory growth."""
    _call_history.pop(sid, None)


def _reset_for_tests() -> None:
    _call_history.clear()