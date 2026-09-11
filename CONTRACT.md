# Word Antakshari — Backend ↔ Frontend Contract

**Status:** Living document — update alongside code changes, not just at the end.
If backend and frontend disagree, this file wins and whichever side is wrong
gets fixed.

---

## 1. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Backend framework | Flask + Flask-SocketIO | `async_mode="threading"` (NOT eventlet — see Section 9) |
| Shared state | Redis | room state, reconnect tokens, message queue for multi-worker scaling |
| Word validation (primary) | `english-words` package (`web2` set) | in-memory `set()`, O(1) lookup, no network call, ~230k+ words |
| Decoy generation | NLTK WordNet | offline synonym/related-word lookup, same-starting-letter preferred (see 5.3) |
| Profanity filter | `better-profanity` | local, fast, handles common obfuscation |
| Word validation (fallback) | Gemini API (`google-genai` SDK, model `gemini-3.5-flash`) | only for words not found locally — rare-word edge cases |
| Backend language | Python 3 | entry point is `run.py`, NOT `app.py` — see Section 9 |
| Frontend | TypeScript + Vite (+ Socket.IO client) | no framework |
| Deployment | TBD | decided after the project is functionally complete |

Target scale: ~1000 concurrent players. Redis is required infrastructure at
this scale, not optional.

---

## 2. Core Game Rules (reference summary)

- 2–8 players per room. Host sets the per-word turn timer.
- **Letter chaining (Antakshari mechanic):** the first turn of the game gets a
  random starting letter from the server. Every word must start with the
  currently required letter. Once a word is accepted, the required letter
  becomes that word's **last letter** for the next player. If a turn is
  skipped, the server rerolls a fresh random letter. If a turn times out
  with no word submitted, the required letter carries over unchanged to the
  next player.
- Words: minimum 4 letters, no max. Must start with the required letter, be
  validated as a real word, not previously used in this game (by anyone),
  and free of banned language.
- Score = `word_length * 10 + time_bonus` (see Section 4).
- 3 lives per player. Timing out on a turn costs 1 life.
- Disconnects get a 10–15s grace period to reconnect before being kicked.
- Guessing phase activates dynamically whenever 3+ players are still active.
  Everyone except the current turn player and the previous turn player gets
  5 word options (1 real, 4 decoys) to guess what the previous player typed.
  - 5-correct streak → one-time double-score powerup (streak resets after
    earning it — no further streak tracking for that player after that).
  - 3-wrong streak → -50 points, resets to 0 only on the next correct guess
    (does NOT reset just because the -50 penalty fired).
  - No guess = neutral, no points, no streak effect either direction.
- The word a player types is **never revealed** to anyone else, at any point.
  Other players only ever learn "your guess was correct" or "wrong."

---

## 3. Room Modes

| Mode | Round limit | Rejoin | Win condition |
|---|---|---|---|
| `endless` | None — plays until 1 player remains | Disabled | Last player standing. Simultaneous final elimination → highest score wins. |
| `rounds` | Host-configurable, 3–12 rounds (1 round = every active player gets one turn — full cycle) | Enabled | Ends early if only 1 player remains before the round limit. Otherwise highest score at the final round wins; ties shown as joint-first. |

Rejoin (rounds mode only): eliminated player requests rejoin → majority vote
(not unanimous) among active players, 15s timeout → if approved, player
returns with score halved (floors at 0) and lives reset to full. Maximum 1
rejoin ever, per player, per game.

---

## 4. Scoring Formula

```
score_gained = (word_length * 10) + time_bonus
time_bonus   = floor((time_remaining_seconds / total_turn_seconds) * 50)
```

Server's calculation is always authoritative; frontend's version (if shown
live) is display-only and never trusted for the real score.

**Double-score powerup** is a separate, instant effect — see Section 5.4. It
is NOT part of this formula; it doubles the player's *total* score at the
moment it's activated, not any individual word's score.

---

## 5. Event Contract

