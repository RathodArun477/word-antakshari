import { socket } from "../socket/connection";
import { getState, setRoomState } from "../state/gameState";
import { renderLobby } from "./lobby";
import type {
  TurnStart,
  TurnResolved,
  WordResult,
  PlayerEliminated,
  GameEnded,
  ErrorEvent,
  LifeLost,
} from "../types/contract";
import { connectSocket } from "../socket/connection";
import { showScreen } from "../state/screen";
import { resetState } from "../state/gameState";
import type { PlayerDisconnected  } from "../types/contract";
import type { PlayerKicked } from "../types/contract";
import type { ReconnectSuccess } from "../types/contract";

socket.on("game_started", () => {
  showScreen(renderGameBoard);
});

let currentTurnPlayerId: string | null = null;
let turnEndsAt: number = 0;
let turnDurationMs: number = 0;
let timerInterval: number | null = null;
let requiredLetter : string = "";

export function renderGameBoard(container: HTMLElement): void {
  const state = getState();
  const room = state.roomState!;
  const me = state.playerState!;

  container.innerHTML = `
    <div class="max-w-4xl mx-auto mt-6 p-4 md:p-6 space-y-8 animate-pop-in">
      <!-- Top Bar -->
      <div class="flex items-center justify-between">
        <div class="space-y-1">
          <h1 class="text-2xl font-extrabold tracking-wider bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">
            WORD ANTAKSHARI
          </h1>
          <p class="text-xs text-gray-400">Survival Mode | Arena: ${room.room_code}</p>
        </div>
        <button id="leave-btn" class="px-3 py-1.5 rounded-lg border border-red-500/30 text-xs font-semibold text-red-400 hover:bg-red-500/10 transition-all duration-300">
          Leave Game
        </button>
      </div>

      <!-- Action Area (Powerup bar & rejoin notices) -->
      <div id="powerup-bar"></div>
      
      <!-- Guess Streak Counter Badge -->
      <div class="flex justify-center mt-2 animate-pop-in">
        <div class="bg-violet-600/15 border border-violet-500/30 text-violet-300 rounded-xl px-4 py-2 text-xs font-bold uppercase tracking-wider flex items-center gap-2 shadow-lg shadow-violet-500/5">
          🔥 Guess Streak: <span class="text-white text-sm font-black">${me.correct_guess_streak ?? 0}</span>/5 
          ${me.has_double_score ? '<span class="text-emerald-400 font-extrabold ml-1 animate-pulse">(2X Score Ready!)</span>' : '<span class="text-gray-500 font-normal ml-1">(Earns 2x Score)</span>'}
        </div>
      </div>

      <div id="rejoin-container"></div>  

      <!-- Central Stats / Required Letter -->
      <div class="grid md:grid-cols-3 gap-6 items-center">
        <!-- Players List Grid -->
        <div id="players-list" class="md:col-span-2 grid grid-cols-2 gap-4">
          ${room.players.map(p => {
            const isCurrent = p.player_id === currentTurnPlayerId;
            const isMe = p.player_id === me.player_id;
            return `
              <div id="player-${p.player_id}"
                class="glass-panel rounded-xl p-4 flex flex-col justify-between min-h-[90px] relative overflow-hidden transition-all duration-300
                ${isCurrent ? "animate-turn-glow" : ""} 
                ${p.is_eliminated ? "opacity-30 grayscale" : ""}">
                
                <!-- Active indicator line -->
                ${isCurrent ? '<div class="absolute left-0 top-0 bottom-0 w-1 bg-violet-500"></div>' : ''}
                
                <div class="flex items-center justify-between">
                  <span class="font-bold text-sm tracking-wide text-gray-200 flex items-center">
                    ${p.name}
                    ${isMe ? '<span class="ml-2 text-[9px] bg-pink-500/20 text-pink-300 border border-pink-500/30 rounded-full px-2 py-0.5 font-bold uppercase tracking-wider">You</span>' : ''}
                  </span>
                  ${isCurrent ? '<span class="text-[8px] bg-violet-500/20 text-violet-300 border border-violet-500/30 rounded-full px-1.5 py-0.5 font-bold uppercase animate-pulse">Turn</span>' : ''}
                </div>

                <div class="flex items-center justify-between mt-3">
                  <div class="flex flex-col">
                    <span class="text-xs text-gray-400 font-medium">Score: <strong class="text-white">${p.score}</strong></span>
                    ${p.correct_guess_streak > 0 ? `<span class="text-[10px] text-amber-400 font-extrabold flex items-center gap-1 mt-0.5">🔥 Streak: ${p.correct_guess_streak}</span>` : ''}
                  </div>
                  
                  <!-- Lives Display as Heart Badges -->
                  <div class="flex gap-0.5">
                    ${Array.from({ length: 3 }).map((_, i) => `
                      <span class="text-xs transition-all duration-300 transform hover:scale-125">${i < p.lives ? '💖' : '💔'}</span>
                    `).join("")}
                  </div>
                </div>
              </div>
            `;
          }).join("")}
        </div>

        <!-- Required Letter Circle Card -->
        <div class="glass-panel rounded-2xl p-6 text-center space-y-4 flex flex-col items-center justify-center min-h-[200px] relative overflow-hidden">
          <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-pink-500"></div>
          <p class="text-xs font-bold uppercase tracking-widest text-gray-400">Required Letter</p>
          <div class="w-20 h-20 rounded-full bg-gradient-to-tr from-violet-500 to-pink-500 flex items-center justify-center text-4xl font-black text-white shadow-lg shadow-violet-500/30 animate-pulse">
            ${requiredLetter ? requiredLetter.toUpperCase() : "..."}
          </div>
          <p class="text-xs text-violet-300 font-medium">Submit word starting with this letter</p>
        </div>
      </div>

      <!-- Turn timer bar -->
      <div class="space-y-2">
        <div class="w-full bg-white/5 rounded-full h-3 overflow-hidden border border-white/5">
          <div id="timer-bar" class="bg-gradient-to-r from-violet-500 to-pink-500 h-3 rounded-full transition-all duration-100" style="width: 100%"></div>
        </div>
      </div>

      <!-- Word submission console -->
      <div class="glass-panel rounded-2xl p-6 space-y-4">
        <div class="flex flex-col md:flex-row gap-4">
          <input id="word-input" type="text" placeholder="Type your word..."
            class="flex-1 glass-input rounded-xl px-4 py-3.5 text-sm focus:outline-none" />
          <button id="submit-word-btn"
            class="glass-button rounded-xl px-8 py-3.5 text-sm font-bold uppercase tracking-wider">
            Submit Word
          </button>
        </div>
        <div class="flex flex-col items-center justify-center space-y-1 min-h-[24px]">
          <p id="game-message" class="text-center text-sm font-semibold transition-all duration-300"></p>
          <p id="streak-display" class="text-center text-xs text-violet-400 font-bold uppercase tracking-wider"></p>
        </div>
      </div>
    </div>
  `;

  updateTurnUI();
  startTimerBar();

  container.querySelector<HTMLButtonElement>("#submit-word-btn")!.onclick = submitWord;
  import("./powerups").then(({ renderPowerupBar }) => {
    renderPowerupBar(container.querySelector<HTMLDivElement>("#powerup-bar")!);
  });
  import("./rejoinVote").then(({ renderRejoinButton }) => {
    renderRejoinButton(container.querySelector<HTMLDivElement>("#rejoin-container")!);
  });
  container.querySelector<HTMLInputElement>("#word-input")!.onkeydown = (e) => {
    if (e.key === "Enter") submitWord();
  };
  container.querySelector<HTMLButtonElement>("#leave-btn")!.onclick = () => {
    let done = false;
    const leave = () => {
      if (done) return;
      done = true;
      socket.disconnect();
      resetState();
      connectSocket();
      import("./lobby").then(({ renderLobby }) => {
        showScreen(renderLobby);
      });
    };
    socket.emit("leave_room", {}, leave);
    setTimeout(leave, 500); // fallback if server doesn't respond quickly
  };
}

