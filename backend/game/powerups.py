"""
Powerup logic: skip, steal, double-score. Pure Python — no sockets.
Each function mutates player state and returns a result dict the socket
handler layer will turn into the matching CONTRACT.md event.
"""
from config import STEAL_REJECT_PENALTY_POINTS


def use_skip(player) -> dict:
    """
    Rule: skips the player's turn, and cancels the guessing phase for
    everyone that turn (that part is the socket handler's job — it just
    needs to know a skip happened and suppress guess_options for this turn).
    No score/life effect on the skipper.
    """
    if not player.has_skip:
        return {"success": False, "reason": "already_used"}

    player.has_skip = False
    return {"success": True}


def use_double_score(player) -> dict:
    """
    Instantly doubles the player's current total score and consumes the
    powerup. No "next submission" delay — the effect is immediate.
    """
    if not player.has_double_score:
        return {"success": False, "reason": "not_available"}

    player.has_double_score = False
    player.score *= 2
    return {"success": True, "new_score": player.score}


def initiate_steal(challenger, target) -> dict:
    """
    Called the instant a player uses their steal powerup. Consumed
    immediately regardless of what happens next (accept/reject/win/lose) —
    per the locked decision, there's no scenario where a player gets it back.
    """
    if not challenger.has_steal:
        return {"success": False, "reason": "already_used"}
    if target.is_eliminated:
        return {"success": False, "reason": "invalid_target"}

    challenger.has_steal = False
    return {"success": True}


def reject_steal(target) -> dict:
    """
    Target rejects the challenge. Rejecting a steal challenge reduces player score by 75 points.
    Returns a dict matching the parts of CONTRACT.md's StealRejected payload.
    """
    penalty_applied = True
    target.steal_reject_used += 1

    points_lost = STEAL_REJECT_PENALTY_POINTS
    target.score = max(0, target.score - STEAL_REJECT_PENALTY_POINTS)

    return {
        "penalty_applied": penalty_applied,
        "points_lost": points_lost,
    }


def resolve_steal_challenge(challenger, target, challenger_won: bool) -> dict:
    """
    Called once the challenge minigame result is known (server-verified,
    per the locked design — no manual verification, like skip in UNO).
    Winner takes one life from loser. Note the confirmed reversal: if the
    TARGET wins, they take a life from the CHALLENGER, not the other way
    around from what "steal" might suggest.
    """
    if challenger_won:
        winner, loser = challenger, target
    else:
        winner, loser = target, challenger

    life_transferred = loser.lives > 0
    if life_transferred:
        loser.lives -= 1
        winner.lives += 1
        if loser.lives <= 0:
            loser.is_eliminated = True

    return {
        "winner_id": winner.player_id,
        "loser_id": loser.player_id,
        "life_transferred": life_transferred,
    }