Conventions:
- `C→S` = client sends to server. `S→C` = server sends to one specific client
  (always via `to=request.sid` or `socketio.emit(..., to=sid)` — never a bare
  `emit()` from inside a background task, see Section 9).
  `S→Room` = server broadcasts to everyone in the room. `S→target` = server
  sends to one specific non-requesting client.
- All timestamps are **Unix epoch milliseconds** (`number`).
- `session_token` and `room_code` are opaque strings.

### 5.1 Connection & Room Lifecycle

```typescript
export interface CreateRoom {
  host_name: string;
  mode: "endless" | "rounds";
  max_players: number;       // 2-8, validated server-side regardless of client value
  turn_timer_seconds: number;
  round_limit?: number;      // REQUIRED when mode is "rounds", 3-12. No default —
                              // server rejects with INVALID_ROOM_CONFIG if missing/out of range.
}

export interface RoomCreated {
  room_code: string;         // 6-char unguessable alphanumeric, collision-checked against Redis
  room_state: "waiting";
}

export interface JoinRoom {
  room_code: string;
  player_name: string;
}

export interface PlayerJoined {
  player_id: string;
  player_name: string;
  current_player_count: number;
  // NOTE: does not carry lives/score/is_eliminated. Frontend currently
  // patches this in manually assuming defaults (3 lives, 0 score,
  // not eliminated) — a real gap, worth eventually having the backend
  // send full PublicPlayerInfo here instead.
}

export interface Reconnect {
  room_code: string;
  session_token: string;
}

export interface ReconnectSuccess {
  room_state: RoomStateSnapshot;
  player_state: PlayerStateSnapshot;
}
// `create_room` and `join_room` are each ALSO followed by a private
// reconnect_success event to the acting player (reusing this same shape),
// giving them full state immediately on entry rather than a separate fetch.
// If reconnecting mid-game (room_state.state === "in_progress"), frontend
// should route straight to the game board and restore turn state from the
// new fields on RoomStateSnapshot (see 5.7), not the lobby.

export interface PlayerDisconnected {
  player_id: string;
  grace_period_ends_at: number;
}

export interface PlayerKicked {
  player_id: string;
  reason: "grace_period_expired";
}
```

### 5.2 Lobby

```typescript
export interface StartGame {}  // no payload

export interface GameStarted {
  turn_order: string[];
  round_limit: number | null;  // null for endless, 3-12 for rounds
  first_player_id: string;
}
```

### 5.3 Turn Flow

```typescript
export interface TurnStart {
  player_id: string;
  server_timestamp: number;
  duration_seconds: number;
  round_number: number;
  required_letter: string;   // the letter the submitted word must start with
}

export interface WordSubmit {
  word: string;
}

export type WordRejectReason =
  | "too_short"
  | "already_used"
  | "not_a_word"
  | "profanity"
  | "out_of_turn"
  | "invalid_phase"
  | "not_authorized"
  | "wrong_starting_letter";

export interface WordResult {
  accepted: boolean;
  reason_if_rejected?: WordRejectReason;
  score_gained?: number;
  word_length?: number;
}

export interface TurnResolved {
  player_id: string;
  word_length: number;
  score_gained: number;
  new_total_score: number;
  new_lives: number;
}
// Word itself is NEVER included, for any reason, ever.

export interface PlayerEliminated {
  player_id: string;
  reason: "timeout" | "steal_lost";
}

// S→Room. Fires whenever ANY player's life count changes, for ANY reason
// (timeout or lost steal challenge). This is the one authoritative signal
// the frontend should use to update lives on screen — do not infer life
// changes from other events.
export interface LifeLost {
  player_id: string;
  new_lives: number;
  reason: "timeout" | "steal_lost";
}
```

### 5.4 Guessing Phase (targeted — never room-wide)

```typescript
export interface GuessOptions {
  options: string[];      // exactly 5, real word + 4 decoys, order randomized
  expires_at: number;
}

export interface GuessSubmit {
  guess_index: number;    // 0-4
}

export interface GuessResult {
  correct: boolean;
  streak_count: number;
  points_delta: number;
}
```

