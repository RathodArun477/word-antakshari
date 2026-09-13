import { socket } from "../socket/connection";
import { showOverlay, removeOverlay } from "./overlay";
import type { GuessOptions, GuessResult } from "../types/contract";
import { getState } from "../state/gameState";
import { getCurrentTurnId } from "./gameBoard";

const OVERLAY_ID = "guess-popup";

socket.on("guess_options", (data: GuessOptions) => {
  const currentTurnId = getCurrentTurnId();
  if(!currentTurnId || data.turn_id != currentTurnId) {
    return;
  }

  const msLeft = data.expires_at - Date.now();
  if(msLeft <= 0) {
    return;
  }
  const html = `
    <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-pink-500"></div>
    <h2 class="text-xl font-bold text-white tracking-wide text-center mb-1">Guess the Word!</h2>
    <p class="text-xs text-gray-400 text-center font-medium mb-4">Select the word you think the previous player submitted:</p>
    
    <div class="space-y-2">
      ${data.options.map((word, i) => `
        <button data-index="${i}"
          class="guess-option-btn w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-left font-medium text-gray-200 hover:bg-white/10 hover:border-violet-500/30 transition-all duration-200 cursor-pointer">
          ${word}
        </button>
      `).join("")}
    </div>
    
    <button id="skip-guess-btn" class="btn-ghost w-full text-xs font-semibold text-gray-400 hover:text-white uppercase tracking-wider mt-3">
      Leave blank (no guess)
    </button>
  `;
  const overlay = showOverlay(OVERLAY_ID, html);

  overlay.querySelectorAll<HTMLButtonElement>(".guess-option-btn").forEach(btn => {
    btn.onclick = () => {
      const index = Number(btn.dataset.index);
      socket.emit("guess_submit", { guess_index: index , turn_id: currentTurnId,});
      removeOverlay(OVERLAY_ID);
    };
  });

  overlay.querySelector<HTMLButtonElement>("#skip-guess-btn")!.onclick = () => {
    removeOverlay(OVERLAY_ID);
  };

  // const msLeft = data.expires_at - Date.now();
  setTimeout(() => removeOverlay(OVERLAY_ID), Math.max(0, msLeft));
});

// Whenever a new turn starts, any leftover guess popup from the previous
// round is stale -- close it unconditionally. If the player is eligible
// to guess this turn too, a fresh guess_options event replaces it right after.
socket.on("turn_start", () => {
  removeOverlay(OVERLAY_ID);
});

socket.on("guess_result", (data: GuessResult) => {
  removeOverlay(OVERLAY_ID);
  
  const state = getState();
  if (state.playerState) {
    state.playerState.correct_guess_streak = data.streak_count;
    if (data.streak_count >= 5) {
      state.playerState.has_double_score = true;
    }
  }

  // Redraw the game board so the streak badge and powerups update instantly!
  import("./gameBoard").then(({ renderGameBoard }) => {
    const app = document.querySelector<HTMLDivElement>("#app");
    if (app) renderGameBoard(app);
  });

  const msgEl = document.querySelector<HTMLParagraphElement>("#game-message");
  if (msgEl) {
    msgEl.textContent = data.correct
      ? `🎉 Correct guess!`
      : `❌ Wrong guess. ${data.points_delta < 0 ? `Lost ${-data.points_delta} points.` : ""}`;
    msgEl.className = data.correct
      ? "text-center text-sm text-emerald-400 font-semibold animate-pop-in"
      : "text-center text-sm text-pink-400 font-semibold animate-shake";
    if (!data.correct) {
      setTimeout(() => { msgEl.classList.remove("animate-shake"); }, 400);
    }
  }

  const streakEl = document.querySelector<HTMLParagraphElement>("#streak-display");
  if (streakEl) {
    streakEl.textContent = data.streak_count > 0 ? `🔥 Guess Streak: ${data.streak_count}` : "";
  }
});