import { socket } from "../socket/connection";

const BANNER_ID = "connection-status-banner";

function showBanner(text: string, colorClass: string): void {
  removeBanner();
  const banner = document.createElement("div");
  banner.id = BANNER_ID;
  banner.className = `fixed top-0 left-0 right-0 text-center py-2 text-sm text-white z-50 ${colorClass}`;
  banner.textContent = text;
  document.body.appendChild(banner);
}

function removeBanner(): void {
  document.getElementById(BANNER_ID)?.remove();
}

socket.on("disconnect", () => {
  showBanner("Connection lost — trying to reconnect...", "bg-red-600");
});

socket.on("connect", () => {
  removeBanner();
});