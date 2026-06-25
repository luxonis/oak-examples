import { Streams, useDaiConnection } from "@luxonis/depthai-viewer-common";
import {
  Component,
  FormEvent,
  MouseEvent,
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
  depthPreview?: {
    minDistanceMm: number;
    maxDistanceMm: number;
    probeMm: number | null;
    frameWidth: number;
    frameHeight: number;
  };
  streamTopics: string[];
};

type DepthPreviewState = NonNullable<FfcState["depthPreview"]>;

type SceneNode = {
  socket: string;
  x: number;
  y: number;
  z: number;
};

type SceneEdge = {
  left: string;
  right: string;
  signedDistance: number;
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
  depthPreview: {
    minDistanceMm: 300,
    maxDistanceMm: 5000,
    probeMm: null,
    frameWidth: 0,
    frameHeight: 0,
  },
  streamTopics: ["Dashboard", "Left", "Right", "Depth"],
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

function projectPoint(x: number, y: number, z: number) {
  return {
    x: 220 + x * 22 + z * 18,
    y: 208 - y * 20 - z * 10,
  };
}

function buildBaselineScene(
  sockets: string[],
  paths: BaselinePath[],
  baselineValues: Record<string, string>,
): { nodes: SceneNode[]; edges: SceneEdge[]; warnings: string[] } | null {
  if (sockets.length === 0 || paths.length === 0) {
    return null;
  }

  const uniqueSockets = Array.from(new Set(sockets));
  const positions = new Map<string, SceneNode>();
  const adjacency = new Map<string, Array<{ next: string; signedDistance: number }>>();
  const edges: SceneEdge[] = [];
  const warnings: string[] = [];

  for (const socket of uniqueSockets) {
    adjacency.set(socket, []);
  }

  for (const [index, path] of paths.entries()) {
    const key = `${path.left}__${path.right}`;
    const raw = baselineValues[key];
    const signedDistance = Number(raw);
    if (!Number.isFinite(signedDistance) || signedDistance === 0) {
      warnings.push(`Baseline ${path.left} -> ${path.right} must be a non-zero number.`);
      continue;
    }

    const strideZ = index % 2 === 0 ? 0 : 1;
    adjacency.get(path.left)?.push({ next: path.right, signedDistance });
    adjacency.get(path.right)?.push({ next: path.left, signedDistance: -signedDistance });
    edges.push({ left: path.left, right: path.right, signedDistance: signedDistance + strideZ * 0 });
  }

  if (edges.length === 0) {
    return null;
  }

  const root = uniqueSockets[0];
  positions.set(root, { socket: root, x: 0, y: 0, z: 0 });
  const queue = [root];
  const visited = new Set<string>([root]);

  while (queue.length > 0) {
    const socket = queue.shift()!;
    const base = positions.get(socket)!;
    const neighbors = adjacency.get(socket) ?? [];
    neighbors.forEach((neighbor, neighborIndex) => {
      const next = neighbor.next;
      const signedDistance = neighbor.signedDistance;
      const candidate: SceneNode = {
        socket: next,
        x: base.x + signedDistance,
        y: (visited.size % 2 === 0 ? 1 : -1) * (neighborIndex % 2 === 0 ? 0.6 : 1.2),
        z: base.z + (neighborIndex % 2 === 0 ? 0 : 1),
      };
      if (!positions.has(next)) {
        positions.set(next, candidate);
      } else {
        const current = positions.get(next)!;
        if (Math.abs(current.x - candidate.x) > 1e-6) {
          warnings.push(
            `Baseline graph is over-constrained around ${socket} and ${next}; preview uses the first solved position.`,
          );
        }
      }
      if (!visited.has(next)) {
        visited.add(next);
        queue.push(next);
      }
    });
  }

  for (const socket of uniqueSockets) {
    if (!positions.has(socket)) {
      positions.set(socket, { socket, x: 0, y: 0, z: 0 });
      warnings.push(`Socket ${socket} is disconnected in the preview graph.`);
    }
  }

  return {
    nodes: uniqueSockets.map((socket) => positions.get(socket)!),
    edges: edges.map((edge, index) => ({
      ...edge,
      signedDistance: Number(baselineValues[`${edge.left}__${edge.right}`]) || edge.signedDistance || index,
    })),
    warnings: Array.from(new Set(warnings)),
  };
}

function BaselineScenePreview({
  scene,
}: {
  scene: { nodes: SceneNode[]; edges: SceneEdge[]; warnings: string[] };
}) {
  const xValues = scene.nodes.map((node) => node.x);
  const minX = Math.min(...xValues);
  const maxX = Math.max(...xValues);
  const spread = Math.max(maxX - minX, 1);
  const normalizedNodes = scene.nodes.map((node) => ({
    ...node,
    x: ((node.x - minX) / spread) * 12 - 6,
  }));
  const nodesBySocket = new Map(normalizedNodes.map((node) => [node.socket, node]));

  return (
    <div style={{ marginTop: 16 }}>
      <div
        style={{
          border: "1px solid #d7dce4",
          borderRadius: 14,
          padding: 12,
          background: "linear-gradient(180deg, #f7faf8 0%, #eef3f7 100%)",
        }}
      >
        <svg viewBox="0 0 440 280" style={{ width: "100%", height: "auto", display: "block" }}>
          <defs>
            <marker id="baseline-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" fill="#1b7f5a" />
            </marker>
          </defs>
          <rect x="0" y="0" width="440" height="280" rx="18" fill="url(#scene-bg)" opacity="0" />
          <line x1="40" y1="230" x2="400" y2="230" stroke="#c4ced8" strokeWidth="2" />
          {scene.edges.map((edge) => {
            const left = nodesBySocket.get(edge.left);
            const right = nodesBySocket.get(edge.right);
            if (!left || !right) {
              return null;
            }
            const p0 = projectPoint(left.x, left.y, left.z);
            const p1 = projectPoint(right.x, right.y, right.z);
            const midX = (p0.x + p1.x) / 2;
            const midY = (p0.y + p1.y) / 2 - 18;
            return (
              <g key={`${edge.left}_${edge.right}`}>
                <line
                  x1={p0.x}
                  y1={p0.y}
                  x2={p1.x}
                  y2={p1.y}
                  stroke="#1b7f5a"
                  strokeWidth="4"
                  markerEnd="url(#baseline-arrow)"
                />
                <text
                  x={midX}
                  y={midY}
                  textAnchor="middle"
                  style={{ fontSize: 12, fontWeight: 700, fill: "#174c44" }}
                >
                  {edge.signedDistance.toFixed(3)} cm
                </text>
              </g>
            );
          })}
          {normalizedNodes.map((node) => {
            const p = projectPoint(node.x, node.y, node.z);
            return (
              <g key={node.socket}>
                <line x1={p.x} y1={p.y} x2={p.x} y2={230} stroke="#9ba9b7" strokeDasharray="4 4" />
                <circle cx={p.x} cy={p.y} r="16" fill="#213548" />
                <circle cx={p.x - 4} cy={p.y - 5} r="4" fill="#7fd6b0" />
                <text x={p.x} y={p.y + 32} textAnchor="middle" style={{ fontSize: 12, fontWeight: 700, fill: "#20303d" }}>
                  {node.socket}
                </text>
              </g>
            );
          })}
        </svg>
        <p style={{ margin: "8px 0 0", color: "#425466", fontSize: 13 }}>
          Negative baselines reverse the arrow direction by placing the destination camera on the opposite side of the source.
        </p>
        {scene.warnings.map((warning) => (
          <p key={warning} style={{ margin: "8px 0 0", color: "#8a5a00", fontSize: 13 }}>
            {warning}
          </p>
        ))}
      </div>
    </div>
  );
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

function DepthTileOverlay({
  dai,
  depthPreview,
  enabled,
}: {
  dai: any;
  depthPreview?: FfcState["depthPreview"];
  enabled: boolean;
}) {
  const [draftMin, setDraftMin] = useState((depthPreview?.minDistanceMm ?? 300) / 1000);
  const [draftMax, setDraftMax] = useState((depthPreview?.maxDistanceMm ?? 5000) / 1000);

  useEffect(() => {
    setDraftMin((depthPreview?.minDistanceMm ?? 300) / 1000);
    setDraftMax((depthPreview?.maxDistanceMm ?? 5000) / 1000);
  }, [depthPreview?.minDistanceMm, depthPreview?.maxDistanceMm]);

  const postRange = useCallback(
    (minMeters: number, maxMeters: number) => {
      if (!enabled) {
        return;
      }
      const minDistanceMm = Math.round(minMeters * 1000);
      const maxDistanceMm = Math.round(maxMeters * 1000);
      if (minDistanceMm >= maxDistanceMm) {
        return;
      }
      dai?.postToService("FFC Depth Range", { minDistanceMm, maxDistanceMm }, () => {});
    },
    [dai, enabled],
  );

  const handlePointerMove = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      if (!enabled) {
        return;
      }
      const containerRect = event.currentTarget.getBoundingClientRect();
      if (containerRect.width <= 0 || containerRect.height <= 0) {
        return;
      }
      const frameWidth = depthPreview?.frameWidth ?? 0;
      const frameHeight = depthPreview?.frameHeight ?? 0;
      let rect = containerRect;
      if (frameWidth > 0 && frameHeight > 0) {
        const frameAspect = frameWidth / frameHeight;
        const containerAspect = containerRect.width / containerRect.height;
        if (containerAspect > frameAspect) {
          const renderedWidth = containerRect.height * frameAspect;
          const padX = (containerRect.width - renderedWidth) * 0.5;
          rect = new DOMRect(
            containerRect.left + padX,
            containerRect.top,
            renderedWidth,
            containerRect.height,
          );
        } else {
          const renderedHeight = containerRect.width / frameAspect;
          const padY = (containerRect.height - renderedHeight) * 0.5;
          rect = new DOMRect(
            containerRect.left,
            containerRect.top + padY,
            containerRect.width,
            renderedHeight,
          );
        }
      }
      if (
        event.clientX < rect.left ||
        event.clientX > rect.right ||
        event.clientY < rect.top ||
        event.clientY > rect.bottom
      ) {
        dai?.postToService("FFC Depth Cursor", { x: null, y: null }, () => {});
        return;
      }
      const x = (event.clientX - rect.left) / rect.width;
      const y = (event.clientY - rect.top) / rect.height;
      dai?.postToService(
        "FFC Depth Cursor",
        {
          x,
          y,
          frameWidth: depthPreview?.frameWidth ?? 0,
          frameHeight: depthPreview?.frameHeight ?? 0,
        },
        () => {},
      );
    },
    [dai, depthPreview?.frameHeight, depthPreview?.frameWidth, enabled],
  );

  const clearPointer = useCallback(() => {
    dai?.postToService("FFC Depth Cursor", { x: null, y: null }, () => {});
  }, [dai]);

  const probeLabel =
    depthPreview?.probeMm && depthPreview.probeMm > 0
      ? `3x3 ROI: ${(depthPreview.probeMm / 1000).toFixed(3)} m`
      : "3x3 ROI: invalid";

  return (
    <div
      className="depth-overlay-hitbox"
      onMouseMove={handlePointerMove}
      onMouseLeave={clearPointer}
    >
      <div className="depth-overlay-readout">{probeLabel}</div>
      <div
        className="depth-range-panel"
        onMouseMove={(event) => event.stopPropagation()}
        onMouseLeave={(event) => event.stopPropagation()}
      >
        <div className="depth-range-title">Depth window</div>
        <label>
          <span>Min: {draftMin.toFixed(1)} m</span>
          <input
            type="range"
            min={0.1}
            max={10}
            step={0.1}
            value={draftMin}
            onChange={(event) => {
              const nextMin = Number(event.target.value);
              const clamped = Math.min(nextMin, draftMax - 0.1);
              setDraftMin(clamped);
              postRange(clamped, draftMax);
            }}
          />
        </label>
        <label>
          <span>Max: {draftMax.toFixed(1)} m</span>
          <input
            type="range"
            min={0.2}
            max={15}
            step={0.1}
            value={draftMax}
            onChange={(event) => {
              const nextMax = Number(event.target.value);
              const clamped = Math.max(nextMax, draftMin + 0.1);
              setDraftMax(clamped);
              postRange(draftMin, clamped);
            }}
          />
        </label>
      </div>
    </div>
  );
}