function submitWord(): void {
  const input = document.querySelector<HTMLInputElement>("#word-input")!;
  const word = input.value.trim();
  if (!word) return;

  socket.emit("word_submit", { word }, (result: WordResult) => {
    const msgEl = document.querySelector<HTMLParagraphElement>("#game-message")!;
    if (!result.accepted) {
      if (result.reason_if_rejected === "already_used_warning") {
        msgEl.textContent = "⚠️ Warning: Word already used! Submit another duplicate to lose a life.";
        msgEl.className = "text-center text-xs md:text-sm text-amber-400 font-bold animate-shake";
      } else if (result.reason_if_rejected === "already_used_penalty") {
        msgEl.textContent = "❌ Life Lost! Submitted duplicate word twice.";
        msgEl.className = "text-center text-xs md:text-sm text-red-500 font-extrabold animate-shake";
        input.value = "";
      } else {
        msgEl.textContent = `Rejected: ${result.reason_if_rejected?.replace(/_/g, " ")}`;
        msgEl.className = "text-center text-sm text-pink-400 font-semibold animate-shake";
      }
      setTimeout(() => { msgEl.classList.remove("animate-shake"); }, 400);
    } else {
      msgEl.textContent = "Word Accepted!";
      msgEl.className = "text-center text-sm text-emerald-400 font-semibold";
      input.value = "";
    }
  });
}

