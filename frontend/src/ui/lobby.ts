import { socket, connectSocket } from "../socket/connection";
import { setRoomState, setPlayerState, getState, resetState } from "../state/gameState";
import { showScreen } from "../state/screen";
import { showOverlay, removeOverlay } from "./overlay";
import type {
  RoomCreated,
  ReconnectSuccess,
  ErrorEvent,
  PlayerJoined,
} from "../types/contract";

export function renderLobby(container: HTMLElement): void {
  const state = getState();

  if (state.roomState && state.roomState.state === "waiting") {
    renderWaitingRoom(container);
  } else {
    renderJoinCreateForms(container);
  }
}

function renderJoinCreateForms(container: HTMLElement): void {
  console.log("renderJoinCreateForms called");
  container.innerHTML = `
    <div class="max-w-4xl mx-auto mt-12 p-4 md:p-8 space-y-12 animate-pop-in relative">
      <!-- Options Dropdown Menu -->
      <div class="absolute top-2 right-2 z-50">
        <button id="menu-btn" class="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all duration-300 cursor-pointer flex items-center justify-center w-8 h-8">
          <span class="text-base font-black">⋮</span>
        </button>
        <div id="menu-dropdown" class="hidden absolute right-0 mt-2 w-52 glass-panel rounded-xl py-1 shadow-xl border border-white/5 animate-pop-in z-50 text-left font-sans">
          <button id="menu-about-btn" class="w-full text-left px-4 py-2.5 text-xs font-semibold text-gray-300 hover:bg-white/5 hover:text-white transition-all duration-200 flex items-center gap-2 cursor-pointer border-b border-white/5">
            ℹ️ About Us
          </button>
          <button id="menu-privacy-btn" class="w-full text-left px-4 py-2.5 text-xs font-semibold text-gray-300 hover:bg-white/5 hover:text-white transition-all duration-200 flex items-center gap-2 cursor-pointer border-b border-white/5">
            🛡️ Privacy Policy
          </button>
          <button id="menu-contact-btn" class="w-full text-left px-4 py-2.5 text-xs font-semibold text-gray-300 hover:bg-white/5 hover:text-white transition-all duration-200 flex items-center gap-2 cursor-pointer border-b border-white/5">
            📬 Contact Support
          </button>
          <button id="menu-feedback-btn" class="w-full text-left px-4 py-2.5 text-xs font-semibold text-gray-300 hover:bg-white/5 hover:text-white transition-all duration-200 flex items-center gap-2 cursor-pointer">
            📋 Give Feedback
          </button>
        </div>
      </div>

      <div class="text-center space-y-3 relative flex flex-col items-center">
        <div class="w-24 h-24 md:w-32 md:h-32 rounded-3xl p-1 bg-slate-900 border border-white/10 shadow-xl shadow-black/60 mb-2 transform hover:scale-105 transition-all duration-300 overflow-hidden">
          <img src="/logo.png" alt="Word Antakshari Logo" class="w-full h-full object-cover rounded-2xl" />
        </div>
        <h1 class="text-4xl md:text-5xl font-black tracking-wider text-slate-100 drop-shadow">
          WORD ANTAKSHARI
        </h1>
        <p class="text-slate-400 font-normal text-sm md:text-base">The ultimate multiplayer word chaining game 🎮</p>
      </div>

      <div class="grid md:grid-cols-2 gap-8">
        <!-- Create Room Card -->
        <div class="glass-panel rounded-2xl p-6 md:p-8 space-y-6 relative overflow-hidden">
          <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-fuchsia-500"></div>
          <h2 class="text-2xl font-bold tracking-wide text-white">Create Arena 🏟️</h2>
          <div class="space-y-4">
            <div>
              <label class="block text-[10px] font-bold uppercase tracking-wider text-violet-300 mb-2">Your Name 👤</label>
              <input id="create-name" type="text" placeholder="Enter name" class="w-full glass-input rounded-xl px-4 py-3 text-sm focus:outline-none" />
            </div>
            <div>
              <label class="block text-[10px] font-bold uppercase tracking-wider text-violet-300 mb-2">Game Mode 🎮</label>
              <select id="create-mode" class="w-full glass-input rounded-xl px-4 py-3 text-sm focus:outline-none">
                <option value="endless">Endless Survival 💀</option>
                <option value="rounds">Rounds Classic 🏁</option>
              </select>
            </div>
            <div id="round-limit-wrapper" class="hidden">
              <label class="block text-[10px] font-bold uppercase tracking-wider text-violet-300 mb-2">Round Limit 🎯</label>
              <input id="create-round-limit" type="number" min="3" max="12" value="5" placeholder="5" class="w-full glass-input rounded-xl px-4 py-3 text-sm focus:outline-none" />
            </div>
            <div>
              <label class="block text-[10px] font-bold uppercase tracking-wider text-violet-300 mb-2">Turn Timer (seconds) ⏱️</label>
              <input id="create-timer" type="number" min="5" value="30" class="w-full glass-input rounded-xl px-4 py-3 text-sm focus:outline-none" />
            </div>
            <button id="create-btn" class="w-full glass-button rounded-xl py-3.5 text-xs font-bold uppercase tracking-wider mt-4">
              Create Room ✨
            </button>
          </div>
        </div>

        <!-- Join Room Card -->
        <div class="glass-panel rounded-2xl p-6 md:p-8 space-y-6 relative overflow-hidden">
          <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-cyan-500 to-blue-500"></div>
          <h2 class="text-2xl font-bold tracking-wide text-white">Join Arena ⚔️</h2>
          <div class="space-y-4">
            <div>
              <label class="block text-[10px] font-bold uppercase tracking-wider text-cyan-300 mb-2">Your Name 👤</label>
              <input id="join-name" type="text" placeholder="Enter name" class="w-full glass-input rounded-xl px-4 py-3 text-sm focus:outline-none" />
            </div>
            <div>
              <label class="block text-[10px] font-bold uppercase tracking-wider text-cyan-300 mb-2">Arena Code 🔑</label>
              <input id="join-code" type="text" placeholder="6-LETTER CODE" class="w-full glass-input rounded-xl px-4 py-3 text-sm uppercase tracking-widest focus:outline-none placeholder:tracking-normal" />
            </div>
            <button id="join-btn" class="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white rounded-xl py-3.5 text-xs font-bold uppercase tracking-wider shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/35 transition-all duration-300 hover:-translate-y-0.5 active:translate-y-0 mt-14">
              Join Room 🚀
            </button>
          </div>
        </div>
      </div>

      <p id="lobby-error" class="text-red-400 text-sm text-center font-medium min-h-[20px] transition-all duration-300"></p>

      <!-- How to Play Section -->
      <div class="max-w-xl mx-auto mt-8">
        <button id="toggle-guide-btn" class="w-full bg-white/3 border border-white/5 hover:bg-white/5 rounded-xl py-3 px-4 text-xs font-bold uppercase tracking-wider text-gray-400 hover:text-white flex items-center justify-between transition-all duration-300 cursor-pointer">
          <span>📖 How to Play & Game Rules</span>
          <span id="guide-chevron" class="transition-transform duration-300">▼</span>
        </button>
        <div id="game-guide" class="hidden glass-panel rounded-2xl p-6 mt-4 space-y-4 text-sm text-gray-300 text-left animate-pop-in relative">
          <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-pink-500"></div>
          <div class="space-y-1">
            <h4 class="text-xs font-bold uppercase tracking-wider text-violet-300">1. Letter Chaining</h4>
            <p class="text-xs text-gray-400">Submit words starting with the target letter. The next player must submit a word starting with the <strong>last letter</strong> of your word.</p>
          </div>
          <div class="space-y-1">
            <h4 class="text-xs font-bold uppercase tracking-wider text-violet-300">2. Guessing Streak & Penalty</h4>
            <p class="text-xs text-gray-400">Guess other players' words during their turns. Current streaks are visible on each player's card:</p>
            <ul class="list-disc list-inside text-xs text-gray-400 pl-1 space-y-0.5">
              <li>🏆 Get <strong class="text-white">5 correct guesses in a row</strong> to unlock the <strong>Double Score</strong> powerup!</li>
              <li>⚠️ <strong class="text-pink-400">3 continuous wrong guesses</strong> will deduct <strong class="text-pink-400">50 points</strong>!</li>
              <li>🔄 Guessing wrong will reset your current correct guess streak to 0. The wrong-guess streak only resets on your next correct guess.</li>
            </ul>
          </div>
          <div class="space-y-1">
            <h4 class="text-xs font-bold uppercase tracking-wider text-violet-300">3. Powerups & Steal Rejections</h4>
            <ul class="list-disc list-inside text-xs text-gray-400 pl-1 space-y-1">
              <li>⚡ <strong class="text-white">Skip:</strong> Pass your turn if you get stuck.</li>
              <li>🔥 <strong class="text-white">Double Score:</strong> Doubles your total score instantly. Consumed on use.</li>
              <li>⚔️ <strong class="text-white">Steal:</strong> Challenge any player to steal one of their lives in a quick mini-challenge!</li>
              <li>🛡️ <strong class="text-white">Rejecting a Steal:</strong> If challenged, you can reject the challenge. Each rejection incurs a <strong class="text-pink-400">-75 points penalty</strong>.</li>
            </ul>
          </div>
          <div class="space-y-1">
            <h4 class="text-xs font-bold uppercase tracking-wider text-violet-300">4. Survival & Victory</h4>
            <p class="text-xs text-gray-400">You start with 3 lives. Lose a life if your turn timer hits 0 or you fail a steal challenge. Be the last player standing to win!</p>
          </div>
      </div>

      <!-- Footer Links & Compliance Bar -->
      <footer class="pt-8 border-t border-white/5 text-center text-xs text-gray-500 space-y-3">
        <div class="flex flex-wrap items-center justify-center gap-4 md:gap-6 font-semibold">
          <button id="footer-about-btn" class="hover:text-violet-300 transition-colors cursor-pointer">ℹ️ About Us</button>
          <span>•</span>
          <button id="footer-privacy-btn" class="hover:text-violet-300 transition-colors cursor-pointer">🛡️ Privacy Policy</button>
          <span>•</span>
          <button id="footer-contact-btn" class="hover:text-violet-300 transition-colors cursor-pointer">📬 Contact Support</button>
          <span>•</span>
          <button id="footer-feedback-btn" class="hover:text-violet-300 transition-colors cursor-pointer">📋 Feedback</button>
        </div>
        <p class="text-[11px] text-gray-600">© 2026 Word Antakshari Arena. All rights reserved. Created by Krishna Dahipalle & Rathod Arun.</p>
      </footer>

    </div>
  `;

  const errorEl = container.querySelector<HTMLParagraphElement>("#lobby-error")!;
  const modeSelect = container.querySelector<HTMLSelectElement>("#create-mode")!;
  const roundLimitWrapper = container.querySelector<HTMLDivElement>("#round-limit-wrapper")!;

  modeSelect.onchange = () => {
    if (modeSelect.value === "rounds") {
      roundLimitWrapper.classList.remove("hidden");
      roundLimitWrapper.classList.add("animate-pop-in");
    } else {
      roundLimitWrapper.classList.add("hidden");
      roundLimitWrapper.classList.remove("animate-pop-in");
    }
  };

  container.querySelector<HTMLButtonElement>("#create-btn")!.onclick = () => {
    console.log("create button clicked");
    const host_name = (container.querySelector("#create-name") as HTMLInputElement).value.trim();
    const mode = modeSelect.value as "endless" | "rounds";
    const round_limit_raw = (container.querySelector("#create-round-limit") as HTMLInputElement).value;
    const turn_timer_seconds = Number((container.querySelector("#create-timer") as HTMLInputElement).value);

    if (!host_name) {
      errorEl.textContent = "Enter your name first.";
      errorEl.className = "text-red-400 text-sm text-center font-medium animate-shake";
      setTimeout(() => { errorEl.className = "text-red-400 text-sm text-center font-medium"; }, 400);
      return;
    }

    const payload: Record<string, unknown> = {
      host_name,
      mode,
      max_players: 8,
      turn_timer_seconds,
    };
    if (mode === "rounds") {
      if (!round_limit_raw) {
        errorEl.textContent = "Rounds mode needs a round limit (3-12).";
        errorEl.className = "text-red-400 text-sm text-center font-medium animate-shake";
        setTimeout(() => { errorEl.className = "text-red-400 text-sm text-center font-medium"; }, 400);
        return;
      }
      payload.round_limit = Number(round_limit_raw);
    }

    errorEl.textContent = "";
    socket.emit("create_room", payload);
  };

  container.querySelector<HTMLButtonElement>("#join-btn")!.onclick = () => {
    const player_name = (container.querySelector("#join-name") as HTMLInputElement).value.trim();
    const room_code = (container.querySelector("#join-code") as HTMLInputElement).value.trim().toUpperCase();

    if (!player_name || !room_code) {
      errorEl.textContent = "Enter your name and a room code.";
      errorEl.className = "text-red-400 text-sm text-center font-medium animate-shake";
      setTimeout(() => { errorEl.className = "text-red-400 text-sm text-center font-medium"; }, 400);
      return;
    }

    errorEl.textContent = "";
    socket.emit("join_room", { room_code, player_name });
  };

  const toggleBtn = container.querySelector<HTMLButtonElement>("#toggle-guide-btn")!;
  const guideEl = container.querySelector<HTMLDivElement>("#game-guide")!;
  const chevron = container.querySelector<HTMLSpanElement>("#guide-chevron")!;
  toggleBtn.onclick = () => {
    if (guideEl.classList.contains("hidden")) {
      guideEl.classList.remove("hidden");
      chevron.style.transform = "rotate(180deg)";
    } else {
      guideEl.classList.add("hidden");
      chevron.style.transform = "rotate(0deg)";
    }
  };

  const menuBtn = container.querySelector<HTMLButtonElement>("#menu-btn")!;
  const menuDropdown = container.querySelector<HTMLDivElement>("#menu-dropdown")!;
  menuBtn.onclick = (e) => {
    e.stopPropagation();
    menuDropdown.classList.toggle("hidden");
  };

  const bindClick = (selector: string, handler: () => void) => {
    container.querySelectorAll<HTMLButtonElement>(selector).forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        menuDropdown.classList.add("hidden");
        handler();
      };
    });
  };

  bindClick("#menu-about-btn, #footer-about-btn", showAboutPopup);
  bindClick("#menu-privacy-btn, #footer-privacy-btn", showPrivacyPolicyPopup);
  bindClick("#menu-contact-btn, #footer-contact-btn", showContactPopup);
  bindClick("#menu-feedback-btn, #footer-feedback-btn", showFeedbackPopup);

  document.addEventListener("click", () => {
    menuDropdown.classList.add("hidden");
  });

  renderCookieConsent();
}