Decoy generation priority (highest to lowest):
1. Synonym, same starting letter as the real word, within length range
2. Synonym, any starting letter, within length range
3. Any wordlist word, same starting letter, within length range
4. Any wordlist word, any starting letter, within length range
5. Any wordlist word, same starting letter, any length
6. Any wordlist word at all (final fallback, rule 23's own stated default)

Guess popups should be closed by the frontend whenever a new `turn_start`
fires, regardless of whether the player is eligible for the new turn's
guess — prevents a stale popup lingering when a player becomes ineligible
(e.g. becomes the current or previous turn player).

### 5.5 Powerups

```typescript
export interface UseSkip {}  // implicit: acting player is the current turn player

export interface SkipUsed {
  player_id: string;
}

export interface UseDoubleScore {}  // no payload

// S→Room. Score doubling is INSTANT on activation — not "applies to your
// next word." Consumed the moment it's used, regardless of whose turn it is.
export interface DoubleScoreActivated {
  player_id: string;
  new_total_score: number;
}

export interface UseSteal {
  target_player_id: string;
}

export type StealChallengeType =
  | "fastest_word"
  | "unscramble"
  | "longest_word_sprint"   // NOT IMPLEMENTED server-side — never offer this in UI
  | "reaction_race"
  | "math_flash";

export interface StealChallengeOffer {
  challenger_id: string;
  available_challenges: StealChallengeType[];
}

export interface StealChallengeResponse {
  accept: boolean;
  challenge_type_if_accepted?: StealChallengeType;
}

export interface StealChallengeResult {
  winner_id: string;
  loser_id: string;
  life_transferred: boolean;
}
// Followed by a life_lost event for the loser (see 5.3) if life_transferred
// is true. Winner's life gain is reflected via the room's next full
// re-render — frontend currently patches winner.lives += 1 locally on
// receipt of this event.

export interface StealRejected {
  challenger_id: string;
  rejecter_id: string;
  penalty_applied: boolean;  // false for the rejecter's first 2 rejects this game
  points_lost: number;       // 0 or 75
}
```

`use_steal` consumes the powerup immediately regardless of accept, reject,
win, or lose.

**Steal challenge resolution (important behavior):** this is NOT
"first submission wins, right or wrong." A wrong or invalid submission is
silently ignored — no penalty, challenge stays open. The challenge only
resolves the moment someone submits something genuinely correct (from
either player, checked individually on every submission). A timeout with
no correct submission from either side defaults to the target winning.

### 5.6 Steal Challenge Minigame Flow

```typescript
export interface ReactionRacePrompt {}
export interface UnscramblePrompt { scrambled: string; }
export interface FastestWordPrompt { starting_letter: string; }
export interface MathFlashPrompt { expression: string; }  // e.g. "5 + 3"

export type ChallengePromptData =
  | ReactionRacePrompt | UnscramblePrompt | FastestWordPrompt | MathFlashPrompt;

export interface ChallengeStart {
  challenge_type: StealChallengeType;
  prompt_data: ChallengePromptData;
}

// S→both. reaction_race only — other challenge types start immediately on
// challenge_start with no separate go signal.
export interface ChallengeGo {}

export interface ChallengeSubmit {
  value: string | number;
  // string for unscramble/fastest_word, number for math_flash,
  // reaction_race sends a placeholder value — server times receipt.
}
```

### 5.7 Rejoin (rounds mode only)

```typescript
export interface RejoinRequest {}  // no payload

export interface RejoinVoteStart {
  requesting_player_id: string;
  expires_at: number;
}

export interface RejoinVoteCast {
  vote: boolean;
}

export interface RejoinResult {
  player_id: string;
  approved: boolean;
  new_score_if_approved?: number;
}
```
**Known issue:** rejoin flow is currently confirmed broken in testing —
specific failure point not yet isolated. See `PROJECT_STATUS.md`.

### 5.8 Game End

```typescript
export interface GameEnded {
  winner_id_or_ids: string[];
  reason: "last_standing" | "round_limit";
  final_scores: { player_id: string; score: number }[];
}
```

### 5.9 Shared Types

```typescript
export interface RoomStateSnapshot {
  room_code: string;
  mode: "endless" | "rounds";
  state: "waiting" | "in_progress" | "finished";
  players: PublicPlayerInfo[];
  current_round: number | null;
  current_turn_player_id: string | null;   // for reconnect-state restoration
  required_letter: string | null;           // for reconnect-state restoration
  turn_started_at: number | null;           // epoch ms, for reconnect-state restoration
  turn_duration_seconds: number;            // for reconnect-state restoration
}

export interface PublicPlayerInfo {
  player_id: string;
  name: string;
  lives: number;
  score: number;
  is_eliminated: boolean;
}

export interface PlayerStateSnapshot {
  player_id: string;
  session_token: string;
  lives: number;
  score: number;
  has_skip: boolean;
  has_steal: boolean;
  has_double_score: boolean;
  rejoins_used: number;
}
```

### 5.10 Errors

```typescript
export type ErrorCode =
  | "OUT_OF_TURN"
  | "INVALID_WORD"
  | "RATE_LIMITED"
  | "INVALID_PHASE"
  | "NOT_AUTHORIZED"
  | "ROOM_FULL"
  | "ROOM_NOT_FOUND"
  | "INVALID_ROOM_CONFIG";

export interface ErrorEvent {
  code: ErrorCode;
  message: string;
}
```

---

## 6. Optimization Principles

1. **No per-second tick events.** `turn_start` is sent once with a server
   timestamp + duration; every client computes its own local countdown.
2. **Targeted emits, not broadcast-and-filter.** Guessing options, word
   results, and guess results go only to the specific socket(s) that should
   receive them.
3. **Delta updates, not full re-serialization** where practical.
4. **Ack callbacks on `word_submit`** for reliable client-side confirmation.
5. **Redis caching for word validation** — validated words aren't
   re-checked against the local wordlist/Gemini repeatedly.

---

## 7. Security Notes

1. Server is the only source of truth for score, lives, timing, word validity.
2. Never render another player's in-progress or submitted word.
3. `session_token` is sensitive — treat like a credential.
4. Server silently drops events sent out of turn or out of phase.
5. Rate limiting is enforced server-side on the highest-traffic events
   (`create_room`, `join_room`, `word_submit`, `guess_submit`, `challenge_submit`).
6. Room codes are unguessable (6-char random alphanumeric, collision-checked).
7. Profanity filtering applies to word submissions server-side, regardless
   of any client-side pre-check.

---

## 8. Change Process

1. Propose the change first — what event, what's changing, why.
2. Update this file in the same commit/PR as the code change.
3. Backend and frontend implementations should both reference this file's
   current version, not memory of an earlier conversation.

---

## 9. Critical Operational Notes

- **Always start the backend with `python run.py`, never `python app.py`
  directly.** Running `app.py` directly causes Python to import it twice
  under different module names, creating two separate `SocketIO` instances
  — the real running server ends up with zero registered event handlers,
  and every socket event silently does nothing with no visible error.
- **`async_mode` is `"threading"`, not `"eventlet"`.** Eventlet caused
  unexplained silent hangs on real (non-test-client) connections during
  development; threading mode resolved it. If ever reconsidering eventlet,
  be aware background-task code must call `socketio.emit(...)` (never the
  bare `emit()` from `flask_socketio`) since background tasks under
  threading mode have no Flask request context — `emit()` alone will
  raise `RuntimeError: Working outside of request context`.
- **`socketio.emit()` broadcasts to everyone if no target is specified.**
  Any response meant for a single client (not the whole room) must pass
  `to=request.sid` explicitly — omitting it was a real bug that caused
  every connected client to receive events meant for only one player.
