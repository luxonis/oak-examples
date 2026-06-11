import "./styles.css";

function setDefaultWebsocketUrl(): void {
  const params = new URLSearchParams(window.location.search);
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const browserHost = window.location.hostname || "localhost";
  const inferredUrl = `${protocol}://${browserHost}:8766`;
  const configuredUrl = import.meta.env.VITE_DAI_WS_URL ?? inferredUrl;
  const currentUrl = params.get("ws_url");

  if (
    currentUrl &&
    currentUrl !== "ws://localhost:8765" &&
    currentUrl !== "ws://127.0.0.1:8765" &&
    !(browserHost !== "localhost" && browserHost !== "127.0.0.1" && currentUrl.includes("localhost"))
  ) {
    return;
  }

  params.set("ws_url", configuredUrl);
  const nextUrl = `${window.location.pathname}?${params.toString()}${window.location.hash}`;
  window.history.replaceState(null, "", nextUrl);
}

function renderFatalError(error: unknown): void {
  const root = document.getElementById("root");
  if (!root) {
    return;
  }

  const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
  const stack = error instanceof Error && error.stack ? error.stack : "";
  root.innerHTML = `
    <main class="fatal-error">
      <h1>FFC Calibration</h1>
      <p>The frontend failed before it could render.</p>
      <pre>${escapeHtml(message + (stack ? `\n\n${stack}` : ""))}</pre>
    </main>
  `;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

window.addEventListener("error", (event) => renderFatalError(event.error ?? event.message));
window.addEventListener("unhandledrejection", (event) => renderFatalError(event.reason));

setDefaultWebsocketUrl();

document.getElementById("root")!.innerHTML = `
  <main class="startup-screen">
    <h1>FFC Calibration</h1>
    <p>Loading frontend...</p>
  </main>
`;

import("./boot").catch(renderFatalError);
