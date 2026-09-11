import { socket } from "../socket/connection";
import { showOverlay, removeOverlay } from "./overlay";
import type {
  StealChallengeOffer,
  StealChallengeType,
  ChallengeStart,
  StealChallengeResult,
  StealRejected,
  DoubleScoreActivated,
} from "../types/contract";
import { getState, setPlayerState, setRoomState } from "../state/gameState";
import type { SkipUsed } from "../types/contract";

export function renderPowerupBar(container: HTMLElement): void {
  const state = getState();
  const me = state.playerState;
  if (!me) return;

  container.innerHTML = `
    <div class="flex gap-4 justify-center items-center py-2 animate-pop-in">
      <button id="skip-btn" ${!me.has_skip ? "disabled" : ""}
        class="px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-xl transition-all duration-300 transform hover:scale-105 active:scale-95
        ${me.has_skip 
          ? 'bg-violet-600/10 text-violet-300 border border-violet-500/30 hover:bg-violet-600/20 shadow-md shadow-violet-500/5' 
          : 'bg-white/3 border border-white/5 text-gray-600 cursor-not-allowed'}">
        ⚡ Skip Turn ⏭️
      </button>
      <button id="double-btn" ${!me.has_double_score ? "disabled" : ""}
        class="px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-xl transition-all duration-300 transform hover:scale-105 active:scale-95
        ${me.has_double_score 
          ? 'bg-amber-600/10 text-amber-300 border border-amber-500/30 hover:bg-amber-600/20 shadow-md shadow-amber-500/5' 
          : 'bg-white/3 border border-white/5 text-gray-600 cursor-not-allowed'}">
        🔥 Double Score 💥
      </button>
      <button id="steal-btn" ${!me.has_steal ? "disabled" : ""}
        class="px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-xl transition-all duration-300 transform hover:scale-105 active:scale-95
        ${me.has_steal 
          ? 'bg-pink-600/10 text-pink-300 border border-pink-500/30 hover:bg-pink-600/20 shadow-md shadow-pink-500/5' 
          : 'bg-white/3 border border-white/5 text-gray-600 cursor-not-allowed'}">
        ⚔️ Steal Life 🩸
      </button>
    </div>
  `;

  container.querySelector<HTMLButtonElement>("#skip-btn")!.onclick = () => {
    socket.emit("use_skip", {});
    const state = getState();
    if (state.playerState) {
      setPlayerState({ ...state.playerState, has_skip: false });
    }
  };

  container.querySelector<HTMLButtonElement>("#double-btn")!.onclick = () => {
    socket.emit("use_double_score", {});
    const state = getState();
    if (state.playerState) {
      setPlayerState({ ...state.playerState, has_double_score: false });
    }
  };

  container.querySelector<HTMLButtonElement>("#steal-btn")!.onclick = () => {
    showStealTargetPicker();
  };
}

function showStealTargetPicker(): void {
  const state = getState();
  const room = state.roomState;
  const me = state.playerState;
  if (!room || !me) return;

  const targets = room.players.filter(p => p.player_id !== me.player_id && !p.is_eliminated);

  const html = `
    <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-pink-500 to-rose-500"></div>
    <h2 class="text-lg font-bold text-white tracking-wide text-center">Select Target Player</h2>
    <p class="text-xs text-gray-400 text-center font-medium mb-4">Choose who you want to steal a life from:</p>
    <div class="space-y-2">
      ${targets.map(p => `
        <button data-target="${p.player_id}"
          class="steal-target-btn w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-left font-medium text-gray-200 hover:bg-white/10 hover:border-pink-500/30 transition-all duration-200 cursor-pointer">
          ${p.name} <span class="text-xs text-pink-400 font-bold ml-1">(${p.lives} Lives)</span>
        </button>
      `).join("")}
    </div>
    <button id="cancel-steal" class="btn-ghost w-full text-xs font-semibold text-gray-400 hover:text-white uppercase tracking-wider mt-3">Cancel</button>
  `;
  const overlay = showOverlay("steal-target-picker", html);

  overlay.querySelectorAll<HTMLButtonElement>(".steal-target-btn").forEach(btn => {
    btn.onclick = () => {
      socket.emit("use_steal", { target_player_id: btn.dataset.target });
      const state = getState();
      if (state.playerState) {
        setPlayerState({ ...state.playerState, has_steal: false });
      }
      removeOverlay("steal-target-picker");
    };
  });

  overlay.querySelector<HTMLButtonElement>("#cancel-steal")!.onclick = () => {
    removeOverlay("steal-target-picker");
  };
}

// --- Being targeted: offer, accept/reject ---

