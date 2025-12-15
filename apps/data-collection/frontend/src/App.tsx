import { css } from "../styled-system/css/css.mjs";
import { Streams, useDaiConnection} from "@luxonis/depthai-viewer-common";
import { ClassSelector } from "./utils/classes/ClassSelector.tsx";
import { ConfidenceSlider } from "./utils/classes/ConfidenceSlider.tsx";
import { ImageUploader } from "./utils/classes/ImageUploader.tsx";
import { SnapConditionsPanel } from "./utils/conditions/SnapConditionsPanel.tsx";
import { useCallback, useEffect, useRef, useState, useMemo } from "react";
import { useToast } from "@luxonis/common-fe-components";

interface BackendConfig {
  classes: string[];
  confidence_threshold: number;
  snapping: {
    running: boolean;
    timed: { enabled: boolean; cooldown: number };
    noDetections: { enabled: boolean; cooldown: number };
    lowConfidence: { enabled: boolean; threshold: number; cooldown: number };
    lostMid: { enabled: boolean; cooldown: number; margin: number };
  };
}

function App() {
  const connection = useDaiConnection();
  const streamContainerRef = useRef<HTMLDivElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [currentRect, setCurrentRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [backendConfig, setBackendConfig] = useState<BackendConfig | null>(null);
  const [configLoaded, setConfigLoaded] = useState(false);
  const { toast } = useToast();
  const topicGroups = useMemo(() => ({ images: "Video" }), []);
  const allowedTopics = useMemo(() => ["Video"], []);

  const getUnderlyingMediaAndSize = () => {
    const container = streamContainerRef.current;
    if (!container) return null;
    const videoEl = container.querySelector("video") as HTMLVideoElement | null;
    const canvases = Array.from(container.querySelectorAll("canvas")) as HTMLCanvasElement[];
    const canvasEl = canvases.find((c) => c.getAttribute("data-role") !== "overlay") || null;
    const containerRect = container.getBoundingClientRect();
    if (videoEl && videoEl.videoWidth && videoEl.videoHeight) {
      const r = videoEl.getBoundingClientRect();
      const displayWidth = r.width;
      const displayHeight = r.height;
      const offsetX = r.left - containerRect.left;
      const offsetY = r.top - containerRect.top;
      return {
        type: "video" as const,
        el: videoEl,
        width: videoEl.videoWidth,
        height: videoEl.videoHeight,
        displayWidth,
        displayHeight,
        offsetX,
        offsetY,
      };
    }
    if (canvasEl && canvasEl.width && canvasEl.height) {
      const r = canvasEl.getBoundingClientRect();
      const displayWidth = r.width;
      const displayHeight = r.height;
      const offsetX = r.left - containerRect.left;
      const offsetY = r.top - containerRect.top;
      return {
        type: "canvas" as const,
        el: canvasEl,
        width: canvasEl.width,
        height: canvasEl.height,
        displayWidth,
        displayHeight,
        offsetX,
        offsetY,
      };
    }
    return null;
  };

  const finalizeBBox = useCallback(() => {
    if (!currentRect) return;
    const overlay = overlayCanvasRef.current;
    if (!overlay) return;
    const { x, y, w, h } = currentRect;
    if (w <= 0 || h <= 0) {
      setIsDrawing(false);
      setCurrentRect(null);
      setDragStart(null);
      const ctx = overlay.getContext("2d");
      if (ctx) ctx.clearRect(0, 0, overlay.width, overlay.height);
      toast({
        description: "Selection too small. Please draw a larger box.",
        colorVariant: "warning",
        duration: "default",
      });
      return;
    }

    const media = getUnderlyingMediaAndSize();
    if (!media) {
      toast({
      description: "No video/canvas found. Reset the view and try again.",
      colorVariant: "error",
      duration: "long",
    });
      return;
    }

    const overlayW = overlay.width;
    const overlayH = overlay.height;
    const srcW = media.width;
    const srcH = media.height;
    const mediaOffsetX = (media as any).offsetX ?? 0;
    const mediaOffsetY = (media as any).offsetY ?? 0;
    const mediaDispW = (media as any).displayWidth ?? overlayW;
    const mediaDispH = (media as any).displayHeight ?? overlayH;

    let contentX = mediaOffsetX;
    let contentY = mediaOffsetY;
    let contentW = mediaDispW;
    let contentH = mediaDispH;
    if (media.type === "canvas") {
      const side = Math.min(mediaDispW, mediaDispH);
      contentX = mediaOffsetX + (mediaDispW - side) / 2;
      contentY = mediaOffsetY + (mediaDispH - side) / 2;
      contentW = side;
      contentH = side;
    }

    const rx0 = Math.max(x, contentX);
    const ry0 = Math.max(y, contentY);
    const rx1 = Math.min(x + w, contentX + contentW);
    const ry1 = Math.min(y + h, contentY + contentH);
    const rw = Math.max(0, rx1 - rx0);
    const rh = Math.max(0, ry1 - ry0);
    if (rw <= 1 || rh <= 1) {
      toast({
        description: "Box outside of content area. Try again within the stream.",
        colorVariant: "warning",
        duration: "long",
      });
      return;
    }

    const scaleX = srcW / contentW;
    const scaleY = srcH / contentH;
    const sx0 = Math.max(0, Math.min(srcW - 1, Math.round((rx0 - contentX) * scaleX)));
    const sy0 = Math.max(0, Math.min(srcH - 1, Math.round((ry0 - contentY) * scaleY)));
    const sx1 = Math.max(0, Math.min(srcW, Math.round((rx1 - contentX) * scaleX)));
    const sy1 = Math.max(0, Math.min(srcH, Math.round((ry1 - contentY) * scaleY)));
    const sw = Math.max(1, sx1 - sx0);
    const sh = Math.max(1, sy1 - sy0);

    const xNorm = sx0 / srcW;
    const yNorm = sy0 / srcH;
    const wNorm = sw / srcW;
    const hNorm = sh / srcH;

    toast({
      description: 'Sending box [${xNorm.toFixed(2)}, ${yNorm.toFixed(2)}, ${wNorm.toFixed(2)}, ${hNorm.toFixed(2)}]',
      colorVariant: "gray",
      duration: "default",
    });

    (connection as any).daiConnection?.postToService(
      "BBox Prompt Service",
      {
        x: xNorm, y: yNorm, width: wNorm, height: hNorm
      },
      (resp: any) => {
        console.log("[BBox] Service ack:", resp);
        toast({
          description: "Bounding box sent",
          colorVariant: "success",
          duration: "default",
        });
      }
    );

    setIsDrawing(false);
    setCurrentRect(null);
    setDragStart(null);
    const ctx = overlay.getContext("2d");
    if (ctx) ctx.clearRect(0, 0, overlay.width, overlay.height);
  }, [connection, currentRect, toast]);

  const handleBeginBBoxDraw = useCallback(() => {
    setIsDrawing(true);
    setCurrentRect(null);
    setDragStart(null);
  }, []);

  useEffect(() => {
    if (!isDrawing) return;
    const container = streamContainerRef.current;
    const overlay = overlayCanvasRef.current;
    if (!container || !overlay) return;
    const sizeOverlay = () => {
      const rect = container.getBoundingClientRect();
      overlay.width = Math.max(1, Math.round(rect.width));
      overlay.height = Math.max(1, Math.round(rect.height));
      const ctx = overlay.getContext("2d");
      if (ctx) ctx.clearRect(0, 0, overlay.width, overlay.height);
    };
    sizeOverlay();
    window.addEventListener("resize", sizeOverlay);
    return () => window.removeEventListener("resize", sizeOverlay);
  }, [isDrawing]);

  useEffect(() => {
    toast({
      description: connection.connected ? "Connected to device" : "Disconnected from device",
      colorVariant: connection.connected ? "success" : "warning",
      duration: "default",
    });
  }, [connection.connected, toast]);

  // Fetch backend config on connection
  useEffect(() => {
    if (!connection.connected || configLoaded) return;

    const timeoutId = setTimeout(() => {
      console.log("[App] Fetching backend configuration...");
      (connection as any).daiConnection?.postToService(
        "Export Service",
        null,
        (response: any) => {
          if (response === null || response === undefined) {
            console.log("[App] Config service not available - using defaults");
            return;
          }

          let config: BackendConfig | null = null;
          try {
            let obj: any = response;
            const td = new TextDecoder('utf-8');
            const view = new Uint8Array(obj.buffer, obj.byteOffset, obj.byteLength);
            const jsonStr = td.decode(view);
            obj = JSON.parse(jsonStr);

            console.log("[App] Received payload:", obj);

            if (obj && obj.data && typeof obj.data === 'object') {
              obj = obj.data;
            }
            if (obj && typeof obj === 'object' && 'classes' in obj) {
              config = obj as BackendConfig;
            }
          } catch (e) {
            console.error('[App] Failed to parse service response:', e);
          }
          
          if (config && Array.isArray(config.classes) && typeof config.confidence_threshold === 'number') {
            setBackendConfig(config);
            setConfigLoaded(true);
            console.log("[App] Config restored from backend");
            toast({
              description: "Configuration restored from backend",
              colorVariant: "success",
              duration: "default",
            });
          } else {
            console.log("[App] Invalid config format - using defaults");
          }
        }
      );
    }, 1500);

    return () => clearTimeout(timeoutId);
  }, [connection.connected, configLoaded, toast]);

  // Reset config loaded flag when disconnected
  useEffect(() => {
    if (!connection.connected) {
      setConfigLoaded(false);
      setBackendConfig(null);
    }
  }, [connection.connected]);

  const onOverlayMouseDown = (e: any) => {
    if (!isDrawing) return;
    const canvas = overlayCanvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setDragStart({ x, y });
    setCurrentRect({ x, y, w: 0, h: 0 });
  };

  const onOverlayMouseMove = (e: any) => {
    if (!isDrawing || !dragStart) return;
    const canvas = overlayCanvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const x0 = Math.min(dragStart.x, x);
    const y0 = Math.min(dragStart.y, y);
    const w = Math.abs(x - dragStart.x);
    const h = Math.abs(y - dragStart.y);
    setCurrentRect({ x: x0, y: y0, w, h });

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#22c55e";
    ctx.lineWidth = 2;
    ctx.strokeRect(x0, y0, w, h);
  };

  const onOverlayMouseUp = () => {
    if (!isDrawing) return;
    finalizeBBox();
  };

  const SectionTitle = (props: { children: any }) => (
    <h2 className={css({ fontSize: "md", fontWeight: "semibold", mt: "xs", mb: "1" })}>{props.children}</h2>
  );

  return (
    <main
      className={css({
        width: "screen",
        height: "screen",
        display: "flex",
        flexDirection: "row",
        gap: "md",
        padding: "md",
      })}
    >
      <div className={css({ flex: 1, minWidth: 0, position: "relative", overflow: "hidden" })} ref={streamContainerRef}>
        <Streams
          allowedTopics={allowedTopics}
          defaultTopics={allowedTopics}
          topicGroups={topicGroups}
        />
        {isDrawing && (
          <canvas
            ref={overlayCanvasRef}
            data-role="overlay"
            className={css({ position: "absolute", inset: 0, cursor: "crosshair", zIndex: 10 })}
            onMouseDown={onOverlayMouseDown}
            onMouseMove={onOverlayMouseMove}
            onMouseUp={onOverlayMouseUp}
          />
        )}
      </div>

      {/* Vertical Divider */}
      <div className={css({ width: "2px", backgroundColor: "gray.300" })} />

      {/* Right: Sidebar — restored width */}
      <div
        className={css({
          width: "420px",
          minWidth: "340px",
          maxWidth: "520px",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          gap: "sm",
          overflowY: "auto",
          height: "100vh",
          pr: "sm",
        })}
      >
        <h1 className={css({ fontSize: "xl", fontWeight: "bold", mb: "1" })}>Data Collection</h1>
        <p className={css({ color: "gray.700", fontSize: "xs", lineHeight: "snug", mb: "sm" })}>
          Detect by name or example and auto-capture snaps based on conditions.
        </p>

        <SectionTitle>Labels by Text</SectionTitle>
        <p className={css({ fontSize: "xs", color: "gray.600", mb: "xs" })}>Enter labels to find (e.g., person, chair, TV).</p>
        <ClassSelector initialClasses={backendConfig?.classes} />

        <SectionTitle>Labels by Image</SectionTitle>
        <p className={css({ fontSize: "xs", color: "gray.600", mb: "xs" })}>Upload a photo or draw a box on the stream.</p>
        <ImageUploader onDrawBBox={handleBeginBBoxDraw} />

        <SectionTitle>Confidence Filter</SectionTitle>
        <p className={css({ fontSize: "xs", color: "gray.600", mb: "xs" })}>Detections below this confidence are dropped.</p>
        <ConfidenceSlider initialValue={backendConfig?.confidence_threshold ?? 0.40} />

        <div
          className={css({
            borderWidth: "1px",
            borderColor: "gray.200",
            rounded: "md",
            p: "sm",
            bg: "white",
            boxShadow: "xs",
          })}
        >
          <h2 className={css({ fontSize: "lg", fontWeight: "semibold", mb: "1" })}>Snap conditions</h2>
          <p className={css({ fontSize: "xs", color: "gray.600", mb: "sm", lineHeight: "snug" })}>Choose when to auto-capture a snap.</p>
          <SnapConditionsPanel initialConfig={backendConfig?.snapping} />
        </div>

        <div
          className={css({
            position: "sticky",
            bottom: 0,
            backgroundColor: "white",
            py: "xs",
            mt: "sm",
            borderTopWidth: "1px",
            borderColor: "gray.200",
            display: "flex",
            alignItems: "center",
            gap: "1",
            color: connection.connected ? "green.500" : "red.500",
          })}
        >
          <div className={css({ width: "2", height: "2", borderRadius: "full", backgroundColor: connection.connected ? "green.500" : "red.500", flexShrink: 0 })} />
          <span className={css({ whiteSpace: "nowrap", fontSize: "xs" })}>
            {connection.connected ? "Connected to device" : "Disconnected"}
          </span>
        </div>
      </div>
    </main>
  );
}

export default App;
