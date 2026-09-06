import os
from flask import Flask
from flask_socketio import SocketIO

from game.validation import load_wordlist

socketio = SocketIO(async_mode="threading", logger=True, engineio_logger=True)


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return {"status": "ok"},200

    load_wordlist()

    cors_allowed = os.environ.get("CORS_ALLOWED_ORIGINS", "*")
    if cors_allowed != "*":
        cors_allowed = [origin.strip() for origin in cors_allowed.split(",")]

    message_queue = os.environ.get("REDIS_QUEUE_URL")

    socketio.init_app(
        app,
        cors_allowed_origins=cors_allowed,
        message_queue=message_queue,
    )

    from sockets import connection_handlers, turn_handlers, guess_handlers, powerup_handlers, rejoin_handlers, lobby_handlers, challenge_handlers  # noqa: F401

    return app