function flashLifeLost(playerId: string): void {
  const el = document.getElementById(`player-${playerId}`);
  if (!el) return;
  el.classList.add("bg-red-900/40", "border-red-500/50");
  setTimeout(() => el.classList.remove("bg-red-900/40", "border-red-500/50"), 2000);
}

function updateTurnUI(): void {
  const state = getState();
  const me = state.playerState!;
  const isMyTurn = currentTurnPlayerId === me.player_id;

  const input = document.querySelector<HTMLInputElement>("#word-input");
  const btn = document.querySelector<HTMLButtonElement>("#submit-word-btn");
  if (input) input.disabled = !isMyTurn;
  if (btn) btn.disabled = !isMyTurn;
}

function startTimerBar(): void {
  if (timerInterval !== null) {
    clearInterval(timerInterval);
  }

  timerInterval = window.setInterval(() => {
    const bar = document.querySelector<HTMLDivElement>("#timer-bar");
    if (!bar) return;

    const now = Date.now();
    const remaining = Math.max(0, turnEndsAt - now);
    const percent = turnDurationMs > 0 ? (remaining / turnDurationMs) * 100 : 0;
    bar.style.width = `${percent}%`;

    // Dynamic timer coloring based on time remaining
    if (percent < 25) {
      bar.className = "bg-gradient-to-r from-red-500 to-pink-500 h-3 rounded-full";
    } else if (percent < 50) {
      bar.className = "bg-gradient-to-r from-amber-500 to-orange-500 h-3 rounded-full";
    } else {
      bar.className = "bg-gradient-to-r from-violet-500 to-pink-500 h-3 rounded-full";
    }

    if (remaining <= 0 && timerInterval !== null) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }, 100);
}

// --- Socket listeners ---

socket.on("turn_start", (data: TurnStart) => {
  currentTurnPlayerId = data.player_id;
  turnEndsAt = data.server_timestamp + data.duration_seconds * 1000;
  turnDurationMs = data.duration_seconds * 1000;
  requiredLetter = data.required_letter;

  const state = getState();
  if (state.roomState) {
    renderGameBoard(document.querySelector<HTMLDivElement>("#app")!);
    startTimerBar();
  }
});

socket.on("turn_resolved", (data: TurnResolved) => {
  const state = getState();
  const room = state.roomState;
  if (!room) return;

  const player = room.players.find(p => p.player_id === data.player_id);
  if (player) {
    player.score = data.new_total_score;
    player.lives = data.new_lives;
  }
  
  if (state.playerState && state.playerState.player_id === data.player_id) {
    state.playerState.score = data.new_total_score;
    state.playerState.lives = data.new_lives;
  }
  
  setRoomState(room);

  const msgEl = document.querySelector<HTMLParagraphElement>("#game-message");
  if (msgEl) {
    msgEl.textContent = `${player?.name ?? "Someone"} scored ${data.score_gained} points!`;
    msgEl.className = "text-center text-sm text-emerald-400 font-semibold animate-pop-in";
  }
  
  renderGameBoard(document.querySelector<HTMLDivElement>("#app")!);
});

socket.on("player_eliminated", (data: PlayerEliminated) => {
  const state = getState();
  const room = state.roomState;
  if (!room) return;

  const player = room.players.find(p => p.player_id === data.player_id);
  if (player) player.is_eliminated = true;
  setRoomState(room);

  renderGameBoard(document.querySelector<HTMLDivElement>("#app")!);
});

