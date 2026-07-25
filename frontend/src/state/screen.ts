export type ScreenRenderer = (container: HTMLElement) => void;

const appContainer = document.querySelector<HTMLDivElement>("#app")!;

export function showScreen(renderFn: ScreenRenderer): void {
  appContainer.innerHTML = "";
  renderFn(appContainer);
}