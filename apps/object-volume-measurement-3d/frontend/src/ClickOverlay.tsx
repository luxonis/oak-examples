// ClickCatcher.tsx
import { useEffect } from "react";
import { useDaiConnection } from "@luxonis/depthai-viewer-common";

const clamp = (v:number)=>Math.max(0, Math.min(1, v));

export function ClickCatcher({
  containerRef,
  frameWidth = 640,        // <-- required: the stream’s image size
  frameHeight = 640,
  serviceName = "Selection Service",
  debug = false,
  allowedPanelTitle, 
}: {
  containerRef: React.RefObject<HTMLElement | null>;
  frameWidth?: number;
  frameHeight?: number;
  serviceName?: string;
  allowedPanelTitle?: string;
  debug?: boolean;
}) {
  const { daiConnection } = useDaiConnection();

  useEffect(() => {
    const host = containerRef.current;
    if (!host) return;

    const onClick = (e: MouseEvent) => {
      // ignore toolbar/buttons
      const path = (e.composedPath?.() || []) as HTMLElement[];
      if (path.some(el => el?.closest?.('button,[role="button"]'))) return;

      // find the media element (canvas/video/img)
      const media = path.find(
        (el) =>
          el instanceof HTMLCanvasElement ||
          el instanceof HTMLVideoElement ||
          el instanceof HTMLImageElement
      ) as HTMLCanvasElement | HTMLVideoElement | HTMLImageElement | undefined;

      if (!media) return;

      // The Streams panel name is embedded in the nearest <section>'s text, e.g. "Video(640x640)" or "Pointclouds3D"
      const panel = media.closest("section") as HTMLElement | null;
      const panelText = panel?.textContent?.trim().toLowerCase() ?? "";

      if (debug) {
        console.log("[ClickCatcher] panelText:", panelText);
        console.log("[ClickCatcher] allowedPanelTitle:", allowedPanelTitle);
      }

      // Allow only if the panel text contains the expected title (e.g., "images" or "video")
      if (allowedPanelTitle && !panelText.includes(allowedPanelTitle.toLowerCase())) {
        if (debug) console.log("ignored: panel text mismatch");
        return;
      }

      const looks3D =
        media instanceof HTMLCanvasElement &&
        (media.hasAttribute("data-camera-controls-version") ||
        getComputedStyle(media).touchAction === "none");

      if (looks3D) {
        if (debug) console.log("ignored: 3D/Pointcloud canvas");
        return;
      }

      const rect = media.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;

      // ---- compute letterboxed content box from KNOWN frame aspect ----
      const ar = frameWidth / frameHeight;
      const boxAr = rect.width / rect.height;

      let contentW: number, contentH: number, offX = 0, offY = 0;
      if (boxAr > ar) {
        // bars left/right
        contentH = rect.height;
        contentW = contentH * ar;
        offX = (rect.width - contentW) / 2;
      } else {
        // bars top/bottom
        contentW = rect.width;
        contentH = contentW / ar;
        offY = (rect.height - contentH) / 2;
      }

      // ignore clicks in gray bars
      if (px < offX || px > offX + contentW || py < offY || py > offY + contentH) {
        if (debug) console.log("ignored letterbox click");
        return;
      }

      const nx = clamp((px - offX) / contentW);
      const ny = clamp((py - offY) / contentH);

      if (debug) console.log("norm(image only):", { nx, ny });

      (daiConnection as any)?.postToService(
        serviceName,
        { x: nx, y: ny },
        (resp:any) => debug && console.log("ack:", resp)
      );
    };

    const onContextMenu = (e: MouseEvent) => {
      const path = (e.composedPath?.() || []) as HTMLElement[];
      const onMedia = path.some(
        (el) =>
          el instanceof HTMLCanvasElement ||
          el instanceof HTMLVideoElement ||
          el instanceof HTMLImageElement
      );
      if (!onMedia) return;
      e.preventDefault();
      (daiConnection as any)?.postToService(serviceName, { clear: true });
    };

    host.addEventListener("click", onClick);
    host.addEventListener("contextmenu", onContextMenu);
    return () => {
      host.removeEventListener("click", onClick);
      host.removeEventListener("contextmenu", onContextMenu);
    };
  }, [containerRef, frameWidth, frameHeight, serviceName, debug, daiConnection, allowedPanelTitle]);

  return null;
}
