import { css } from "../styled-system/css/css.mjs";
import { Streams, useConnection } from "@luxonis/depthai-viewer-common";
import { ClassSelector } from "./ClassSelector.tsx";
import { ConfidenceSlider } from "./ConfidenceSlider.tsx";
import { ImageUploader } from "./ImageUploader.tsx";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNotifications } from "./Notifications.tsx";

function App() {
    const connection = useConnection();
    const streamContainerRef = useRef<HTMLDivElement>(null);
    const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
    const [isDrawing, setIsDrawing] = useState(false);
    const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
    const [currentRect, setCurrentRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
    const { notify } = useNotifications();

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
            console.log("[BBox] Capturing from video element", { width: videoEl.videoWidth, height: videoEl.videoHeight, displayWidth, displayHeight, offsetX, offsetY });
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
            console.log("[BBox] Capturing from canvas element", { width: canvasEl.width, height: canvasEl.height, displayWidth, displayHeight, offsetX, offsetY });
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
            notify('Selection too small. Please draw a larger box.', { type: 'warning' });
            return;
        }

        // Map overlay-space bbox to source frame using displayed media rect
        const media = getUnderlyingMediaAndSize();
        if (!media) {
            console.warn("[BBox] No media found under overlay; aborting bbox post");
            notify('No video/canvas found. Reset the view and try again.', { type: 'error', durationMs: 6000 });
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
            console.warn("[BBox] BBox outside content area; aborting");
            notify('Box outside of content area. Try again within the stream.', { type: 'warning', durationMs: 6000 });
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

        console.log("[BBox] Posting BBox Prompt Service (normalized source)", {
            bbox: { x: xNorm, y: yNorm, width: wNorm, height: hNorm },
            src: { width: srcW, height: srcH },
            overlay: { width: overlayW, height: overlayH },
            display: { width: mediaDispW, height: mediaDispH, offsetX: mediaOffsetX, offsetY: mediaOffsetY },
            content: { x: contentX, y: contentY, width: contentW, height: contentH },
            scales: { scaleX, scaleY }
        });
        notify(
            `Sending box [${xNorm.toFixed(2)}, ${yNorm.toFixed(2)}, ${wNorm.toFixed(2)}, ${hNorm.toFixed(2)}]`,
            { type: 'info' }
        );
        // @ts-ignore - Custom service
        (connection as any).daiConnection?.postToService(
            "BBox Prompt Service",
            {
                filename: "object.png",
                type: "application/json",
                data: null,
                bbox: { x: xNorm, y: yNorm, width: wNorm, height: hNorm },
                bboxType: "normalized",
                label: "object"
            },
            (resp: any) => {
                console.log("[BBox] Service ack:", resp);
                notify('Bounding box sent', { type: 'success' });
            }
        );

        setIsDrawing(false);
        setCurrentRect(null);
        setDragStart(null);
        const ctx = overlay.getContext("2d");
        if (ctx) ctx.clearRect(0, 0, overlay.width, overlay.height);
    }, [connection, currentRect]);

    const handleBeginBBoxDraw = useCallback(() => {
        console.log("[BBox] Begin drawing requested");
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
            console.log("[BBox] Overlay sized", { width: overlay.width, height: overlay.height });
        };
        sizeOverlay();
        window.addEventListener("resize", sizeOverlay);
        return () => window.removeEventListener("resize", sizeOverlay);
    }, [isDrawing]);

    useEffect(() => {
        notify(connection.connected ? 'Connected to device' : 'Disconnected from device', { type: connection.connected ? 'success' : 'warning', durationMs: 1800 });
        // eslint-disable-next-line react-hooks/exhaustive-deps
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
        console.log("[BBox] Mouse down", { x, y });
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
        ctx.strokeStyle = "#22c55e"; // green
        ctx.lineWidth = 2;
        ctx.strokeRect(x0, y0, w, h);
        if ((w * h) % 20 === 0) {
            console.log("[BBox] Mouse move bbox", { x: x0, y: y0, w, h });
        }
    };

    const onOverlayMouseUp = () => {
        if (!isDrawing) return;
        console.log("[BBox] Mouse up, finalizing bbox", currentRect);
        finalizeBBox();
    };

    return (
        <main className={css({
            width: 'screen',
            height: 'screen',
            display: 'flex',
            flexDirection: 'row',
            gap: 'md',
            padding: 'md'
        })}>
            {/* Left: Stream Viewer */}
            <div className={css({ flex: 1, position: 'relative' })} ref={streamContainerRef}>
                <Streams />
                {isDrawing && (
                    <canvas
                        ref={overlayCanvasRef}
                        data-role="overlay"
                        className={css({ position: 'absolute', inset: 0, cursor: 'crosshair', zIndex: 10 })}
                        onMouseDown={onOverlayMouseDown}
                        onMouseMove={onOverlayMouseMove}
                        onMouseUp={onOverlayMouseUp}
                    />
                )}
            </div>

            {/* Vertical Divider */}
            <div className={css({
                width: '2px',
                backgroundColor: 'gray.300'
            })} />

            {/* Right: Sidebar (Info and Controls) */}
            <div className={css({
                width: 'md',
                display: 'flex',
                flexDirection: 'column',
                gap: 'md'
            })}>
                <h1 className={css({ fontSize: '2xl', fontWeight: 'bold' })}>
                    Dynamic YOLO-World/YOLOE Example
                </h1>
                <p>
                    This example showcases the integration of the YOLO-World/YOLOE model with a custom static frontend,
                    enabling dynamic configuration of the object classes you want to detect at runtime.
                </p>

                {/* Class Input */}
                <ClassSelector />

                {/* Image Uploader */}
                <ImageUploader onDrawBBox={handleBeginBBoxDraw} />

                {/* Confidence Slider */}
                <ConfidenceSlider initialValue={0.1} />

                {/* Connection Status */}
                <div className={css({
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'xs',
                    marginTop: 'auto',
                    color: connection.connected ? 'green.500' : 'red.500'
                })}>
                    <div className={css({
                        width: '3',
                        height: '3',
                        borderRadius: 'full',
                        backgroundColor: connection.connected ? 'green.500' : 'red.500'
                    })} />
                    <span>{connection.connected ? 'Connected to device' : 'Disconnected'}</span>
                </div>
            </div>
        </main>
    );
}

export default App;