export function showAboutPopup(): void {
  const html = `
    <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-cyan-500 to-blue-500"></div>
    <h2 class="text-lg font-extrabold text-white tracking-wide text-center uppercase mb-3">About Us ℹ️</h2>
    <div class="space-y-4 text-xs text-gray-300 max-h-[65vh] overflow-y-auto pr-1 text-left leading-relaxed font-sans">
      <div class="space-y-1">
        <h3 class="font-bold text-cyan-300 uppercase tracking-wider">🌟 Our Mission</h3>
        <p class="text-gray-400">
          Word Antakshari Arena was created to elevate the beloved traditional word-chaining game into a modern, real-time multiplayer esports experience. Our platform brings word lovers together to compete, expand vocabulary, and test quick-thinking strategy under pressure.
        </p>
      </div>
      <div class="space-y-1 border-t border-white/5 pt-3">
        <h3 class="font-bold text-cyan-300 uppercase tracking-wider">🚀 Technology & Platform</h3>
        <p class="text-gray-400">
          Engineered with real-time Socket.IO synchronization, high-speed Redis state management, and modern Web Architecture to ensure instant turn transitions, live animated leaderboards, and seamless room re-connections.
        </p>
      </div>
      <div class="space-y-1 border-t border-white/5 pt-3">
        <h3 class="font-bold text-cyan-300 uppercase tracking-wider">👨‍💻 Founders & Developers</h3>
        <p class="text-gray-400">
          Designed and developed by <strong class="text-white">Krishna Dahipalle</strong> & <strong class="text-white">Rathod Arun</strong> with a dedication to fair play, responsive visual design, and continuous community updates.
        </p>
      </div>
      <button id="close-about-btn" class="w-full glass-button rounded-xl py-3 text-xs font-bold uppercase tracking-wider mt-4 cursor-pointer">Close</button>
    </div>
  `;
  const overlay = showOverlay("about-popup", html);
  overlay.querySelector<HTMLButtonElement>("#close-about-btn")!.onclick = () => {
    removeOverlay("about-popup");
  };
}

