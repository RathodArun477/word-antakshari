// Shared helper for popup-style overlays (guess popup, steal offers, challenge
// minigames, rejoin votes) — these float above the game board rather than
// replacing it, since #app is fully owned by the current screen.

export function showOverlay(id: string, html: string): HTMLDivElement {
  removeOverlay(id);

  const overlay = document.createElement("div");
  overlay.id = id;
  overlay.className = "fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-pop-in";
  overlay.innerHTML = `<div class="glass-panel rounded-2xl p-6 max-w-md w-full mx-4 relative overflow-hidden">${html}</div>`;
  document.body.appendChild(overlay);
  return overlay;
}

export function removeOverlay(id: string): void {
  document.getElementById(id)?.remove();
}