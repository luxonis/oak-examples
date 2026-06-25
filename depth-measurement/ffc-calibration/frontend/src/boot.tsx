import { StrictMode } from "react";
import { Component, ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { DepthAIContext } from "@luxonis/depthai-viewer-common";
import "@luxonis/depthai-viewer-common/styles";
import App from "./App";

function getBasePath(): string {
  return window.location.pathname.match(/^\/\d+\.\d+\.\d+\/$/)?.[0] ?? "";
}

class AppErrorBoundary extends Component<{ children: ReactNode }, { error: unknown }> {
  state = { error: null };

  static getDerivedStateFromError(error: unknown) {
    return { error };
  }

  componentDidCatch(error: unknown) {
    console.error("FFC frontend failed", error);
  }

  render() {
    if (this.state.error) {
      return (
        <main className="fatal-error">
          <h1>FFC Calibration</h1>
          <p>The frontend failed while rendering.</p>
          <pre>{String(this.state.error)}</pre>
        </main>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppErrorBoundary>
      <BrowserRouter basename={getBasePath()}>
        <DepthAIContext
          activeServices={[
            "FFC State",
            "FFC Set Sockets",
            "FFC Set Baselines",
            "FFC Select Pair",
          ] as any}
        >
          <App />
        </DepthAIContext>
      </BrowserRouter>
    </AppErrorBoundary>
  </StrictMode>,
);