socket.on("game_ended", (data: GameEnded) => {
  if (timerInterval !== null) clearInterval(timerInterval);

  const app = document.querySelector<HTMLDivElement>("#app")!;
  const state = getState();
  const winnerNames = data.winner_id_or_ids
    .map(id => state.roomState?.players.find(p => p.player_id === id)?.name ?? id)
    .join(", ");

  const sortedScores = [...data.final_scores].sort((a, b) => b.score - a.score);
  const maxScore = Math.max(...sortedScores.map(s => s.score), 1);
  const myPlayerId = state.playerState?.player_id;
  const myRank = sortedScores.findIndex(s => s.player_id === myPlayerId);

  const p1 = sortedScores[0];
  const p2 = sortedScores[1];
  const p3 = sortedScores[2];

  const getPlayerName = (id: string) => state.roomState?.players.find(p => p.player_id === id)?.name ?? id;

  const renderPodiumSlot = (playerData: { player_id: string; score: number } | undefined, rank: 1 | 2 | 3) => {
    if (!playerData) {
      return `<div class="flex-1 max-w-[95px] md:max-w-[120px] opacity-0"></div>`;
    }

    const name = getPlayerName(playerData.player_id);
    const isMe = playerData.player_id === myPlayerId;

    if (rank === 1) {
      return `
        <div class="flex-1 max-w-[110px] md:max-w-[140px] flex flex-col items-center animate-podium-1st relative z-10">
          <div class="relative flex flex-col items-center mb-2">
            <span class="text-3xl md:text-4xl animate-crown-float filter drop-shadow-[0_0_8px_rgba(245,158,11,0.8)]">👑</span>
            <div class="w-14 h-14 md:w-16 md:h-16 rounded-full bg-gradient-to-tr from-amber-500 via-yellow-400 to-amber-200 border-2 border-amber-300 flex items-center justify-center text-slate-950 font-black text-xl md:text-2xl shadow-[0_0_20px_rgba(245,158,11,0.6)] relative mt-[-6px]">
              ${name.charAt(0).toUpperCase()}
              <span class="absolute -bottom-1 -right-1 bg-amber-500 text-slate-950 text-[10px] font-black w-5 h-5 rounded-full flex items-center justify-center border border-amber-200 shadow">🥇</span>
            </div>
            <span class="mt-1.5 font-black text-xs md:text-sm text-yellow-200 truncate max-w-[100px] text-center flex items-center gap-1">
              ${name}
              ${isMe ? '<span class="bg-pink-500 text-white text-[8px] font-extrabold px-1 rounded">YOU</span>' : ''}
            </span>
            <span class="text-[11px] font-extrabold px-2.5 py-0.5 rounded-full bg-amber-500/20 text-yellow-300 border border-amber-400/40 mt-0.5 shadow-sm">
              ${playerData.score} pts
            </span>
          </div>

          <div class="w-full h-36 md:h-44 rounded-t-2xl bg-gradient-to-t from-amber-950 via-amber-900/90 to-yellow-600/30 border-t-4 border-x border-amber-400 animate-gold-glow flex flex-col items-center justify-between py-3 shadow-[0_-5px_30px_rgba(245,158,11,0.35)]">
            <span class="text-2xl md:text-3xl font-black text-amber-300 drop-shadow">#1</span>
            <span class="text-[10px] uppercase font-black tracking-widest text-amber-200/80 bg-amber-950/60 px-2 py-0.5 rounded-full border border-amber-500/30">WINNER</span>
          </div>
        </div>
      `;
    }

    if (rank === 2) {
      return `
        <div class="flex-1 max-w-[95px] md:max-w-[120px] flex flex-col items-center animate-podium-2nd">
          <div class="relative flex flex-col items-center mb-2">
            <div class="w-12 h-12 md:w-14 md:h-14 rounded-full bg-gradient-to-tr from-slate-400 to-slate-200 border-2 border-slate-300 flex items-center justify-center text-slate-950 font-black text-lg md:text-xl shadow-[0_0_15px_rgba(148,163,184,0.4)] relative">
              ${name.charAt(0).toUpperCase()}
              <span class="absolute -bottom-1 -right-1 bg-slate-300 text-slate-950 text-[10px] font-black w-5 h-5 rounded-full flex items-center justify-center border border-white shadow">🥈</span>
            </div>
            <span class="mt-1.5 font-bold text-xs text-slate-200 truncate max-w-[90px] text-center flex items-center gap-1">
              ${name}
              ${isMe ? '<span class="bg-pink-500 text-white text-[8px] font-extrabold px-1 rounded">YOU</span>' : ''}
            </span>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 border border-slate-500/40 text-slate-300 mt-0.5">
              ${playerData.score} pts
            </span>
          </div>

          <div class="w-full h-28 md:h-32 rounded-t-2xl bg-gradient-to-t from-slate-950 via-slate-800/80 to-slate-700/40 border-t-4 border-x border-slate-400/60 flex flex-col items-center justify-between py-3 shadow-[0_-5px_20px_rgba(148,163,184,0.2)]">
            <span class="text-xl md:text-2xl font-black text-slate-300">#2</span>
            <span class="text-[9px] uppercase font-bold tracking-wider text-slate-400">SILVER</span>
          </div>
        </div>
      `;
    }

    return `
      <div class="flex-1 max-w-[95px] md:max-w-[120px] flex flex-col items-center animate-podium-3rd">
        <div class="relative flex flex-col items-center mb-2">
          <div class="w-11 h-11 md:w-13 md:h-13 rounded-full bg-gradient-to-tr from-amber-800 to-amber-600 border-2 border-amber-500 flex items-center justify-center text-amber-100 font-black text-base md:text-lg shadow-[0_0_15px_rgba(180,83,9,0.4)] relative">
            ${name.charAt(0).toUpperCase()}
            <span class="absolute -bottom-1 -right-1 bg-amber-700 text-amber-100 text-[10px] font-black w-5 h-5 rounded-full flex items-center justify-center border border-amber-400 shadow">🥉</span>
          </div>
          <span class="mt-1.5 font-bold text-xs text-amber-200/90 truncate max-w-[90px] text-center flex items-center gap-1">
            ${name}
            ${isMe ? '<span class="bg-pink-500 text-white text-[8px] font-extrabold px-1 rounded">YOU</span>' : ''}
          </span>
          <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-950 border border-amber-700/40 text-amber-300 mt-0.5">
            ${playerData.score} pts
          </span>
        </div>

        <div class="w-full h-20 md:h-24 rounded-t-2xl bg-gradient-to-t from-amber-950 via-amber-900/60 to-amber-800/30 border-t-4 border-x border-amber-700/60 flex flex-col items-center justify-between py-2 shadow-[0_-5px_20px_rgba(180,83,9,0.2)]">
          <span class="text-lg md:text-xl font-black text-amber-400">#3</span>
          <span class="text-[9px] uppercase font-bold tracking-wider text-amber-500/80">BRONZE</span>
        </div>
      </div>
    `;
  };

  const renderListRows = sortedScores
    .map((s, index) => {
      const name = getPlayerName(s.player_id);
      const isMe = s.player_id === myPlayerId;
      const pct = Math.max(Math.round((s.score / maxScore) * 100), 6);

      let rankBadgeClass = "bg-slate-800 border border-slate-700 text-slate-400";
      let rankText = `#${index + 1}`;

      if (index === 0) {
        rankBadgeClass = "bg-amber-500/20 border border-amber-400/60 text-yellow-300 shadow-[0_0_10px_rgba(245,158,11,0.3)]";
        rankText = "🥇 #1";
      } else if (index === 1) {
        rankBadgeClass = "bg-slate-400/20 border border-slate-300/60 text-slate-200";
        rankText = "🥈 #2";
      } else if (index === 2) {
        rankBadgeClass = "bg-amber-900/30 border border-amber-700/60 text-amber-400";
        rankText = "🥉 #3";
      }

      return `
        <div class="animate-row-slide flex items-center justify-between gap-3 p-3.5 rounded-2xl border transition-all duration-300 hover:scale-[1.01] ${
          isMe
            ? 'bg-violet-950/40 border-violet-500/60 shadow-[0_0_20px_rgba(139,92,246,0.25)]'
            : 'bg-slate-900/60 border-white/5 hover:border-white/15'
        }" style="animation-delay: ${(index * 90) + 350}ms">
          <div class="flex items-center gap-3 min-w-0 flex-1">
            <span class="px-2.5 py-1 rounded-xl flex items-center justify-center font-black text-xs shrink-0 ${rankBadgeClass}">
              ${rankText}
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="font-bold text-sm text-gray-100 truncate flex items-center gap-1.5">
                  ${name}
                  ${isMe ? '<span class="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider bg-pink-500/20 text-pink-300 border border-pink-500/40 shrink-0">You</span>' : ''}
                </span>
              </div>
              <div class="w-full bg-slate-950 rounded-full h-2 mt-1.5 overflow-hidden p-0.5 border border-white/5">
                <div class="h-full rounded-full animate-bar-fill ${
                  isMe
                    ? 'bg-gradient-to-r from-violet-500 via-fuchsia-500 to-pink-500'
                    : 'bg-gradient-to-r from-indigo-500 to-violet-400'
                }" style="--target-width: ${pct}%;"></div>
              </div>
            </div>
          </div>
          <div class="text-right shrink-0">
            <span class="text-base font-black text-white">${s.score} <span class="text-[10px] text-gray-400 font-semibold uppercase">pts</span></span>
          </div>
        </div>
      `;
    })
    .join("");

  app.innerHTML = `
    <div class="max-w-2xl mx-auto mt-6 mb-12 p-4 md:p-6 animate-pop-in">
      <div class="glass-panel rounded-3xl p-6 md:p-10 space-y-8 relative overflow-hidden text-center backdrop-blur-xl bg-slate-950/80 border border-violet-500/20 shadow-[0_10px_50px_rgba(0,0,0,0.8)]">
        
        <div class="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-amber-500 via-fuchsia-500 to-violet-500"></div>

        <div class="space-y-2 relative">
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/30 text-violet-300 text-[11px] font-extrabold uppercase tracking-widest">
            <span>🏆</span> Arena Final Results
          </div>
          <h1 class="text-3xl md:text-5xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-200 to-violet-300">
            LEADERBOARD
          </h1>
          <p class="text-sm md:text-base font-semibold text-pink-400">🎉 ${winnerNames} Won the Arena!</p>
          <p class="text-xs text-gray-400">Reason: ${data.reason.replace(/_/g, " ")}</p>
        </div>

        <!-- Podium Layout: 2nd (Left), 1st (Center), 3rd (Right) -->
        <div class="relative pt-6 pb-2">
          <div class="flex items-end justify-center gap-2 md:gap-4 max-w-lg mx-auto">
            ${renderPodiumSlot(p2, 2)}
            ${renderPodiumSlot(p1, 1)}
            ${renderPodiumSlot(p3, 3)}
          </div>
        </div>

        <!-- Detailed Standings List Below Podium -->
        <div class="space-y-4 pt-4 border-t border-white/10 text-left">
          <div class="flex items-center justify-between px-1">
            <h3 class="text-xs font-black uppercase tracking-widest text-violet-300 flex items-center gap-1.5">
              <span>📊</span> Detailed Player Standings
            </h3>
            <span class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">${sortedScores.length} Players</span>
          </div>

          <div class="space-y-2.5">
            ${renderListRows}
          </div>
        </div>

        <div class="pt-2 space-y-2.5">
          <button id="play-again-btn" class="w-full glass-button rounded-2xl py-4 text-xs md:text-sm font-extrabold uppercase tracking-widest shadow-lg shadow-violet-600/30 hover:shadow-violet-600/50 hover:scale-[1.01] transition-all">
            🎮 Back to Arena Lobby
          </button>
          <button id="end-feedback-btn" class="w-full bg-white/5 border border-white/10 hover:bg-white/10 text-xs font-bold text-gray-300 hover:text-white rounded-2xl py-3 px-4 transition-all duration-200 cursor-pointer flex items-center justify-center gap-2">
            💬 Share Feedback
          </button>
        </div>

      </div>
    </div>
  `;

  // Trigger party confetti only if in top 3
  if (myRank !== -1 && myRank < 3) {
    triggerConfetti();
  }

  app.querySelector<HTMLButtonElement>("#end-feedback-btn")!.onclick = () => {
    import("./lobby").then(({ showFeedbackPopup }) => {
      showFeedbackPopup();
    });
  };

  app.querySelector<HTMLButtonElement>("#play-again-btn")!.onclick = () => {
    resetState();
    showScreen(renderLobby);
  };
});

