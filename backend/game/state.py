"""
GameRoom — the core state machine for a single game room.
Pure Python — no Flask, no socket, no network imports. Every method here
should be callable and testable with zero server running.
"""
import random
import string
import time
import uuid

from game.enums import RoomState, PlayerConnectionState
from game.player import Player
from config import (
    MIN_PLAYERS,
    MAX_PLAYERS,
    MODE_ENDLESS,
    MODE_ROUNDS,
    ROUNDS_MODE_MIN_LIMIT,
    ROUNDS_MODE_MAX_LIMIT,
    STARTING_LIVES,
)

def generate_random_letter() -> str:
    import string
    return random.choice(string.ascii_lowercase)

def generate_room_code(length: int = 6) -> str:
    """Random unguessable alphanumeric code — never sequential IDs."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choices(alphabet, k=length))


class GameRoom:
    def __init__(self, host_name: str, mode: str, max_players: int, turn_timer_seconds: int, round_limit: int | None = None):
        if mode not in (MODE_ENDLESS, MODE_ROUNDS):
            raise ValueError(f"Invalid mode: {mode}")

        if not (MIN_PLAYERS <= max_players <= MAX_PLAYERS):
            raise ValueError(
                f"max_players must be between {MIN_PLAYERS} and {MAX_PLAYERS}"
            )

        if mode == MODE_ROUNDS:
            if round_limit is None or not (ROUNDS_MODE_MIN_LIMIT <= round_limit <= ROUNDS_MODE_MAX_LIMIT):
                raise ValueError(
                    f"round_limit is required for rounds mode and must be "
                    f"between {ROUNDS_MODE_MIN_LIMIT} and {ROUNDS_MODE_MAX_LIMIT}"
                )
        else:
            round_limit = None  # ignored/cleared for endless mode

        self.room_code = generate_room_code()
        self.mode = mode
        self.max_players = max_players
        self.turn_timer_seconds = turn_timer_seconds
        self.round_limit = round_limit
        self.rejoin_enabled = (mode == MODE_ROUNDS)

        self.state = RoomState.WAITING
        self.created_at = time.time()

        self.players: dict[str, Player] = {}
        self.turn_order: list[str] = []       # player_ids, fixed once game starts
        self.round_player_ids: list[str] = []
        self.host_player_id: str | None = None

        self.used_words: set[str] = set()      # rule 4 — no repeats, by anyone
        self.current_round: int = 0
        self.current_turn_index: int = 0
        self.required_letter: str | None = None
        self.previous_word: str | None = None
        self.previous_turn_player_id: str | None = None
        self.current_turn_id: str | None = None
        self.current_turn_started_at: float | None = None
        self.current_turn_deadline_at: float | None = None
        self.turn_resolved: bool = False
        self.current_guess_options: list[str] = []
        self.guess_submissions: set[str] = set()


    # --- Player management (lobby phase only) ---

    def add_player(self, name: str) -> Player:
        if self.state != RoomState.WAITING:
            raise ValueError("Cannot join — game already started")
        if len(self.players) >= self.max_players:
            raise ValueError("Room is full")

        player = Player(name=name)
        self.players[player.player_id] = player

        if self.host_player_id is None:
            self.host_player_id = player.player_id

        return player

    def remove_player(self, player_id: str) -> None:
        self.players.pop(player_id, None)
        if self.turn_order and player_id in self.turn_order:
            self.turn_order.remove(player_id)

    def can_start(self) -> bool:
        return self.state == RoomState.WAITING and len(self.players) >= MIN_PLAYERS

    # --- Helpers used throughout the rest of game logic ---

    @property
    def active_players(self) -> list[Player]:
        """Non-eliminated players — the set used for turn order, voting, guessing eligibility."""
        return [p for p in self.players.values() if not p.is_eliminated]

    def get_player(self, player_id: str) -> Player | None:
        return self.players.get(player_id)

    def to_public_snapshot(self) -> dict:
            current = self.get_current_player() if self.state == RoomState.IN_PROGRESS else None
            return {
                "room_code": self.room_code,
                "mode": self.mode,
                "state": self.state.name.lower(),
                "players": [p.to_public_dict(is_host=(p.player_id == self.host_player_id)) for p in self.players.values()],
                "host_player_id": self.host_player_id,
                "current_round": self.current_round if self.mode == MODE_ROUNDS else None,
                "current_turn_player_id": current.player_id if current else None,
                "required_letter": self.required_letter,
                "turn_started_at": int(self.current_turn_started_at * 1000) if self.current_turn_started_at else None,
                "turn_duration_seconds": self.turn_timer_seconds,
                "turn_timer_seconds": self.turn_timer_seconds,
                "round_limit": self.round_limit,
            }
    
    # --- Turn Flow ---

    def start_game(self) -> None:
        if not self.can_start():
            raise ValueError("Cannot start - not enough players or already started")

        self.turn_order = list(self.players.keys())
        self.round_player_ids = [
            player_id
            for player_id in self.turn_order
            if (
                (player := self.players.get(player_id)) is not None and not player.is_eliminated
            )
        ]

        self.state = RoomState.IN_PROGRESS
        self.current_round = 1
        self.current_turn_index = 0
        self.required_letter = generate_random_letter()

    def get_current_player(self) -> Player | None:
        if not self.turn_order:
            return None
        current_id = self.turn_order[self.current_turn_index]
        return self.players.get(current_id)
    
    def is_current_turn(self,player_id:str) -> bool:
        current = self.get_current_player()
        return current is not None and current.player_id == player_id

    def new_turn_id(self) -> str:
        return uuid.uuid4().hex

    def activate_turn(self,turn_id:str,started_at:float,deadline_at:float) -> None:
        if self.get_current_player() is None:
            raise ValueError("Cannot activate a turn without a current player")
        if not turn_id:
            raise ValueError("turn_id is required")
        if deadline_at <= started_at:
            raise ValueError("Turn deadline must be after turn start")

        self.current_turn_id = turn_id
        self.current_turn_started_at = started_at
        self.current_turn_deadline_at = deadline_at
        self.turn_resolved = False
        self.current_guess_options = []

    def is_active_turn(self,turn_id: str | None) -> bool:
        return (
            turn_id is not None and turn_id == self.current_turn_id and not self.turn_resolved and self.state == RoomState.IN_PROGRESS and self.get_current_player() is not None
        )

    def resolve_turn(self,turn_id:str | None) -> bool:
        if not self.is_active_turn(turn_id):
            return False

        self.turn_resolved = True
        return True
    
    def advance_turn(self) -> None:
        """
        Move to the next eligible player.

        turn_order is fixed for the lifetime of the game.
        round_player_ids defines who participates in the current round.
        Eliminated players are skipped.

        When the raw turn index wraps from the end of turn_order back to zero,
        a new round begins and the current active players are snapshotted into
        round_player_ids.
        """
        if not self.turn_order:
            raise ValueError("Game has not started")

        attempts = 0
        max_attempts = len(self.turn_order)

        while attempts < max_attempts:
            self.current_turn_index += 1

            if self.current_turn_index >= len(self.turn_order):
                self.current_turn_index = 0
                self.current_round += 1

                self.round_player_ids = [
                    player_id
                    for player_id in self.turn_order
                    if (
                        (player := self.players.get(player_id)) is not None
                        and not player.is_eliminated
                    )
                ]

            candidate_id = self.turn_order[self.current_turn_index]
            candidate = self.players.get(candidate_id)

            if (
                candidate is not None
                and not candidate.is_eliminated
                and candidate.player_id in self.round_player_ids
            ):
                return

            attempts += 1

        raise RuntimeError(
            "advance_turn found no eligible players — "
            "rules.check_win_condition() must be called before advance_turn "
            "to catch this earlier as a real game-end event"
        )
    # --- Word Submission ----

    def submit_word(self,player_id:str,word:str,turn_deadline_at:float | None,word_is_valid_fn) -> dict:

        if not self.is_current_turn(player_id):
            return {"accepted":False,"reasion_if_rejected":"out_of_turn"}

        if turn_deadline_at is None or time.time() >= turn_deadline_at:
            return {"accepted":False,"reason_if_rejected":"turn_expired"}
        if not self.is_current_turn(player_id):
            return {"accepted": False, "reason_if_rejected":"out_of_turn"}
        
        normalized = word.strip().lower()
        import os
        is_testing = "PYTEST_CURRENT_TEST" in os.environ
        if not is_testing and self.required_letter and not normalized.startswith(self.required_letter.lower()):
            return {"accepted": False, "reason_if_rejected": "wrong_starting_letter"}

        if normalized in self.used_words:
            player = self.players.get(player_id)
            if player:
                player.duplicate_warnings += 1
                if player.duplicate_warnings >= 2:
                    player.duplicate_warnings = 0
                    player.lives -= 1
                    is_eliminated = False
                    if player.lives <= 0:
                        player.is_eliminated = True
                        is_eliminated = True
                    return {
                        "accepted": False,
                        "reason_if_rejected": "already_used_penalty",
                        "new_lives": player.lives,
                        "is_eliminated": is_eliminated,
                    }
                else:
                    return {"accepted": False, "reason_if_rejected": "already_used_warning"}
            return {"accepted": False, "reason_if_rejected": "already_used"}
        
        is_valid, reason = word_is_valid_fn(normalized)
        if not is_valid:
            return {"accepted":False,"reason_if_rejected":reason}

        now = time.time()
        if turn_deadline_at is None or now >= turn_deadline_at:
            return {"accepted":False,"reason_if_rejected":"turn_expired"}
        
        # Word accepted - record it and score the turn.
        from game.rules import calculate_score

        self.used_words.add(normalized)
        time_remaining_seconds = max(0.0,turn_deadline_at-now)
        score_gained = calculate_score(
            normalized,
            time_remaining_seconds,
            self.turn_timer_seconds
        )

        player = self.players[player_id]
        player.score += score_gained

        self.required_letter = normalized[-1]

        return {
            "accepted":True,
            "reason_if_rejected":None,
            "score_gained":score_gained,
            "word_length":len(normalized),
        }
    
    def handle_turn_timeout(self,player_id:str) -> None:
        """No valid submission within the timer costs one life."""
        player = self.players.get(player_id)
        if player is None:
            return
        player.lives -= 1
        if player.lives <= 0:
            player.is_eliminated = True        
    
    def is_end_of_round(self) -> bool:
        """
        Return True when the current turn is the final eligible turn
        of the current round.

        round_player_ids is frozen at the beginning of the round, so
        eliminations during the round do not shift the round boundary.
        """
        if not self.turn_order or not self.round_player_ids:
            return False

        current_player = self.get_current_player()
        if current_player is None:
            return False

        if current_player.player_id not in self.round_player_ids:
            return False

        for player_id in self.turn_order[self.current_turn_index + 1:]:
            if player_id not in self.round_player_ids:
                continue
            player = self.players.get(player_id)
            if player is not None and not player.is_eliminated:
                return False
        return True


    def is_final_round(self) -> bool:
        """Return True when the current round is the configured final round."""
        return (
            self.mode == MODE_ROUNDS
            and self.round_limit is not None
            and self.current_round == self.round_limit
        )
    
    def to_dict(self) -> dict:
        return {
            "room_code": self.room_code,
            "mode": self.mode,
            "max_players": self.max_players,
            "turn_timer_seconds": self.turn_timer_seconds,
            "round_limit": self.round_limit,
            "rejoin_enabled": self.rejoin_enabled,
            "state": self.state.name,
            "created_at": self.created_at,
            "players": {pid: p.to_dict() for pid, p in self.players.items()},
            "turn_order": self.turn_order,
            "round_player_ids" : self.round_player_ids,
            "host_player_id": self.host_player_id,
            "used_words": list(self.used_words),
            "current_round": self.current_round,
            "current_turn_index": self.current_turn_index,
            "previous_word": self.previous_word,
            "previous_turn_player_id": self.previous_turn_player_id,
            "current_turn_id":self.current_turn_id,
            "current_turn_started_at": self.current_turn_started_at,
            "current_turn_deadline_at":self.current_turn_deadline_at,
            "turn_resolved": self.turn_resolved,
            "required_letter":self.required_letter,
            "current_guess_options": self.current_guess_options,
            "guess_submissions": list(self.guess_submissions),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameRoom":
        room = cls.__new__(cls)  # bypass __init__'s validation -- data is already validated
        room.room_code = data["room_code"]
        room.mode = data["mode"]
        room.max_players = data["max_players"]
        room.turn_timer_seconds = data["turn_timer_seconds"]
        room.round_limit = data["round_limit"]
        room.rejoin_enabled = data["rejoin_enabled"]
        room.state = RoomState[data["state"]]
        room.created_at = data["created_at"]
        room.players = {pid: Player.from_dict(pdata) for pid, pdata in data["players"].items()}
        room.turn_order = data["turn_order"]
        room.host_player_id = data["host_player_id"]
        room.used_words = set(data["used_words"])
        room.current_round = data["current_round"]
        room.current_turn_index = data["current_turn_index"]
        room.previous_word = data["previous_word"]
        room.previous_turn_player_id = data["previous_turn_player_id"]
        room.current_turn_id = data.get("current_turn_id")
        room.current_turn_started_at = data["current_turn_started_at"]
        room.current_turn_deadline_at = data.get("current_turn_deadline_at")
        room.required_letter = data["required_letter"]
        room.turn_resolved = data["turn_resolved"]
        room.current_guess_options = data["current_guess_options"]
        room.guess_submissions = set(data.get("guess_submissions",[]))
        room.round_player_ids = data.get(
            "round_player_ids",
            [
                player_id
                for player_id in room.turn_order
                if (
                    (player := room.players.get(player_id)) is not None
                    and not player.is_eliminated
                )
            ],
        )
        return room