export default function App() {
  const connection = useDaiConnection();
  const [state, setState] = useState<FfcState>(emptyState);
  const [selectedSockets, setSelectedSockets] = useState<string[]>([]);
  const [baselinePaths, setBaselinePaths] = useState<BaselinePath[]>([]);
  const [baselineValues, setBaselineValues] = useState<Record<string, string>>({});
  const [showBaselineScene, setShowBaselineScene] = useState(false);
  const dai = (connection as any).daiConnection;
  const websocketUrl = new URLSearchParams(window.location.search).get("ws_url") ?? getDefaultWebsocketUrl();
  const baselineFields = baselinePaths.map((path) => ({
    ...path,
    key: `${path.left}__${path.right}`,
  }));
  const streamTopics = state.streamTopics.length > 0 ? state.streamTopics : ["Dashboard", "Left", "Right", "Depth"];
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
  const baselineScene = useMemo(
    () => buildBaselineScene(state.selectedSockets, baselinePaths, baselineValues),
    [state.selectedSockets, baselinePaths, baselineValues],
  );

  const selectedPair = useMemo(
    () => state.pairs[state.selectedPairIndex] ?? null,
    [state.pairs, state.selectedPairIndex],
  );
  const depthPreview = state.depthPreview ?? emptyState.depthPreview;
  const topicOverlays = useMemo(
    () =>
      new Map<string, ReactNode>([
        [
          "Depth",
          <DepthTileOverlay
            key="depth-overlay"
            dai={dai}
            depthPreview={depthPreview}
            enabled={streamTopics.includes("Depth")}
          />,
        ],
      ]),
    [dai, depthPreview, streamTopics],
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
            selected.has(path.right),
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
    if (state.stage === "preview") {
      return;
    }
    const intervalMs = state.stage === "calibrating" ? 500 : 1000;
    const id = window.setInterval(refreshState, intervalMs);
    return () => window.clearInterval(id);
  }, [connection.connected, refreshState, state.stage]);

  useEffect(() => {
    if (!connection.connected || state.stage !== "preview") {
      return;
    }
    const refreshDepthState = () => {
      dai?.postToService("FFC Depth State", {}, (response: unknown) => {
        const nextDepthState = parseServiceResponse<DepthPreviewState & { ok?: boolean }>(response);
        setState((current) => ({
          ...current,
          depthPreview: nextDepthState.ok === false
            ? current.depthPreview
            : {
                minDistanceMm: nextDepthState.minDistanceMm,
                maxDistanceMm: nextDepthState.maxDistanceMm,
                probeMm: nextDepthState.probeMm ?? null,
                frameWidth: nextDepthState.frameWidth ?? 0,
                frameHeight: nextDepthState.frameHeight ?? 0,
              },
        }));
      });
    };
    refreshDepthState();
    const id = window.setInterval(refreshDepthState, 150);
    return () => window.clearInterval(id);
  }, [connection.connected, dai, state.stage]);

  const submitBaselines = (event: FormEvent) => {
    event.preventDefault();
    if (!connection.connected) {
      setState((current) => ({
        ...current,
        status: "Backend is not connected. Click Connect in any stream tile, or restart visualizer.py if connection fails.",
      }));
      return;
    }
    if (hasInvalidBaselinePaths || hasDuplicateBaselinePaths) {
      setState((current) => ({
        ...current,
        status: "Fix duplicate baseline links and links that use the same socket before starting calibration.",
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
    dai?.postToService("FFC Flash Calibration", { confirm: true }, refreshState);
  };

  const navigateToStage = (stage: "socket_select" | "baseline") => {
    dai?.postToService("FFC Navigate", { stage }, refreshState);
  };

  const closeWindow = () => {
    window.close();
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
            topicOverlayMap={topicOverlays as Map<any, any>}
            targetFps={30}
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
            <div className="action-stack">
              <button
                className="primary-button"
                type="button"
                onClick={submitSockets}
                disabled={!connection.connected || selectedSockets.length < 2}
              >
                {connection.connected ? "Continue to Baselines" : "Connect Backend First"}
              </button>
              <button className="secondary-button" type="button" onClick={closeWindow}>
                Close
              </button>
            </div>
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
                  min={undefined}
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
              className="secondary-outline-button"
              type="button"
              onClick={() => setShowBaselineScene((current) => !current)}
              disabled={baselineFields.length === 0}
            >
              {showBaselineScene ? "Hide 3D Scenery" : "Generate 3D Scenery"}
            </button>
            {showBaselineScene && baselineScene && <BaselineScenePreview scene={baselineScene} />}
            <div className="action-stack">
              <button
                className="primary-button"
                type="submit"
                disabled={
                  !connection.connected ||
                  baselineFields.length === 0
                }
              >
                {connection.connected ? "Start Calibration" : "Connect Backend First"}
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={() => navigateToStage("socket_select")}
                disabled={!connection.connected}
              >
                Back to Socket Selection
              </button>
              <button className="secondary-button" type="button" onClick={closeWindow}>
                Close
              </button>
            </div>
          </form>
        )}

        {state.stage === "calibrating" && (
          <div className="panel-section">
            <h2>Capture</h2>
            <p>Watch the Dashboard tile for camera pose and capture progress.</p>
            <div className="action-stack">
              <button
                className="secondary-button"
                type="button"
                onClick={() => navigateToStage("baseline")}
                disabled={!connection.connected}
              >
                Back to Baselines
              </button>
              <button className="secondary-button" type="button" onClick={closeWindow}>
                Close
              </button>
            </div>
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
          <div className="action-stack">
            {state.stage === "preview" && (
              <>
                <button className="secondary-button" type="button" onClick={flashCalibration}>
                  Flash Calibration
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => navigateToStage("socket_select")}
                  disabled={!connection.connected}
                >
                  Back to Start
                </button>
                <button className="secondary-button" type="button" onClick={closeWindow}>
                  Close
                </button>
              </>
            )}
          </div>
          {state.flashStatus && <p className="flash-status">{state.flashStatus}</p>}
        </div>
      </aside>
    </main>
  );
}