export function showPrivacyPolicyPopup(): void {
  const html = `
    <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 via-fuchsia-500 to-pink-500"></div>
    <h2 class="text-lg font-extrabold text-white tracking-wide text-center uppercase mb-3">Privacy Policy 🛡️</h2>
    <div class="space-y-4 text-xs text-gray-300 max-h-[65vh] overflow-y-auto pr-1 text-left leading-relaxed font-sans">
      <div class="space-y-1">
        <h3 class="font-bold text-violet-300 uppercase tracking-wider">1. Third-Party Advertising</h3>
        <p class="text-gray-400">
          Word Antakshari partners with third-party ad networks (including Adsterra and Google AdSense) to serve advertisements. These networks may use cookies, web beacons, and device identifiers to collect non-personally identifiable information during your visits to present relevant ads.
        </p>
      </div>
      <div class="space-y-1 border-t border-white/5 pt-3">
        <h3 class="font-bold text-violet-300 uppercase tracking-wider">2. Data Collection & Privacy</h3>
        <p class="text-gray-400">
          We collect minimal gameplay session data necessary to maintain real-time multiplayer room state (e.g. player display names, room scores, and session tokens). We do not harvest or sell your personal identity.
        </p>
      </div>
      <div class="space-y-1 border-t border-white/5 pt-3">
        <h3 class="font-bold text-violet-300 uppercase tracking-wider">3. Cookies & Local Storage</h3>
        <p class="text-gray-400">
          Local browser storage is used strictly for game state restoration (rejoining ongoing matches after reconnection) and remembering your cookie consent preferences.
        </p>
      </div>
      <div class="space-y-1 border-t border-white/5 pt-3">
        <h3 class="font-bold text-violet-300 uppercase tracking-wider">4. Contact & Inquiries</h3>
        <p class="text-gray-400">
          For privacy inquiries or data requests, contact us at: 
          <br/><a href="mailto:support.wordantakshari@gmail.com" class="text-violet-400 font-bold underline">support.wordantakshari@gmail.com</a>.
        </p>
      </div>
      <button id="close-privacy-btn" class="w-full glass-button rounded-xl py-3 text-xs font-bold uppercase tracking-wider mt-4 cursor-pointer">Close</button>
    </div>
  `;
  const overlay = showOverlay("privacy-popup", html);
  overlay.querySelector<HTMLButtonElement>("#close-privacy-btn")!.onclick = () => {
    removeOverlay("privacy-popup");
  };
}