socket.on("steal_challenge_offer", (data: StealChallengeOffer) => {
  const state = getState();
  const challenger = state.roomState?.players.find(p => p.player_id === data.challenger_id);
  const usableChallenges = data.available_challenges.filter(c => c !== "longest_word_sprint");

  const html = `
    <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-fuchsia-500"></div>
    <h2 class="text-xl font-bold text-white tracking-wide text-center mb-1">Arena Challenge!</h2>
    <p class="text-xs text-gray-400 text-center font-medium mb-4">
      <strong class="text-violet-300 font-bold">${challenger?.name ?? "A player"}</strong> is attempting to steal one of your lives! Pick a minigame to defend:
    </p>
    <div class="grid grid-cols-2 gap-3 mb-4">
      ${usableChallenges.map(c => `
        <button data-type="${c}"
          class="challenge-choice-btn bg-white/5 border border-white/10 rounded-xl px-3 py-3 text-center text-xs font-bold uppercase tracking-wider text-gray-200 hover:bg-violet-600/10 hover:border-violet-500/30 transition-all duration-200 cursor-pointer">
          ${formatChallengeName(c)}
        </button>
      `).join("")}
    </div>
    <div class="border-t border-white/5 pt-4">
      <button id="reject-steal-btn" class="btn-secondary w-full text-pink-400 border-pink-500/20 hover:bg-pink-500/10 text-xs font-bold uppercase tracking-wider">
        Reject Challenge (-75 pts penalty)
      </button>
    </div>
  `;
  const overlay = showOverlay("steal-offer", html);

  overlay.querySelectorAll<HTMLButtonElement>(".challenge-choice-btn").forEach(btn => {
    btn.onclick = () => {
      socket.emit("steal_challenge_response", {
        accept: true,
        challenge_type_if_accepted: btn.dataset.type,
      });
      removeOverlay("steal-offer");
    };
  });

  overlay.querySelector<HTMLButtonElement>("#reject-steal-btn")!.onclick = () => {
    socket.emit("steal_challenge_response", { accept: false });
    removeOverlay("steal-offer");
  };
});

function formatChallengeName(type: StealChallengeType): string {
  const names: Record<string, string> = {
    fastest_word: "🏎️ Speed Word",
    unscramble: "🧩 Unscramble",
    reaction_race: "⚡ Reaction Race",
    math_flash: "🧮 Math Flash",
  };
  return names[type] ?? type;
}

// --- The actual minigames ---

socket.on("challenge_start", (data: ChallengeStart) => {
  let html = "";

  if (data.challenge_type === "reaction_race") {
    html = `
      <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-pink-500"></div>
      <h2 class="text-xl font-extrabold text-white text-center">REACTION RACE</h2>
      <p class="text-xs text-gray-400 font-medium text-center mb-4">Keep your mouse ready. Wait for the button to turn <span class="text-emerald-400 font-semibold">GREEN</span>, then click instantly!</p>
      <button id="reaction-btn" disabled
        class="w-full bg-white/5 border border-white/5 rounded-xl py-5 text-sm font-bold uppercase tracking-wider text-gray-500 cursor-not-allowed transition-all duration-100">
        Ready...
      </button>
    `;
  } else if (data.challenge_type === "unscramble") {
    const prompt = data.prompt_data as { scrambled: string };
    html = `
      <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-pink-500"></div>
      <h2 class="text-xl font-extrabold text-white text-center">🧩 UNSCRAMBLE</h2>
      <div class="bg-white/3 border border-white/5 rounded-xl py-4 text-center mb-4">
        <p class="text-3xl font-black font-mono tracking-widest text-violet-300 uppercase">${prompt.scrambled}</p>
      </div>
      <div class="space-y-3">
        <input id="challenge-input" type="text" placeholder="Enter unscrambled word" class="w-full glass-input rounded-xl px-4 py-3 text-sm focus:outline-none" />
        <button id="challenge-submit-btn" class="w-full glass-button rounded-xl py-3.5 text-xs font-bold uppercase tracking-wider">Submit</button>
      </div>
    `;
  } else if (data.challenge_type === "fastest_word") {
    const prompt = data.prompt_data as { starting_letter: string };
    html = `
      <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-pink-500"></div>
      <h2 class="text-xl font-extrabold text-white text-center">🏎️ SPEED WORD</h2>
      <p class="text-xs text-gray-400 text-center font-medium mb-4">Type any valid English word starting with:</p>
      <div class="w-16 h-16 rounded-full bg-violet-600/10 border border-violet-500/30 flex items-center justify-center text-3xl font-black text-violet-300 mx-auto animate-pulse mb-4">
        ${prompt.starting_letter.toUpperCase()}
      </div>
      <div class="space-y-3">
        <input id="challenge-input" type="text" placeholder="Enter word" class="w-full glass-input rounded-xl px-4 py-3 text-sm focus:outline-none" />
        <button id="challenge-submit-btn" class="w-full glass-button rounded-xl py-3.5 text-xs font-bold uppercase tracking-wider">Submit</button>
      </div>
    `;
  } else if (data.challenge_type === "math_flash") {
    const prompt = data.prompt_data as { expression: string };
    html = `
      <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-pink-500"></div>
      <h2 class="text-xl font-extrabold text-white text-center">🧮 MATH FLASH</h2>
      <div class="bg-white/3 border border-white/5 rounded-xl py-4 text-center mb-4">
        <p class="text-3xl font-black font-mono tracking-widest text-violet-300">${prompt.expression}</p>
      </div>
      <div class="space-y-3">
        <input id="challenge-input" type="number" placeholder="Enter answer" class="w-full glass-input rounded-xl px-4 py-3 text-sm focus:outline-none" />
        <button id="challenge-submit-btn" class="w-full glass-button rounded-xl py-3.5 text-xs font-bold uppercase tracking-wider">Submit</button>
      </div>
    `;
  }

  const overlay = showOverlay("challenge-minigame", html);

  if (data.challenge_type === "reaction_race") {
    const btn = overlay.querySelector<HTMLButtonElement>("#reaction-btn")!;
    btn.onclick = () => {
      socket.emit("challenge_submit", { value: "reacted" });
      removeOverlay("challenge-minigame");
    };
  } else {
    const submitBtn = overlay.querySelector<HTMLButtonElement>("#challenge-submit-btn")!;
    const input = overlay.querySelector<HTMLInputElement>("#challenge-input")!;
    const submit = () => {
      const raw = input.value.trim();
      if (!raw) return;
      const value = data.challenge_type === "math_flash" ? Number(raw) : raw;
      socket.emit("challenge_submit", { value });
      removeOverlay("challenge-minigame");
    };
    submitBtn.onclick = submit;
    input.onkeydown = (e) => { if (e.key === "Enter") submit(); };
  }
});

