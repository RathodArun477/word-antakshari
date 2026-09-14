import "./style.css";
import { connectSocket, socket } from "./socket/connection";
import { showScreen } from "./state/screen";
import { renderLobby } from "./ui/lobby";
import { getSavedSession } from "./state/gameState";
import { renderHowToPlay } from "./ui/howToPlay";
import "./ui/gameBoard";
import "./ui/guessPopup";
import "./ui/powerups";
import "./ui/rejoinVote";
import "./state/connectionStatus";

connectSocket();

const app = document.querySelector<HTMLDivElement>("#app");

if (window.location.pathname === "/how-to-play") {
  if (app) {
    renderHowToPlay(app);
  }
} else {
  showScreen(renderLobby);
}

socket.on("connect", () => {
  const saved = getSavedSession();
  if (saved) {
    socket.emit("reconnect", saved);
  }
});

import { setPlayerState } from "./state/gameState";
import type { PlayerStateSnapshot } from "./types/contract";

socket.on("player_state_update", (data: PlayerStateSnapshot) => {
  if (window.location.pathname === "/how-to-play") {
    return;
  }
  setPlayerState(data);
  const app = document.querySelector<HTMLDivElement>("#app");
  if (app && document.querySelector("#word-input")) {
    import("./ui/gameBoard").then(({ renderGameBoard }) => {
      renderGameBoard(app);
    });
  }
});

import { setRoomState } from "./state/gameState";
import type { RoomStateSnapshot } from "./types/contract";

socket.on("room_state_update", (data: RoomStateSnapshot) => {
  if (window.location.pathname === "/how-to-play") {
    return;
  }
  setRoomState(data);
  const app = document.querySelector<HTMLDivElement>("#app");
  if (app) {
    // If the leaderboard is showing (leave-lobby button present), don't disrupt it unless a rematch is starting (state === "waiting")
    if (document.querySelector("#leave-lobby-btn") && data.state !== "waiting") {
      return;
    }
    if (document.querySelector("#word-input")) {
      import("./ui/gameBoard").then(({ renderGameBoard }) => {
        renderGameBoard(app);
      });
    } else {
      import("./ui/lobby").then(({ renderLobby }) => {
        renderLobby(app);
      });
    }
  }
});