socket.on("error", (data: ErrorEvent) => {
  const msgEl = document.querySelector<HTMLParagraphElement>("#game-message");
  if (msgEl) {
    msgEl.textContent = `Error: ${data.message.replace(/_/g, " ")}`;
    msgEl.className = "text-center text-sm text-pink-400 font-semibold animate-shake";
    setTimeout(() => { msgEl.classList.remove("animate-shake"); }, 400);
  }
});

socket.on("player_disconnected", (data: PlayerDisconnected) => {
  const state = getState();
  const name = state.roomState?.players.find(p => p.player_id === data.player_id)?.name ?? "A player";
  const msgEl = document.querySelector<HTMLParagraphElement>("#game-message");
  if (msgEl) {
    msgEl.textContent = `${name} disconnected — grace period active...`;
    msgEl.className = "text-center text-sm text-amber-400 font-semibold animate-pulse";
  }
});

socket.on("player_kicked", (data: PlayerKicked) => {
  const state = getState();
  const room = state.roomState;
  if (room) {
    const player = room.players.find(p => p.player_id === data.player_id);
    if (player) player.is_eliminated = true;
    setRoomState(room);
  }

  const name = room?.players.find(p => p.player_id === data.player_id)?.name ?? "A player";
  const msgEl = document.querySelector<HTMLParagraphElement>("#game-message");
  if (msgEl) {
    msgEl.textContent = `${name} was kicked (grace period expired).`;
    msgEl.className = "text-center text-sm text-pink-400 font-semibold";
  }

  renderGameBoard(document.querySelector<HTMLDivElement>("#app")!);
});