socket.on("challenge_go", () => {
  const btn = document.querySelector<HTMLButtonElement>("#reaction-btn");
  if (btn) {
    btn.disabled = false;
    btn.textContent = "💥 CLICK NOW!";
    btn.className = "w-full bg-gradient-to-r from-emerald-500 to-teal-500 text-white rounded-xl py-5 text-sm font-black uppercase tracking-wider shadow-lg shadow-emerald-500/20 active:scale-95 transition-all duration-75 cursor-pointer";
  }
});

socket.on("steal_challenge_result", (data: StealChallengeResult) => {
  removeOverlay("challenge-minigame");
  const state = getState();
  const room = state.roomState;

  if (room && data.life_transferred) {
    const winner = room.players.find(p => p.player_id === data.winner_id);
    const loser = room.players.find(p => p.player_id === data.loser_id);
    if (winner) winner.lives += 1;
    if (loser) {
      loser.lives -= 1;
      if (loser.lives <= 0) loser.is_eliminated = true;
    }
    setRoomState(room);
  }

  const winnerName = room?.players.find(p => p.player_id === data.winner_id)?.name ?? "Someone";
  const msgEl = document.querySelector<HTMLParagraphElement>("#game-message");
  if (msgEl) {
    msgEl.textContent = `⚔️ ${winnerName} won the challenge!`;
    msgEl.className = "text-center text-sm text-emerald-400 font-semibold animate-pop-in";
  }

  import("./gameBoard").then(({ renderGameBoard }) => {
    renderGameBoard(document.querySelector<HTMLDivElement>("#app")!);
  });
});

socket.on("steal_rejected", (data: StealRejected) => {
  const state = getState();
  const room = state.roomState;
  if (room && data.penalty_applied) {
    const rejecter = room.players.find(p => p.player_id === data.rejecter_id);
    if (rejecter) {
      rejecter.score -= data.points_lost;
    }
    setRoomState(room);
  }

  if (state.playerState && state.playerState.player_id === data.rejecter_id && data.penalty_applied) {
    setPlayerState({
      ...state.playerState,
      score: state.playerState.score - data.points_lost,
    });
  }

  const msgEl = document.querySelector<HTMLParagraphElement>("#game-message");
  if (msgEl) {
    msgEl.textContent = data.penalty_applied
      ? `Steal challenge rejected! (-${data.points_lost} points penalty)`
      : `Steal challenge rejected!`;
    msgEl.className = "text-center text-sm text-amber-400 font-semibold animate-pop-in";
  }

  import("./gameBoard").then(({ renderGameBoard }) => {
    const app = document.querySelector<HTMLDivElement>("#app");
    if (app) renderGameBoard(app);
  });
});

socket.on("skip_used", (data: SkipUsed) => {
  const state = getState();
  const name = state.roomState?.players.find(p => p.player_id === data.player_id)?.name ?? "Someone";
  const msgEl = document.querySelector<HTMLParagraphElement>("#game-message");
  if (msgEl) {
    msgEl.textContent = `⚡ ${name} skipped their turn!`;
    msgEl.className = "text-center text-sm text-violet-400 font-bold uppercase tracking-wider animate-pop-in";
  }
});

socket.on("double_score_activated", (data: DoubleScoreActivated) => {
  const state = getState();
  const room = state.roomState;
  if (room) {
    const player = room.players.find(p => p.player_id === data.player_id);
    if (player) player.score = data.new_total_score;
    setRoomState(room);
  }

  const name = room?.players.find(p => p.player_id === data.player_id)?.name ?? "Someone";
  const msgEl = document.querySelector<HTMLParagraphElement>("#game-message");
  if (msgEl) {
    msgEl.textContent = `🔥 ${name} doubled their total score!`;
    msgEl.className = "text-center text-sm text-amber-400 font-bold uppercase tracking-wider animate-pop-in";
  }

  import("./gameBoard").then(({ renderGameBoard }) => {
    renderGameBoard(document.querySelector<HTMLDivElement>("#app")!);
  });
});