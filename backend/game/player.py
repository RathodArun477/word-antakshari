"""
Player state. Pure Python - no Flask, no socket, no network imports.
This must stay fully testable by just instantiating a Player and calling methods on it, with zero server running.
"""

import uuid
from dataclasses import dataclass, field
from game.enums import PlayerConnectionState
from config import STARTING_LIVES, MAX_REJOINS_PER_PLAYER


@dataclass
class Player:
    name:str
    session_token:str = field(default_factory=lambda:str(uuid.uuid4()))
    player_id:str = field(default_factory=lambda:str(uuid.uuid4()))

    lives: int = STARTING_LIVES
    score:int = 0

    connection_state: PlayerConnectionState = PlayerConnectionState.CONNECTED
    is_eliminated: bool = False

    # Powerups - one-time use each. Flags track whether still available.
    has_skip: bool = True
    has_steal:bool = True
    has_double_score:bool = False # Earned via 5 - guess streak, not held from the start

    # Guessing phase 
    correct_guess_streak:int = 0
    wrong_guess_streak:int = 0
    double_score_earned:bool = False # Once earned, streak tracking for it stops
    double_score_active:bool = False

    # Rejoin (round mode only)
    rejoins_used:int = 0

    # Steal reject penalty (locked decision: 2 free rejects, then -75 each after)
    steal_reject_used:int = 0
    duplicate_warnings:int = 0

    def can_rejoin(self) -> bool:
        return self.rejoins_used < MAX_REJOINS_PER_PLAYER
    
    def can_reject_steal_free(self) -> bool:
        return self.steal_reject_used < 2
    
    def to_public_dict(self, is_host: bool = False) -> dict:
        """
        Shape matches CONTRACT.md's PublicPlayerInfo - safe to send to every player in the room. Never include session_token or anything else private here.
        """

        return {
            "player_id": self.player_id,
            "name": self.name,
            "lives": self.lives,
            "score": self.score,
            "is_eliminated": self.is_eliminated,
            "is_host": is_host,
            "correct_guess_streak": self.correct_guess_streak,
        }
    
    def to_private_dict(self) -> dict:
        """
        Shape matches CONTRACT.md's PlayerStateSnapshot - only ever sent to this specific player (e.g. on reconnect), never broadcast.
        """

        return {
            "player_id":self.player_id,
            "session_token":self.session_token,
            "lives":self.lives,
            "score":self.score,
            "has_skip":self.has_skip,
            "has_steal":self.has_steal,
            "has_double_score":self.has_double_score,
            "rejoins_used":self.rejoins_used,
            "correct_guess_streak":self.correct_guess_streak,
        }
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "session_token":self.session_token,
            "player_id":self.player_id,
            "lives":self.lives,
            "score":self.score,
            "connection_state":self.connection_state.name,
            "is_eliminated":self.is_eliminated,
            "has_skip":self.has_skip,
            "has_steal":self.has_steal,
            "has_double_score":self.has_double_score,
            "double_score_active":self.double_score_active,
            "correct_guess_streak":self.correct_guess_streak,
            "wrong_guess_streak":self.wrong_guess_streak,
            "double_score_earned":self.double_score_earned,
            "rejoins_used":self.rejoins_used,
            "steal_reject_used":self.steal_reject_used,
            "duplicate_warnings":self.duplicate_warnings,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Player":
        from game.enums import PlayerConnectionState
        player = cls(name=data["name"])
        player.session_token = data["session_token"]
        player.player_id = data["player_id"]
        player.lives = data["lives"]
        player.score = data["score"]
        player.connection_state = PlayerConnectionState[data["connection_state"]]
        player.is_eliminated = data["is_eliminated"]
        player.has_skip = data["has_skip"]
        player.has_steal = data["has_steal"]
        player.has_double_score = data["has_double_score"]
        player.double_score_active = data["double_score_active"]
        player.correct_guess_streak = data["correct_guess_streak"]
        player.wrong_guess_streak = data["wrong_guess_streak"]
        player.double_score_earned = data["double_score_earned"]
        player.rejoins_used = data["rejoins_used"]
        player.steal_reject_used = data["steal_reject_used"]
        player.duplicate_warnings = data.get("duplicate_warnings", 0)
        return player