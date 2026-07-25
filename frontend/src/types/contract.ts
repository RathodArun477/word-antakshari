// ============================================================
// Word Antakshari — Backend/Frontend Contract Types
// Mirrored 1:1 from CONTRACT.md. Any change to CONTRACT.md
// requires a matching update here in the same PR.
// ============================================================

// --- Shared / room state ---

export type RoomMode = "endless" | "rounds";
export type RoomState = "waiting" | "in_progress" | "finished";

export interface PublicPlayerInfo {
  player_id: string;
  name: string;
  lives: number;
  score: number;
  is_eliminated: boolean;
  is_host: boolean;
  correct_guess_streak: number;
}

export interface RoomStateSnapshot {
  room_code: string;
  mode: RoomMode;
  state: RoomState;
  players: PublicPlayerInfo[];
  current_round: number | null;
  turn_timer_seconds: number;
  round_limit: number | null;
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
  correct_guess_streak: number;
}

// --- Connection & room lifecycle ---

export interface CreateRoom {
  host_name: string;
  mode: RoomMode;
  max_players: number;
  turn_timer_seconds: number;
  round_limit?: number; // REQUIRED when mode is "rounds", 3-12. No default.
}

export interface RoomCreated {
  room_code: string;
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
  player: PublicPlayerInfo;
}

export interface Reconnect {
  room_code: string;
  session_token: string;
}

export interface ReconnectSuccess {
  room_state: RoomStateSnapshot;
  player_state: PlayerStateSnapshot;
}
// Note: create_room and join_room are each followed by a private
// reconnect_success event to the acting player, reusing this same shape,
// giving them full state immediately on entry.

export interface PlayerDisconnected {
  player_id: string;
  grace_period_ends_at: number; // epoch ms
}

export interface PlayerKicked {
  player_id: string;
  reason: "grace_period_expired";
}

// --- Lobby ---

export interface StartGame {} // no payload needed

export interface GameStarted {
  turn_order: string[];
  round_limit: number | null; // null for endless, 3-12 for rounds
  first_player_id: string;
}

// --- Turn flow ---

export interface TurnStart {
  player_id: string;
  server_timestamp: number; // epoch ms
  duration_seconds: number;
  round_number: number;
}

export interface WordSubmit {
  word: string;
}

export type WordRejectReason =
  | "too_short"
  | "already_used"
  | "already_used_warning"
  | "already_used_penalty"
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

export interface PlayerEliminated {
  player_id: string;
  reason: "timeout" | "steal_lost";
}

// --- Guessing phase ---

export interface GuessOptions {
  options: string[]; // exactly 5
  expires_at: number; // epoch ms
}

export interface GuessSubmit {
  guess_index: number; // 0-4
}

export interface GuessResult {
  correct: boolean;
  streak_count: number;
  points_delta: number;
}

// --- Powerups ---

export interface UseSkip {}

export interface SkipUsed {
  player_id: string;
}

export interface UseDoubleScore {}
// Note: activating this does not double anything immediately. It flags
// the powerup active for the player's NEXT word submission — the doubled
// score only appears in that submission's turn_resolved event.

export interface UseSteal {
  target_player_id: string;
}

export type StealChallengeType =
  | "fastest_word"
  | "unscramble"
  | "longest_word_sprint"
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

export interface StealRejected {
  challenger_id: string;
  rejecter_id: string;
  penalty_applied: boolean; // false for the rejecter's first 2 rejects this game
  points_lost: number; // 0 or 75
}
// Note: use_steal consumes the powerup immediately regardless of accept,
// reject, win, or lose.

// --- Steal challenge minigame flow ---
// Built types: reaction_race, unscramble, fastest_word, math_flash.
// (longest_word_sprint is listed as a valid challenge type but not
// currently implemented server-side — do not offer it in the UI yet.)

export interface ReactionRacePrompt {}
export interface UnscramblePrompt {
  scrambled: string;
}
export interface FastestWordPrompt {
  starting_letter: string;
}
export interface MathFlashPrompt {
  expression: string; // e.g. "5 + 3"
}

export type ChallengePromptData =
  | ReactionRacePrompt
  | UnscramblePrompt
  | FastestWordPrompt
  | MathFlashPrompt;

export interface ChallengeStart {
  challenge_type: StealChallengeType;
  prompt_data: ChallengePromptData;
}

// S→both. reaction_race only — other challenge types start immediately
// on challenge_start with no separate go signal.
export interface ChallengeGo {}

export interface ChallengeSubmit {
  value: string | number;
  // string for unscramble/fastest_word, number for math_flash.
  // reaction_race needs no value field content — server times receipt,
  // but the client should still emit challenge_submit with an empty/
  // placeholder value the instant the player reacts.
}
// On a false start or no valid submissions from either player, in ANY of
// the four built challenge types, the target wins by default.

// --- Rejoin (rounds mode only) ---

export interface RejoinRequest {}

export interface RejoinVoteStart {
  requesting_player_id: string;
  expires_at: number; // epoch ms
}

export interface RejoinVoteCast {
  vote: boolean;
}

export interface RejoinResult {
  player_id: string;
  approved: boolean;
  new_score_if_approved?: number;
}

// --- Game end ---

export interface GameEnded {
  winner_id_or_ids: string[]; // multiple entries only on a tie
  reason: "last_standing" | "round_limit";
  final_scores: { player_id: string; score: number }[];
}

// --- Errors ---

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

export interface TurnStart {
  player_id: string;
  server_timestamp: number;
  duration_seconds: number;
  round_number: number;
  required_letter: string;
}

export interface RoomStateSnapshot {
  room_code: string;
  mode: RoomMode;
  state: RoomState;
  players: PublicPlayerInfo[];
  current_round: number | null;
  current_turn_player_id: string | null;
  required_letter: string | null;
  turn_started_at: number | null;
  turn_duration_seconds: number;
}

export interface DoubleScoreActivated {
  player_id: string;
  new_total_score: number;
}

export interface LifeLost {
  player_id: string;
  new_lives: number;
  reason: "timeout" | "steal_lost";
}