"""
Scoring and word-submission rules. Pure Python — no Flask, no sockets, no
network calls. Dictionary/profanity checking is injected as a callable
(see submit_word's word_is_valid_fn param) so this file never has to know
HOW words get validated, just what to do with the result.
"""

import math
from config import SCORE_PER_LETTER, MAX_TIME_BONUS

def calculate_score(word:str,time_remaining_seconds:float,total_turn_seconds:float) -> int:
    """
    Matches CONTRACT.md Section 4 exactly:
    score = (word_length * 10) + time_bonus
    time_bonus = floor((time_remaining / total_time) * 50)
    """

    if total_turn_seconds <= 0:
        time_bonus = 0
    else:
        ratio = max(0.0,min(1.0,time_remaining_seconds / total_turn_seconds))
        time_bonus = math.floor(ratio * MAX_TIME_BONUS)
    return (len(word) * SCORE_PER_LETTER + time_bonus)

def check_win_condition(room) -> dict | None:
    """
    Checks both room modes' win conditions against the given GameRoom. Returns a dict matching CONTRACT.md's GameEnded payload if the game should end now, or None if play continues.
    Takes the GameRoom object directly (not individual fields) since this needs multiple pieces of room state together — kept in rules.py rather than as a GameRoom method to keep win-condition logic in one place, separate from state management.
    """
    active = room.active_players

    # Both modes: game ends the instant only one player remains.
    if len(active) == 1:
        return {
            "winner_id_or_ids": [active[0].player_id],
            "reason": "last_standing",
            "final_scores": _final_scores(room),
        }

    # Edge case: two or more players hit zero lives in the same round,
    # leaving zero active players simultaneously. Tiebreak by score.
    if len(active) == 0:
        return {
            "winner_id_or_ids": _highest_score_ids(room),
            "reason": "last_standing",
            "final_scores": _final_scores(room),
        }

    # Rounds mode only: game ends when the round limit is reached,
    # regardless of how many players are still active.
    if room.is_round_limit_reached():
        return {
            "winner_id_or_ids": _highest_score_ids(room),
            "reason": "round_limit",
            "final_scores": _final_scores(room),
        }

    return None  # game continues


def _final_scores(room) -> list[dict]:
    return [
        {"player_id": p.player_id, "name": p.name, "score": p.score}
        for p in room.players.values()
    ]

def process_guess(player, correct: bool) -> dict:
    """
    Updates streaks per rules 15, 16, 29, 30. Returns a dict with the parts
    of CONTRACT.md's GuessResult that depend on game state (caller already
    knows `correct` since it's the one comparing the guess to the answer).
    """
    from config import (
        CORRECT_STREAK_FOR_DOUBLE_POWERUP,
        WRONG_STREAK_PENALTY_THRESHOLD,
        WRONG_STREAK_PENALTY_POINTS,
    )

    points_delta = 0

    if correct:
        player.wrong_guess_streak = 0  # rule 30: only a correct guess resets it

        if not player.double_score_earned:
            player.correct_guess_streak += 1
            if player.correct_guess_streak >= CORRECT_STREAK_FOR_DOUBLE_POWERUP:
                player.has_double_score = True
                player.double_score_earned = True
                player.correct_guess_streak = 0  # rule 29: stops tracking after earned
    else:
        player.correct_guess_streak = 0  # any wrong guess breaks it

        player.wrong_guess_streak += 1
        if player.wrong_guess_streak % WRONG_STREAK_PENALTY_THRESHOLD == 0:
            player.score -= WRONG_STREAK_PENALTY_POINTS
            points_delta = -WRONG_STREAK_PENALTY_POINTS
            # streak is NOT reset here — rule 30 says only a correct guess resets it

    return {
        "streak_count": player.correct_guess_streak,
        "points_delta": points_delta,
    }

def request_rejoin(room, player) -> dict:
    """
    Rule 24: max 1 rejoin ever per player. Rejoin is rounds-mode only —
    caller (socket handler) should already be enforcing that via
    room.rejoin_enabled before this is even called, but we check again
    here since game/ should never trust its caller blindly.
    """
    if not room.rejoin_enabled:
        return {"success": False, "reason": "rejoin_disabled"}
    if not player.is_eliminated:
        return {"success": False, "reason": "not_eliminated"}
    if not player.can_rejoin():
        return {"success": False, "reason": "rejoin_limit_reached"}

    return {"success": True}


def tally_rejoin_vote(votes: dict[str, bool], eligible_voter_count: int) -> bool:
    """
    Rule 27: majority, not unanimous. votes is {player_id: bool}, already
    guaranteed one-vote-per-player by the socket layer (CONTRACT.md
    Section 7, point about enforcing one vote per player).
    Ties (exactly 50%) count as rejected — majority means MORE than half.
    """
    from config import MAJORITY_VOTE_THRESHOLD

    if eligible_voter_count == 0:
        return False

    yes_votes = sum(1 for v in votes.values() if v)
    return (yes_votes / eligible_voter_count) > MAJORITY_VOTE_THRESHOLD


def apply_rejoin(player) -> int:
    """
    Rule 24: score halved on rejoin, floors at 0. Also resets elimination
    status and grants 1 life (instead of 3 lives), un-eliminating the player.
    Returns the new score, matching CONTRACT.md's RejoinResult.new_score_if_approved.
    """
    from config import REJOIN_SCORE_PENALTY_MULTIPLIER
    from game.enums import PlayerConnectionState
    player.score = max(0, int(player.score * REJOIN_SCORE_PENALTY_MULTIPLIER))
    player.is_eliminated = False
    player.lives = 1
    player.rejoins_used += 1
    player.connection_state = PlayerConnectionState.CONNECTED

    return player.score

def _highest_score_ids(room) -> list[str]:
    """Handles ties — multiple ids returned means joint-first, per CONTRACT.md."""
    all_players = list(room.players.values())
    if not all_players:
        return []
    top_score = max(p.score for p in all_players)
    return [p.player_id for p in all_players if p.score == top_score]