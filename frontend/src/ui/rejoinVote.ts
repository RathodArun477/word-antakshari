import { socket } from "../socket/connection";
import { getState, setRoomState } from "../state/gameState";
import { showOverlay, removeOverlay } from "./overlay";
import type { RejoinVoteStart } from "../types/contract";

export function renderRejoinButton(container: HTMLElement): void {
  const state = getState();
  const room = state.roomState;
  const me = state.playerState;
  if (!room || !me) return;

  const myPlayer = room.players.find(p => p.player_id === me.player_id);
  const isEliminated = myPlayer?.is_eliminated ?? false;
  const canRejoin = isEliminated && me.rejoins_used < 1 && room.mode === "rounds";

  if (!canRejoin) {
    container.innerHTML = "";
    return;
  }

  container.innerHTML = `
    <button id="rejoin-btn" class="w-full bg-violet-600/10 text-violet-300 border border-violet-500/30 hover:bg-violet-600/20 rounded-xl py-3.5 text-xs font-bold uppercase tracking-wider transition-all duration-300">
      Request Rejoin
    </button>
  `;
  container.querySelector<HTMLButtonElement>("#rejoin-btn")!.onclick = () => {
    const html = `
      <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-pink-500"></div>
      <h2 class="text-lg font-bold text-white tracking-wide text-center">Confirm Rejoin Request</h2>
      <p class="text-xs text-gray-400 font-medium text-center my-4 leading-relaxed">
        Rejoining will deduct <strong class="text-pink-400 font-extrabold">50% of your points</strong>. 
        These deducted points will be distributed equally among players who vote <strong class="text-emerald-400 font-bold">YES</strong> for you. 
        Players who vote <strong class="text-pink-400 font-bold">NO</strong> receive nothing. 
        <br/><br/>
        Do you still want to request a rejoin?
      </p>
      <div class="flex gap-3">
        <button id="rejoin-confirm-yes" class="flex-1 glass-button rounded-xl py-3 text-xs font-bold uppercase tracking-wider">Yes, Deduct & Ask</button>
        <button id="rejoin-confirm-no" class="flex-1 bg-white/5 border border-white/10 text-gray-400 font-bold rounded-xl py-3 text-xs uppercase tracking-wider hover:bg-white/10 transition-all duration-300">Cancel</button>
      </div>
    `;
    const overlay = showOverlay("rejoin-confirm", html);

    overlay.querySelector<HTMLButtonElement>("#rejoin-confirm-yes")!.onclick = () => {
      socket.emit("rejoin_request", {});
      removeOverlay("rejoin-confirm");
    };

    overlay.querySelector<HTMLButtonElement>("#rejoin-confirm-no")!.onclick = () => {
      removeOverlay("rejoin-confirm");
    };
  };
}

socket.on("rejoin_vote_start", (data: RejoinVoteStart) => {
  const state = getState();
  const requester = state.roomState?.players.find(p => p.player_id === data.requesting_player_id);

  const html = `
    <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-pink-500"></div>
    <h2 class="text-lg font-bold text-white tracking-wide text-center">Rejoin Vote</h2>
    <p class="text-xs text-gray-400 font-medium text-center my-4 leading-relaxed font-semibold">
      <strong class="text-violet-300 font-bold">${requester?.name ?? "A player"}</strong> wants to rejoin the arena. 
      <br/><br/>
      If they rejoin, their 50% points penalty will be shared among everyone who votes <strong class="text-emerald-400">YES</strong>. 
      If you vote <strong class="text-pink-400">NO</strong>, you won't get any share of their points.
    </p>
    <div class="flex gap-3">
      <button id="vote-yes" class="flex-1 bg-emerald-600/20 border border-emerald-500/30 text-emerald-400 font-bold rounded-xl py-3 text-xs uppercase tracking-wider hover:bg-emerald-600/30 transition-all duration-300">Vote Yes</button>
      <button id="vote-no" class="flex-1 bg-pink-600/20 border border-pink-500/30 text-pink-400 font-bold rounded-xl py-3 text-xs uppercase tracking-wider hover:bg-pink-600/30 transition-all duration-300">Vote No</button>
    </div>
  `;
  const overlay = showOverlay("rejoin-vote", html);

  overlay.querySelector<HTMLButtonElement>("#vote-yes")!.onclick = () => {
    socket.emit("rejoin_vote_cast", { vote: true });
    removeOverlay("rejoin-vote");
  };
  overlay.querySelector<HTMLButtonElement>("#vote-no")!.onclick = () => {
    socket.emit("rejoin_vote_cast", { vote: false });
    removeOverlay("rejoin-vote");
  };

  const msLeft = data.expires_at - Date.now();
  setTimeout(() => removeOverlay("rejoin-vote"), Math.max(0, msLeft));
});

socket.on("rejoin_result", (data: any) => {
  if (data.room_state) {
    setRoomState(data.room_state);
  }
  const state = getState();
  const room = state.roomState;

  if (room && data.approved) {
    const player = room.players.find(p => p.player_id === data.player_id);
    if (player) {
      player.is_eliminated = false;
      player.lives = 1;
      if (data.new_score_if_approved !== undefined && data.new_score_if_approved !== null) {
        player.score = data.new_score_if_approved;
      }
    }

    const me = state.playerState;
    if (me && me.player_id === data.player_id) {
      me.lives = 1;
      if (data.new_score_if_approved !== undefined && data.new_score_if_approved !== null) {
        me.score = data.new_score_if_approved;
      }
    }

    if (me) {
      const myUpdatedObj = room.players.find(p => p.player_id === me.player_id);
      if (myUpdatedObj) {
        me.score = myUpdatedObj.score;
      }
    }

    setRoomState(room);
    import("./gameBoard").then(({ renderGameBoard }) => {
      renderGameBoard(document.querySelector<HTMLDivElement>("#app")!);
    });
  }

  const name = room?.players.find(p => p.player_id === data.player_id)?.name ?? "Player";
  const msgEl = document.querySelector<HTMLParagraphElement>("#game-message");
  if (msgEl) {
    msgEl.textContent = data.approved
      ? `🎉 ${name} rejoined the game!`
      : `❌ ${name}'s rejoin request was denied.`;
    msgEl.className = data.approved
      ? "text-center text-sm text-emerald-400 font-semibold animate-pop-in"
      : "text-center text-sm text-pink-400 font-semibold animate-shake";
    if (!data.approved) {
      setTimeout(() => { msgEl.classList.remove("animate-shake"); }, 400);
    }
  }
});