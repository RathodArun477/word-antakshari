import type { RoomStateSnapshot, PlayerStateSnapshot } from "../types/contract";

interface GameState {
  roomState: RoomStateSnapshot | null;
  playerState: PlayerStateSnapshot | null;
}

const state: GameState = {
  roomState: null,
  playerState: null,
};

export function getState(): Readonly<GameState> {
  return state;
}

export function setRoomState(roomState: RoomStateSnapshot): void {
  state.roomState = roomState;
}

export function setPlayerState(playerState: PlayerStateSnapshot): void {
  state.playerState = playerState;
  sessionStorage.setItem("session_token", playerState.session_token);
  sessionStorage.setItem("room_code", state.roomState?.room_code ?? "");
}

export function getSavedSession(): { room_code: string; session_token: string } | null {
  const room_code = sessionStorage.getItem("room_code");
  const session_token = sessionStorage.getItem("session_token");
  if (!room_code || !session_token) return null;
  return { room_code, session_token };
}

export function clearSavedSession(): void {
  sessionStorage.removeItem("session_token");
  sessionStorage.removeItem("room_code");
}

export function resetState(): void {
  state.roomState = null;
  state.playerState = null;
  clearSavedSession();
}