// ClickCatcher.tsx
import { useEffect } from "react";
import { useDaiConnection } from "@luxonis/depthai-viewer-common";

const clamp = (v:number)=>Math.max(0, Math.min(1, v));

export function ClickCatcher({
  containerRef,
  frameWidth = 640,  
  frameHeight = 400,
  serviceName = "Selection Service",
  debug = false,
  allowedPanelTitle,
  onPointAdded,
}: {
  containerRef: React.RefObject<HTMLElement | null>;
  frameWidth?: number;
  frameHeight?: number;
  serviceName?: string;
  allowedPanelTitle?: string;
  debug?: boolean;
  onPointAdded?: (pointCount: number) => void;
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

      // Allow only if the panel text contains the expected title (e.g., "images" or "video")
      // Support multiple panel titles separated by comma
      const allowedTitles = allowedPanelTitle ? allowedPanelTitle.split(',').map(t => t.trim().toLowerCase()) : [];
      const isAllowed = allowedTitles.length === 0 || allowedTitles.some(title => panelText.includes(title));
      
      if (!isAllowed) {
        return;
      }

      const rect = media.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;

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
        return;
      }

      const nx = clamp((px - offX) / contentW);
      const ny = clamp((py - offY) / contentH);
      
      if (!daiConnection) {
        console.error(`[ClickCatcher] No daiConnection available!`);
        return;
      }
      
      (daiConnection as any)?.postToService(
        serviceName,
        { x: nx, y: ny },
        (resp:any) => {
          
          let parsedResp = resp;
          if (resp && resp.constructor && resp.constructor.name === 'DataView') {
            try {
              const decoder = new TextDecoder();
              const jsonString = decoder.decode(resp);
              parsedResp = JSON.parse(jsonString);
            } catch (e) {
              // If parsing fails, assume success for now
              parsedResp = { ok: true };
            }
          }
          
          if (parsedResp?.ok && onPointAdded) {
            // Since we can't get point count from service response, 
            // we'll let the parent component handle the count
            onPointAdded(-1); // Signal that a point was added
          } else {
            console.error(`[ClickCatcher] Service call failed. resp.ok:`, parsedResp?.ok, `onPointAdded:`, !!onPointAdded);
          }
        }
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
        (daiConnection as any)?.postToService(serviceName, { clear: true }, (resp: any) => {
          
          let parsedResp = resp;
          if (resp && resp.constructor && resp.constructor.name === 'DataView') {
            try {
              const decoder = new TextDecoder();
              const jsonString = decoder.decode(resp);
              parsedResp = JSON.parse(jsonString);
            } catch (e) {
              console.error(`[ClickCatcher] Error parsing clear DataView response:`, e);
              parsedResp = { ok: true };
            }
          }
          
          if (parsedResp?.ok && onPointAdded) {
            console.error(`[ClickCatcher] Clear successful, calling onPointAdded with count: 0`);
            onPointAdded(0);
          }
        });
    };

    host.addEventListener("click", onClick);
    host.addEventListener("contextmenu", onContextMenu);
    return () => {
      host.removeEventListener("click", onClick);
      host.removeEventListener("contextmenu", onContextMenu);
    };
  }, [containerRef, frameWidth, frameHeight, serviceName, debug, daiConnection, allowedPanelTitle, onPointAdded]);

  return null;
}
