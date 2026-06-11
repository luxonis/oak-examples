import { Streams, useDaiConnection } from "@luxonis/depthai-viewer-common";
import {
  Component,
  FormEvent,
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

type BaselineField = {
  key: string;
  left: string;
  right: string;
};

type BaselinePath = {
  left: string;
  right: string;
};

type SocketOption = {
  socket: string;
  sensorName?: string;
  width?: number;
  height?: number;
  orientation?: string;
  supportedTypes?: string[] | string;
  hasAutofocus?: boolean;
  hasAutofocusIC?: boolean;
  name?: string;
  calibrationResolution?: string | null;
};

type PairStats = {
  label: string;
  left: string;
  right: string;
  baseline_cm: number;
  translation: number[];
  entered_baseline_cm?: number | null;
};

type FfcState = {
  ok: boolean;
  stage: "socket_select" | "baseline" | "calibrating" | "preview" | string;
  status: string;
  socketOptions: SocketOption[];
  selectedSockets: string[];
  baselineFields: BaselineField[];
  recommendedBaselineFields: BaselineField[];
  baselines: Record<string, number>;
  pairs: PairStats[];
  selectedPairIndex: number;
  flashStatus: string;
};

const emptyState: FfcState = {
  ok: false,
  stage: "socket_select",
  status: "Connecting to backend.",
  socketOptions: [],
  selectedSockets: [],
  baselineFields: [],
  recommendedBaselineFields: [],
  baselines: {},
  pairs: [],
  selectedPairIndex: 0,
  flashStatus: "",
};

function getDefaultWebsocketUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.hostname || "localhost";
  return `${protocol}://${host}:8766`;
}

function parseServiceResponse<T>(response: unknown): T {
  if (response instanceof DataView) {
    return JSON.parse(new TextDecoder().decode(response)) as T;
  }
  if (response instanceof ArrayBuffer) {
    return JSON.parse(new TextDecoder().decode(response)) as T;
  }
  return response as T;
}

class StreamErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error("Stream renderer failed", error);
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="stream-fallback">
          <strong>Streams failed</strong>
          <span>Stream renderer failed. Backend controls remain available.</span>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const connection = useDaiConnection();
  const [state, setState] = useState<FfcState>(emptyState);
  const [selectedSockets, setSelectedSockets] = useState<string[]>([]);
  const [baselinePaths, setBaselinePaths] = useState<BaselinePath[]>([]);
  const [baselineValues, setBaselineValues] = useState<Record<string, string>>({});
  const dai = (connection as any).daiConnection;
  const websocketUrl = new URLSearchParams(window.location.search).get("ws_url") ?? getDefaultWebsocketUrl();
  const baselineFields = baselinePaths.map((path) => ({
    ...path,
    key: `${path.left}__${path.right}`,
  }));
  const streamTopics = ["Dashboard", "Left", "Right", "Depth"];
  const selectedSocketSet = useMemo(() => new Set(state.selectedSockets), [state.selectedSockets]);
  const hasInvalidBaselinePaths = baselineFields.some(
    (field) =>
      field.left === field.right ||
      !selectedSocketSet.has(field.left) ||
      !selectedSocketSet.has(field.right),
  );
  const hasDuplicateBaselinePaths = new Set(
    baselineFields.map((field) => [field.left, field.right].sort().join("__")),
  ).size !== baselineFields.length;

  const selectedPair = useMemo(
    () => state.pairs[state.selectedPairIndex] ?? null,
    [state.pairs, state.selectedPairIndex],
  );

  const refreshState = useCallback(() => {
    dai?.postToService("FFC State", {}, (response: unknown) => {
      const nextState = parseServiceResponse<FfcState>(response);
      setState(nextState);
      setSelectedSockets((current) => {
        const available = new Set(nextState.socketOptions.map((socket) => socket.socket));
        const filtered = current.filter((socket) => available.has(socket));
        if (filtered.length > 0) {
          return filtered;
        }
        if (nextState.selectedSockets.length > 0) {
          return nextState.selectedSockets;
        }
        return nextState.socketOptions.map((socket) => socket.socket);
      });
      setBaselineValues((current) => {
        const merged = { ...current };
        for (const field of nextState.baselineFields) {
          if (merged[field.key] === undefined) {
            merged[field.key] = nextState.baselines[field.key]?.toString() ?? "";
          }
        }
        return merged;
      });
      setBaselinePaths((current) => {
        const backendPaths = nextState.baselineFields.map((field) => ({
          left: field.left,
          right: field.right,
        }));
        if (nextState.stage !== "baseline") {
          return backendPaths;
        }

        const selected = new Set(nextState.selectedSockets);
        const filtered = current.filter(
          (path) =>
            selected.has(path.left) &&
            selected.has(path.right) &&
            path.left !== path.right,
        );
        return filtered.length > 0 ? filtered : backendPaths;
      });
    });
  }, [dai]);

  useEffect(() => {
    if (!connection.connected) {
      setState({ ...emptyState, status: "Disconnected from backend." });
      return;
    }
    refreshState();
    const intervalMs = state.stage === "calibrating" ? 500 : state.stage === "preview" ? 1500 : 1000;
    const id = window.setInterval(refreshState, intervalMs);
    return () => window.clearInterval(id);
  }, [connection.connected, refreshState, state.stage]);

  const submitBaselines = (event: FormEvent) => {
    event.preventDefault();
    if (!connection.connected) {
      setState((current) => ({
        ...current,
        status: "Backend is not connected. Click Connect in any stream tile, or restart visualizer.py if connection fails.",
      }));
      return;
    }

    const payload: Record<string, number> = {};
    for (const field of baselineFields) {
      payload[field.key] = Number(baselineValues[field.key]);
    }
    dai?.postToService("FFC Set Baselines", { baselines: payload, paths: baselinePaths }, refreshState);
  };

  const submitSockets = () => {
    if (!connection.connected) {
      setState((current) => ({
        ...current,
        status: "Backend is not connected. Click Connect in any stream tile, or restart visualizer.py if connection fails.",
      }));
      return;
    }
    if (selectedSockets.length < 2) {
      setState((current) => ({
        ...current,
        status: "Select at least two sockets.",
      }));
      return;
    }
    dai?.postToService("FFC Set Sockets", { sockets: selectedSockets }, refreshState);
  };

  const resetRecommendedBaselines = () => {
    setBaselinePaths(
      state.recommendedBaselineFields.map((field) => ({
        left: field.left,
        right: field.right,
      })),
    );
  };

  const addBaselinePath = () => {
    const sockets = state.selectedSockets;
    if (sockets.length < 2) {
      return;
    }
    setBaselinePaths((current) => [
      ...current,
      { left: sockets[0], right: sockets.find((socket) => socket !== sockets[0]) ?? sockets[1] },
    ]);
  };

  const updateBaselinePath = (index: number, patch: Partial<BaselinePath>) => {
    setBaselinePaths((current) =>
      current.map((path, pathIndex) =>
        pathIndex === index ? { ...path, ...patch } : path,
      ),
    );
  };

  const removeBaselinePath = (index: number) => {
    setBaselinePaths((current) => current.filter((_, pathIndex) => pathIndex !== index));
  };

  const toggleSocket = (socket: string) => {
    setSelectedSockets((current) =>
      current.includes(socket)
        ? current.filter((entry) => entry !== socket)
        : [...current, socket],
    );
  };

  const selectPair = (index: number) => {
    dai?.postToService("FFC Select Pair", { index }, refreshState);
  };

  const flashCalibration = () => {
    dai?.postToService("FFC Flash Calibration", {}, refreshState);
  };

  return (
    <main className="app-shell">
      <section className="streams-panel">
        <StreamErrorBoundary>
          <Streams
            allowedTopics={streamTopics}
            defaultTopics={streamTopics}
            hideToolbar
            numberOfColumns={2}
            targetFps={10}
          />
        </StreamErrorBoundary>
      </section>

      <aside className="control-panel">
        <header>
          <h1>FFC Calibration</h1>
          <div className={`stage-pill stage-${state.stage}`}>{state.stage}</div>
        </header>

        <p className="status-text">{state.status}</p>

        {!connection.connected && (
          <div className="panel-section warning-panel">
            <h2>Backend Connection</h2>
            <p>Click Connect in any stream tile before starting calibration. If it does not connect, restart `visualizer.py`.</p>
            <code>{websocketUrl}</code>
          </div>
        )}

        {state.stage === "socket_select" && (
          <div className="panel-section">
            <h2>Detected Sockets</h2>
            {connection.connected && state.socketOptions.length === 0 && (
              <p>Waiting for connected camera sockets from backend.</p>
            )}
            <div className="socket-list">
              {state.socketOptions.map((socket) => {
                const checked = selectedSockets.includes(socket.socket);
                const supportedTypes = Array.isArray(socket.supportedTypes)
                  ? socket.supportedTypes.join(", ")
                  : socket.supportedTypes;
                return (
                  <label className={checked ? "socket-card selected" : "socket-card"} key={socket.socket}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleSocket(socket.socket)}
                    />
                    <span className="socket-main">
                      <strong>{socket.socket}</strong>
                      <span>{socket.sensorName || socket.name || "Unknown sensor"}</span>
                    </span>
                    <span className="socket-meta">
                      {socket.width && socket.height ? `${socket.width} x ${socket.height}` : "Resolution unknown"}
                    </span>
                    {socket.orientation && <span className="socket-detail">Orientation: {socket.orientation}</span>}
                    {supportedTypes && <span className="socket-detail">Types: {supportedTypes}</span>}
                    <span className="socket-detail">
                      AF: {socket.hasAutofocus ? "yes" : "no"} | AF IC: {socket.hasAutofocusIC ? "yes" : "no"}
                    </span>
                    {socket.calibrationResolution && (
                      <span className="socket-detail">Calibration: {socket.calibrationResolution}</span>
                    )}
                  </label>
                );
              })}
            </div>
            <button
              className="primary-button"
              type="button"
              onClick={submitSockets}
              disabled={!connection.connected || selectedSockets.length < 2}
            >
              {connection.connected ? "Continue to Baselines" : "Connect Backend First"}
            </button>
          </div>
        )}

        {state.stage === "baseline" && (
          <form className="panel-section" onSubmit={submitBaselines}>
            <h2>Baselines</h2>
            {connection.connected && state.selectedSockets.length < 2 && (
              <p>Waiting for connected camera sockets from backend.</p>
            )}
            {!connection.connected && (
              <p className="muted-text">Fill these now; start becomes available after backend connection.</p>
            )}
            <div className="path-section">
              <div className="path-header">
                <h3>Baseline Paths</h3>
                <button className="text-button" type="button" onClick={resetRecommendedBaselines}>
                  Use recommended
                </button>
              </div>
              <p className="muted-text">
                Recommended: {state.recommendedBaselineFields.map((field) => `${field.left} -> ${field.right}`).join(", ")}
              </p>
              <div className="path-list">
                {baselinePaths.map((path, index) => (
                  <div className="path-row" key={`${path.left}_${path.right}_${index}`}>
                    <select
                      value={path.left}
                      onChange={(event) => updateBaselinePath(index, { left: event.target.value })}
                    >
                      {state.selectedSockets.map((socket) => (
                        <option key={socket} value={socket}>{socket}</option>
                      ))}
                    </select>
                    <span>to</span>
                    <select
                      value={path.right}
                      onChange={(event) => updateBaselinePath(index, { right: event.target.value })}
                    >
                      {state.selectedSockets.map((socket) => (
                        <option key={socket} value={socket}>{socket}</option>
                      ))}
                    </select>
                    <button className="icon-button" type="button" onClick={() => removeBaselinePath(index)}>
                      Remove
                    </button>
                  </div>
                ))}
              </div>
              <button className="secondary-outline-button" type="button" onClick={addBaselinePath}>
                Add Baseline Link
              </button>
              {(hasInvalidBaselinePaths || hasDuplicateBaselinePaths) && (
                <p className="error-text">
                  Baseline links must use two different selected sockets and cannot be duplicated.
                </p>
              )}
            </div>
            {baselineFields.map((field) => (
              <label className="field-row" key={field.key}>
                <span>{field.left} to {field.right}</span>
                <input
                  type="number"
                  min="0.001"
                  step="0.001"
                  value={baselineValues[field.key] ?? ""}
                  onChange={(event) =>
                    setBaselineValues((current) => ({
                      ...current,
                      [field.key]: event.target.value,
                    }))
                  }
                />
              </label>
            ))}
            <button
              className="primary-button"
              type="submit"
              disabled={
                !connection.connected ||
                baselineFields.length === 0 ||
                hasInvalidBaselinePaths ||
                hasDuplicateBaselinePaths
              }
            >
              {connection.connected ? "Start Calibration" : "Connect Backend First"}
            </button>
          </form>
        )}

        {state.stage === "calibrating" && (
          <div className="panel-section">
            <h2>Capture</h2>
            <p>Watch the Dashboard tile for camera pose and capture progress.</p>
          </div>
        )}

        {state.pairs.length > 0 && (
          <div className="panel-section">
            <h2>Stereo Pairs</h2>
            <div className="pair-list">
              {state.pairs.map((pair, index) => (
                <button
                  className={index === state.selectedPairIndex ? "pair-button selected" : "pair-button"}
                  key={pair.label}
                  type="button"
                  onClick={() => selectPair(index)}
                >
                  <span>{pair.label}</span>
                  <strong>{pair.baseline_cm.toFixed(3)} cm</strong>
                </button>
              ))}
            </div>
          </div>
        )}

        {selectedPair && (
          <div className="panel-section compact">
            <h2>Displayed Pair</h2>
            <p>{selectedPair.label}</p>
            <code>
              [{selectedPair.translation.map((value) => value.toFixed(3)).join(", ")}]
            </code>
          </div>
        )}

        <div className="panel-section">
          <button className="secondary-button" type="button" onClick={flashCalibration} disabled={state.stage !== "preview"}>
            Flash Calibration
          </button>
          {state.flashStatus && <p className="flash-status">{state.flashStatus}</p>}
        </div>
      </aside>
    </main>
  );
}
