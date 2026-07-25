"""
Central constants for the game. Nothing here talks to Flask, sockets, or
any external API — pure numbers/config so both game logic and (later)
frontend-facing docs can reference a single source of truth.
"""

# --- Room / player limits ---
MIN_PLAYERS = 2
MAX_PLAYERS = 8

# --- Lives / words ---
STARTING_LIVES = 3
MIN_WORD_LENGTH = 4

# --- Scoring ---
SCORE_PER_LETTER = 10          # rule 3: length * 10
MAX_TIME_BONUS = 50            # bonus scales down to 0 as time runs out

# --- Guessing phase (rule 14-17, 29-30) ---
GUESS_OPTIONS_COUNT = 5        # 1 correct + 4 decoys
CORRECT_STREAK_FOR_DOUBLE_POWERUP = 5
WRONG_STREAK_PENALTY_THRESHOLD = 3
WRONG_STREAK_PENALTY_POINTS = 50
DECOY_LENGTH_OFFSET = 2        # rule 23: decoy length = guessed word len +/- 2

# --- Disconnect / reconnect (rule 9) ---
RECONNECT_GRACE_SECONDS = 15   # upper bound of the 10-15s window

# --- Rejoin (rule 11, 24 — ROUNDS mode only) ---
MAJORITY_VOTE_THRESHOLD = 0.5  # rule 27: majority, not unanimous
REJOIN_VOTE_TIMEOUT_SECONDS = 15
REJOIN_SCORE_PENALTY_MULTIPLIER = 0.5  # rule 24: score halved on rejoin
MAX_REJOINS_PER_PLAYER = 1     # rule 24: only ever once

# --- Steal challenge (locked decision) ---
STEAL_FREE_REJECTS = 0
STEAL_REJECT_PENALTY_POINTS = 75

# --- Room modes ---
MODE_ENDLESS = "endless"       # no round cap, no rejoin
MODE_ROUNDS = "rounds"         # host-set round cap (3-12), rejoin enabled
ROUNDS_MODE_MIN_LIMIT = 3
ROUNDS_MODE_MAX_LIMIT = 12

# --- Guessing phase minimum active players ---
MIN_PLAYERS_FOR_GUESS_PHASE = 3  # rule 13, dynamic per rule 26