export function showContactPopup(): void {
  const html = `
    <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-emerald-500 to-teal-500"></div>
    <h2 class="text-lg font-extrabold text-white tracking-wide text-center uppercase mb-3">Contact Support 📬</h2>
    <div class="space-y-4 text-xs text-gray-300 text-left leading-relaxed font-sans">
      <p class="text-gray-400">
        Have feedback, bug reports, or inquiries regarding advertising partnerships? Reach out directly to our team:
      </p>
      <div class="p-4 rounded-xl bg-white/5 border border-white/10 space-y-3">
        <div>
          <span class="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">Official Support & Inquiries</span>
          <a href="mailto:support.wordantakshari@gmail.com" class="text-emerald-400 font-bold underline text-sm">support.wordantakshari@gmail.com</a>
        </div>
      </div>
      <p class="text-[11px] text-gray-500 text-center">We typically respond to inquiries within 24–48 hours.</p>
      <button id="close-contact-btn" class="w-full glass-button rounded-xl py-3 text-xs font-bold uppercase tracking-wider mt-2 cursor-pointer">Close</button>
    </div>
  `;
  const overlay = showOverlay("contact-popup", html);
  overlay.querySelector<HTMLButtonElement>("#close-contact-btn")!.onclick = () => {
    removeOverlay("contact-popup");
  };
}