socket.on("reconnect_success", (data: ReconnectSuccess) => {
  if (data.room_state.state === "in_progress" && data.room_state.current_turn_player_id) {
    currentTurnPlayerId = data.room_state.current_turn_player_id;
    requiredLetter = data.room_state.required_letter ?? "";
    if (data.room_state.turn_started_at) {
      turnEndsAt = data.room_state.turn_started_at + data.room_state.turn_duration_seconds * 1000;
      turnDurationMs = data.room_state.turn_duration_seconds * 1000;
    }
  }
});

socket.on("life_lost", (data: LifeLost) => {
  console.log("Life_lost received:", data);
  const state = getState();
  const room = state.roomState;
  if (room) {
    const player = room.players.find(p => p.player_id === data.player_id);
    if (player) player.lives = data.new_lives;
    setRoomState(room);
  }
  
  if (state.playerState && state.playerState.player_id === data.player_id) {
    state.playerState.lives = data.new_lives;
  }

  renderGameBoard(document.querySelector<HTMLDivElement>("#app")!);
  flashLifeLost(data.player_id);
});

function triggerConfetti(): void {
  const container = document.body;
  const colors = ["#8b5cf6", "#ec4899", "#06b6d4", "#f59e0b", "#10b981", "#eab308", "#3b82f6", "#f43f5e", "#a855f7", "#22c55e"];
  const count = 600; // Increased confetti quantity

  for (let i = 0; i < count; i++) {
    const confetti = document.createElement("div");
    confetti.className = "confetti";
    confetti.style.left = `${Math.random() * 100}vw`;
    confetti.style.top = `-20px`;
    confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
    
    // Vary size for realistic depth
    const size = 6 + Math.random() * 10;
    confetti.style.width = `${size}px`;
    confetti.style.height = `${size * (Math.random() > 0.5 ? 1 : 2.5)}px`;
    
    confetti.style.animationDelay = `${Math.random() * 2.5}s`;
    confetti.style.animationDuration = `${2.5 + Math.random() * 3}s`;
    
    // Randomize shape (circles, squares, ribbons)
    const shapeType = Math.random();
    if (shapeType > 0.66) {
      confetti.style.borderRadius = "50%";
    } else if (shapeType > 0.33) {
      confetti.style.borderRadius = "2px";
    } else {
      confetti.style.borderRadius = "0px";
      confetti.style.transform = `rotate(${Math.random() * 360}deg)`;
    }
    
    container.appendChild(confetti);
    
    // Clean up
    setTimeout(() => confetti.remove(), 6000);
  }
}