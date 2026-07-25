"""
Steal challenge minigames. Pure Python — no sockets, no timing side effects.
Each generator produces the prompt data both players need; each resolver
decides a winner from submitted data. The socket layer (challenge_handlers.py)
owns all timing/network plumbing — this file only knows game rules.
"""

import random

class ActiveChallenge:
    """
    Tracks one in-progress steal challenge between two players. Lives in memory on the socket layer, not on GameRoom - a challenge is a short-lived side-activity, not core turn-based game state.
    """

    def __init__(self,challenge_type:str,challenger_id:str,target_id:str,room_code:str):
        self.challenge_type = challenge_type
        self.challenger_id = challenger_id
        self.target_id = target_id
        self.room_code = room_code
        self.prompt_data: dict = {}
        self.go_at: float | None = None
        self.submissions: dict[str,dict] = {}
        self.resolved = False
        self.answer: str | None = None

    def to_dict(self) -> dict:
        return {
            "challenge_type": self.challenge_type,
            "challenger_id": self.challenger_id,
            "target_id": self.target_id,
            "room_code": self.room_code,
            "prompt_data": self.prompt_data,
            "go_at": self.go_at,
            "submissions": self.submissions,
            "resolved": self.resolved,
            "answer": self.answer,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActiveChallenge":
        challenge = cls(
            challenge_type=data["challenge_type"],
            challenger_id=data["challenger_id"],
            target_id=data["target_id"],
            room_code=data["room_code"],
        )
        challenge.prompt_data = data["prompt_data"]
        challenge.go_at = data["go_at"]
        challenge.submissions = data["submissions"]
        challenge.resolved = data["resolved"]
        challenge.answer = data["answer"]
        return challenge
    
def generate_reaction_race() -> tuple[dict,float]:
    """
    Returns (prompt_data_for_clients, delay_seconds_before_go).
    Random 2-5s delay prevents players from just timing a fixed interval instead of genuinely reacting.
    """

    delay = random.uniform(2.0,5.0)
    return {}, delay

def _other_player(challenge: "ActiveChallenge", submitter_id: str) -> str:
    return challenge.target_id if submitter_id == challenge.challenger_id else challenge.challenger_id


def check_reaction_race_win(challenge: "ActiveChallenge", received_at: float) -> bool:
    return challenge.go_at is not None and received_at >= challenge.go_at

def generate_unscramble() -> tuple[dict, str]:
    """
    Picks a random real word from the local wordlist and scrambles its
    letters. Returns (prompt_data_for_clients, correct_answer) — the
    answer is server-side only, never included in prompt_data.
    """
    from game.validation import get_wordlist

    # Restrict to a reasonable length range so the challenge is actually
    # solvable in a real-time race, not a 12-letter word nobody can unscramble fast.
    candidates = [w for w in get_wordlist() if 4 <= len(w) <= 8]
    word = random.choice(candidates)

    letters = list(word)
    scrambled = word
    while scrambled == word:   # guard against the shuffle landing back on the original
        random.shuffle(letters)
        scrambled = "".join(letters)

    return {"scrambled": scrambled}, word


def check_unscramble_win(challenge: "ActiveChallenge", value) -> bool:
    return isinstance(value, str) and value.strip().lower() == challenge.answer


def generate_fastest_word() -> tuple[dict, str]:
    """
    Picks a random starting letter. Returns (prompt_data_for_clients, letter).
    Letter is also stored in prompt_data since, unlike unscramble's answer,
    there's nothing secret about it — both players need to see it to play.
    """
    import string
    letter = random.choice(string.ascii_lowercase)
    return {"starting_letter": letter}, letter


def check_fastest_word_win(challenge: "ActiveChallenge", value) -> bool:
    from game.validation import validate_word

    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    letter = challenge.prompt_data["starting_letter"]
    if not normalized.startswith(letter):
        return False
    is_valid, _reason = validate_word(normalized)
    return is_valid

def generate_math_flash() -> tuple[dict, int]:
    """
    Simple single-operation arithmetic problem. Kept intentionally easy —
    the challenge is about speed, not difficulty, so a hard problem would
    just make it a math test instead of a race.
    Returns (prompt_data_for_clients, correct_answer).
    """
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    operation = random.choice(["+", "-", "*"])

    if operation == "+":
        answer = a + b
    elif operation == "-":
        answer = a - b
    else:
        answer = a * b

    return {"expression": f"{a} {operation} {b}"}, answer


def check_math_flash_win(challenge: "ActiveChallenge", value) -> bool:
    try:
        return int(value) == challenge.answer
    except (TypeError, ValueError):
        return False