export function renderCookieConsent(): void {
  if (localStorage.getItem("cookie_consent") === "accepted") return;

  const existing = document.querySelector("#cookie-consent-banner");
  if (existing) return;

  const banner = document.createElement("div");
  banner.id = "cookie-consent-banner";
  banner.className = "fixed bottom-4 left-4 right-4 max-w-xl mx-auto glass-panel p-4 rounded-2xl border border-violet-500/30 z-50 shadow-2xl animate-slide-down flex flex-col md:flex-row items-center justify-between gap-3 text-left";
  banner.innerHTML = `
    <div class="text-xs text-gray-300 space-y-1">
      <p class="font-bold text-white flex items-center gap-1.5">
        <span>🍪</span> Cookie & Ad Consent Notice
      </p>
      <p class="text-[11px] text-gray-400 leading-relaxed">
        This site uses cookies & local storage for session functionality and ad personalization (Adsterra & Google AdSense). By continuing, you agree to our 
        <button id="cookie-privacy-link" class="text-violet-400 underline font-semibold hover:text-violet-300 cursor-pointer">Privacy Policy</button>.
      </p>
    </div>
    <button id="cookie-accept-btn" class="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 text-white font-extrabold text-xs uppercase tracking-wider rounded-xl transition-all shadow-md shrink-0 cursor-pointer">
      Accept & Continue
    </button>
  `;

  document.body.appendChild(banner);

  banner.querySelector("#cookie-accept-btn")!.addEventListener("click", () => {
    localStorage.setItem("cookie_consent", "accepted");
    banner.remove();
  });

  banner.querySelector("#cookie-privacy-link")!.addEventListener("click", () => {
    showPrivacyPolicyPopup();
  });
}

export function showFeedbackPopup(): void {
  const html = `
    <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-cyan-500 to-blue-500"></div>
    <h2 class="text-lg font-extrabold text-white tracking-wide text-center uppercase mb-3">Feedback 📋</h2>
    <form id="feedback-form" class="space-y-4 max-h-[70vh] overflow-y-auto px-1 text-left font-sans">
      <!-- Question 1 -->
      <div class="space-y-1">
        <label class="block text-xs font-medium text-gray-300">1. How would you rate the game speed & timers? ⏱️</label>
        <div class="flex gap-2" data-question="q1">
          ${[1,2,3,4,5].map(n => `<button type="button" data-value="${n}" class="rating-btn w-8 h-8 rounded-full border border-white/10 hover:border-cyan-500/50 hover:bg-cyan-500/10 text-xs font-bold text-gray-400 hover:text-white transition-all duration-200">${n}</button>`).join("")}
        </div>
      </div>
      <!-- Question 2 -->
      <div class="space-y-1">
        <label class="block text-xs font-medium text-gray-300">2. How fun are the steal challenge minigames? ⚔️</label>
        <div class="flex gap-2" data-question="q2">
          ${[1,2,3,4,5].map(n => `<button type="button" data-value="${n}" class="rating-btn w-8 h-8 rounded-full border border-white/10 hover:border-cyan-500/50 hover:bg-cyan-500/10 text-xs font-bold text-gray-400 hover:text-white transition-all duration-200">${n}</button>`).join("")}
        </div>
      </div>
      <!-- Question 3 -->
      <div class="space-y-1">
        <label class="block text-xs font-medium text-gray-300">3. How would you rate the guess word mechanic? 🔮</label>
        <div class="flex gap-2" data-question="q3">
          ${[1,2,3,4,5].map(n => `<button type="button" data-value="${n}" class="rating-btn w-8 h-8 rounded-full border border-white/10 hover:border-cyan-500/50 hover:bg-cyan-500/10 text-xs font-bold text-gray-400 hover:text-white transition-all duration-200">${n}</button>`).join("")}
        </div>
      </div>
      <!-- Question 4 -->
      <div class="space-y-1">
        <label class="block text-xs font-medium text-gray-300">4. How is the visual design & look of the game? 🎨</label>
        <div class="flex gap-2" data-question="q4">
          ${[1,2,3,4,5].map(n => `<button type="button" data-value="${n}" class="rating-btn w-8 h-8 rounded-full border border-white/10 hover:border-cyan-500/50 hover:bg-cyan-500/10 text-xs font-bold text-gray-400 hover:text-white transition-all duration-200">${n}</button>`).join("")}
        </div>
      </div>
      <!-- Question 5 -->
      <div class="space-y-1">
        <label class="block text-xs font-medium text-gray-300">5. Overall rating of Word Antakshari? 🌟</label>
        <div class="flex gap-2" data-question="q5">
          ${[1,2,3,4,5].map(n => `<button type="button" data-value="${n}" class="rating-btn w-8 h-8 rounded-full border border-white/10 hover:border-cyan-500/50 hover:bg-cyan-500/10 text-xs font-bold text-gray-400 hover:text-white transition-all duration-200">${n}</button>`).join("")}
        </div>
      </div>
      <!-- Comment -->
      <div class="space-y-1">
        <label class="block text-xs font-medium text-gray-300">What can we improve? ✍️</label>
        <textarea id="feedback-comment" placeholder="Your suggestions..." rows="2" class="w-full glass-input rounded-xl px-3 py-2 text-xs focus:outline-none placeholder:text-gray-600"></textarea>
      </div>
      <button type="submit" id="submit-feedback-btn" class="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white rounded-xl py-3 text-xs font-bold uppercase tracking-wider transition-all duration-200 mt-2">Submit Feedback 📬</button>
      <button type="button" id="close-feedback-btn" class="w-full glass-button rounded-xl py-3 text-xs font-bold uppercase tracking-wider mt-2">Cancel</button>
    </form>
  `;

  const overlay = showOverlay("feedback-popup", html);

  const ratings: Record<string, number> = { q1: 0, q2: 0, q3: 0, q4: 0, q5: 0 };

  overlay.querySelectorAll<HTMLButtonElement>(".rating-btn").forEach(btn => {
    btn.onclick = () => {
      const q = btn.parentElement!.dataset.question!;
      const val = Number(btn.dataset.value);
      ratings[q] = val;

      btn.parentElement!.querySelectorAll(".rating-btn").forEach(sibling => {
        sibling.className = "rating-btn w-8 h-8 rounded-full border border-white/10 hover:border-cyan-500/50 hover:bg-cyan-500/10 text-xs font-bold text-gray-400 hover:text-white transition-all duration-200";
      });

      btn.className = "rating-btn w-8 h-8 rounded-full border border-cyan-500 bg-cyan-500/20 text-xs font-bold text-cyan-300 transition-all duration-200";
    };
  });

  const feedbackForm = overlay.querySelector<HTMLFormElement>("#feedback-form")!;
  feedbackForm.onsubmit = (e) => {
    e.preventDefault();
    const comment = overlay.querySelector<HTMLTextAreaElement>("#feedback-comment")!.value.trim();

    connectSocket();
    socket.emit("submit_feedback", {
      ratings,
      comment,
    });

    feedbackForm.innerHTML = `
      <div class="text-center py-8 space-y-3 animate-pop-in">
        <p class="text-3xl">💖</p>
        <h4 class="text-sm font-bold text-white uppercase tracking-wider">Thank you!</h4>
        <p class="text-xs text-gray-400">Your feedback helps us make the game better.</p>
        <button type="button" id="close-after-feedback-btn" class="w-full glass-button rounded-xl py-3 text-xs font-bold uppercase tracking-wider mt-4">Close</button>
      </div>
    `;

    overlay.querySelector<HTMLButtonElement>("#close-after-feedback-btn")!.onclick = () => {
      removeOverlay("feedback-popup");
    };
  };

  overlay.querySelector<HTMLButtonElement>("#close-feedback-btn")!.onclick = () => {
    removeOverlay("feedback-popup");
  };
}

function renderWaitingRoom(container: HTMLElement): void {
  const state = getState();
  const room = state.roomState!;
  const myPlayer = room.players.find(p => p.player_id === state.playerState?.player_id);
  const isHost = myPlayer?.is_host ?? false;

  container.innerHTML = `
    <div class="max-w-xl mx-auto mt-12 p-4 md:p-8 space-y-8 animate-pop-in">
      <div class="glass-panel rounded-2xl p-6 md:p-8 space-y-6 relative overflow-hidden text-center">
        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 via-fuchsia-500 to-pink-500"></div>
        
        <div class="space-y-2">
          <p class="text-xs uppercase font-bold tracking-widest text-violet-400">Waiting Room</p>
          <h1 class="text-3xl md:text-4xl font-extrabold tracking-widest text-white">
            CODE: ${room.room_code}
          </h1>
          <p class="text-xs text-gray-400 font-medium">Mode: <span class="text-white capitalize">${room.mode}</span> | Turn Timer: <span class="text-white">${room.turn_timer_seconds}s</span></p>
        </div>

        <div class="space-y-3">
          <h3 class="text-xs font-bold uppercase tracking-wider text-left text-violet-300">Players Connected (${room.players.length}/8)</h3>
          <ul class="grid gap-3">
            ${room.players.map(p => `
              <li class="flex items-center justify-between bg-white/3 border border-white/5 rounded-xl px-4 py-3.5 hover:bg-white/5 transition-all duration-300">
                <span class="font-medium text-gray-200">${p.name} ${p.player_id === myPlayer?.player_id ? '<span class="text-xs text-violet-400 font-normal ml-1">(You)</span>' : ''}</span>
                ${p.is_host ? '<span class="text-[10px] bg-violet-500/20 text-violet-300 border border-violet-500/30 rounded-full px-2 py-0.5 font-bold uppercase tracking-wider">Host</span>' : '<span class="text-[10px] bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 rounded-full px-2 py-0.5 font-semibold">Ready</span>'}
              </li>
            `).join("")}
          </ul>
        </div>

        <!-- Edit Room Rules Button (Host Only) -->
        ${isHost ? `
          <div class="border-t border-white/5 pt-4 text-center">
            <button id="open-edit-settings-btn" class="w-full bg-violet-600/10 text-violet-300 border border-violet-500/20 hover:bg-violet-600/20 rounded-xl py-2 text-xs font-bold uppercase tracking-wider transition-all duration-300 cursor-pointer">
              ✏️ Edit Room Rules
            </button>
          </div>
        ` : ''}

        <div class="pt-4 space-y-4">
          ${isHost ? `
            <button id="start-btn"
              class="w-full glass-button rounded-xl py-3.5 text-xs font-bold uppercase tracking-wider disabled:opacity-50"
              ${room.players.length < 2 ? "disabled" : ""}>
              Start Match
            </button>
            ${room.players.length < 2 ? `<p class="text-[10px] text-pink-400 font-semibold tracking-wide">Waiting for at least one more player to join...</p>` : ''}
          ` : `
            <div class="flex items-center justify-center gap-3 py-2">
              <div class="w-2.5 h-2.5 bg-violet-500 rounded-full animate-ping"></div>
              <p class="text-sm text-gray-400 font-medium">Waiting for host to start the game...</p>
            </div>
          `}
        </div>

        <p id="waiting-error" class="text-red-400 text-sm font-medium mt-4 min-h-[20px]"></p>
      </div>

      <!-- Exit Button -->
      <button id="back-lobby-btn" class="px-4 py-2 rounded-xl border border-white/10 text-xs font-bold text-gray-400 hover:text-white transition-all duration-300 block mx-auto">
        ← Exit Arena (Back to Lobby)
      </button>
    </div>
  `;

  if (isHost) {
    container.querySelector<HTMLButtonElement>("#start-btn")!.onclick = () => {
      socket.emit("start_game", {});
    };

    container.querySelector<HTMLButtonElement>("#open-edit-settings-btn")!.onclick = () => {
      showEditSettingsOverlay(room);
    };
  }

  container.querySelector<HTMLButtonElement>("#back-lobby-btn")!.onclick = () => {
    socket.disconnect();
    resetState();
    connectSocket();
    import("./lobby").then(({ renderLobby }) => {
      showScreen(renderLobby);
    });
  };
}

function showEditSettingsOverlay(room: any): void {
  const html = `
    <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500 to-pink-500"></div>
    <h2 class="text-lg font-bold text-white tracking-wide text-center">Edit Room Rules</h2>
    <div class="space-y-4 my-4">
      <div>
        <label class="block text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">Mode</label>
        <select id="edit-mode" class="w-full glass-input rounded-xl px-3 py-2 text-xs focus:outline-none">
          <option value="endless" ${room.mode === "endless" ? "selected" : ""}>Endless Survival</option>
          <option value="rounds" ${room.mode === "rounds" ? "selected" : ""}>Rounds Classic</option>
        </select>
      </div>
      <div>
        <label class="block text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">Turn Timer (seconds)</label>
        <input id="edit-timer" type="number" min="5" max="300" value="${room.turn_timer_seconds}" class="w-full glass-input rounded-xl px-3 py-2 text-xs focus:outline-none" />
      </div>
      <div id="edit-round-limit-wrapper" class="${room.mode === 'rounds' ? '' : 'hidden'}">
        <label class="block text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">Round Limit (3-12)</label>
        <input id="edit-round-limit" type="number" min="3" max="12" value="${room.round_limit ?? 5}" class="w-full glass-input rounded-xl px-3 py-2 text-xs focus:outline-none" />
      </div>
    </div>
    <div class="flex gap-3">
      <button id="save-settings-btn" class="flex-1 glass-button rounded-xl py-3 text-xs font-bold uppercase tracking-wider">Save Rules</button>
      <button id="cancel-settings-btn" class="flex-1 bg-white/5 border border-white/10 text-gray-400 font-bold rounded-xl py-3 text-xs uppercase tracking-wider hover:bg-white/10 transition-all duration-300">Cancel</button>
    </div>
  `;
  const overlay = showOverlay("edit-settings", html);

  const editMode = overlay.querySelector<HTMLSelectElement>("#edit-mode")!;
  const editRoundLimitWrapper = overlay.querySelector<HTMLDivElement>("#edit-round-limit-wrapper")!;
  editMode.onchange = () => {
    if (editMode.value === "rounds") {
      editRoundLimitWrapper.classList.remove("hidden");
    } else {
      editRoundLimitWrapper.classList.add("hidden");
    }
  };

  overlay.querySelector<HTMLButtonElement>("#save-settings-btn")!.onclick = () => {
    const mode = editMode.value as "endless" | "rounds";
    const turn_timer_seconds = Number(overlay.querySelector<HTMLInputElement>("#edit-timer")!.value);
    const round_limit_raw = overlay.querySelector<HTMLInputElement>("#edit-round-limit")!.value;
    const payload: Record<string, unknown> = {
      mode,
      turn_timer_seconds,
    };
    if (mode === "rounds") {
      payload.round_limit = Number(round_limit_raw);
    }
    socket.emit("update_room_settings", payload);
    removeOverlay("edit-settings");
  };

  overlay.querySelector<HTMLButtonElement>("#cancel-settings-btn")!.onclick = () => {
    removeOverlay("edit-settings");
  };
}

// --- Socket listeners, registered once ---

socket.on("room_created", (data: RoomCreated) => {
  console.log("room_created event received:", data);
});

socket.on("reconnect_success", (data: ReconnectSuccess) => {
  setRoomState(data.room_state);
  setPlayerState(data.player_state);

  if (data.room_state.state === "in_progress") {
    import("./gameBoard").then(({ renderGameBoard }) => {
      showScreen(renderGameBoard);
    });
  } else {
    showScreen(renderLobby);
  }
});

socket.on("player_joined", (data: PlayerJoined) => {
  const state = getState();
  if (state.roomState) {
    const alreadyExists = state.roomState.players.some(p => p.player_id === data.player_id);
    if (!alreadyExists) {
      state.roomState.players.push(data.player);
      setRoomState(state.roomState);
    }
  }
  showScreen(renderLobby);
});

socket.on("player_left", (data: { player_id: string, host_player_id?: string }) => {
  const state = getState();
  if (state.roomState) {
    state.roomState.players = state.roomState.players.filter(p => p.player_id !== data.player_id);
    if (data.host_player_id) {
      state.roomState.players.forEach(p => {
        p.is_host = (p.player_id === data.host_player_id);
      });
    }
    setRoomState(state.roomState);
  }
  showScreen(renderLobby);
});

socket.on("room_settings_updated", (data: any) => {
  setRoomState(data);
  showScreen(renderLobby);
});

socket.on("error", (data: ErrorEvent) => {
  const errorEl = document.querySelector<HTMLParagraphElement>("#lobby-error, #waiting-error");
  if (errorEl) {
    errorEl.textContent = data.message;
    errorEl.className = "text-red-400 text-sm font-medium animate-shake";
    setTimeout(() => { errorEl.className = "text-red-400 text-sm font-medium"; }, 400);
  }
});