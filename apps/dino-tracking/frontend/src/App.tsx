import { css } from "../styled-system/css/css.mjs";
import { Streams, useConnection } from "@luxonis/depthai-viewer-common";
import { AnnotationModeSelector } from "./AnnotationModeSelector.tsx";
import { OutlinesToggle } from "./OutlinesToggle.tsx";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNotifications } from "./Notifications.tsx";
import { Button } from "@luxonis/common-fe-components";

function App() {
    const connection = useConnection();
    const streamContainerRef = useRef<HTMLDivElement>(null);
    const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
    const [isDrawing, setIsDrawing] = useState(false);
    const [currentCoord, setCurrentCoord] = useState<{ x: number; y: number } | null>(
        null
    );
    const { notify } = useNotifications();

    const getUnderlyingMediaAndSize = () => {
        const container = streamContainerRef.current;
        if (!container) return null;

        const videoEl = container.querySelector("video") as HTMLVideoElement | null;
        const canvases = Array.from(
            container.querySelectorAll("canvas")
        ) as HTMLCanvasElement[];
        const canvasEl =
            canvases.find((c) => c.getAttribute("data-role") !== "overlay") || null;
        const containerRect = container.getBoundingClientRect();

        if (videoEl && videoEl.videoWidth && videoEl.videoHeight) {
            const r = videoEl.getBoundingClientRect();
            const displayWidth = r.width;
            const displayHeight = r.height;
            const offsetX = r.left - containerRect.left;
            const offsetY = r.top - containerRect.top;
            console.log("[BBox] Capturing from video element", {
                width: videoEl.videoWidth,
                height: videoEl.videoHeight,
                displayWidth,
                displayHeight,
                offsetX,
                offsetY,
            });
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
            console.log("[BBox] Capturing from canvas element", {
                width: canvasEl.width,
                height: canvasEl.height,
                displayWidth,
                displayHeight,
                offsetX,
                offsetY,
            });
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
        if (!currentCoord) return;
        const overlay = overlayCanvasRef.current;
        if (!overlay) return;
        const { x, y } = currentCoord;

        const media = getUnderlyingMediaAndSize();
        if (!media) {
            console.warn("[BBox] No media found under overlay; aborting bbox post");
            notify("No video/canvas found. Reset the view and try again.", {
                type: "error",
                durationMs: 6000,
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
            // Assume the canvas displays a 4:3 video where the video height fills the canvas height
            const targetAspect = 4 / 3;
            contentH = mediaDispH;
            contentW = contentH * targetAspect;
            contentX = mediaOffsetX + (mediaDispW - contentW) / 2;
            contentY = mediaOffsetY;
        }

        const rx0 = Math.max(x, contentX);
        const ry0 = Math.max(y, contentY);
        if (rx0 <= 1 || ry0 <= 1) {
            console.warn("[BBox] BBox outside content area; aborting");
            notify("Box outside of content area. Try again within the stream.", {
                type: "warning",
                durationMs: 6000,
            });
            return;
        }

        const scaleX = srcW / contentW;
        const scaleY = srcH / contentH;
        const sx0 = Math.max(
            0,
            Math.min(srcW - 1, Math.round((rx0 - contentX) * scaleX))
        );
        const sy0 = Math.max(
            0,
            Math.min(srcH - 1, Math.round((ry0 - contentY) * scaleY))
        );

        const xNorm = sx0 / srcW;
        const yNorm = sy0 / srcH;

        console.log("[BBox] Posting BBox Prompt Service (normalized source)", {
            bbox: { x: xNorm, y: yNorm },
            src: { width: srcW, height: srcH },
            overlay: { width: overlayW, height: overlayH },
            display: {
                width: mediaDispW,
                height: mediaDispH,
                offsetX: mediaOffsetX,
                offsetY: mediaOffsetY,
            },
            content: { x: contentX, y: contentY, width: contentW, height: contentH },
            scales: { scaleX, scaleY },
        });

        notify(`Sending box [${xNorm.toFixed(2)}, ${yNorm.toFixed(2)}]`, {
            type: "info",
        });

        // @ts-ignore - Custom service
        (connection as any).daiConnection?.postToService(
            "BBox Prompt Service",
            {
                bbox: { x: xNorm, y: yNorm },
            },
            (resp: any) => {
                console.log("[BBox] Service ack:", resp);
                notify("Bounding box sent", { type: "success" });
            }
        );

        setIsDrawing(false);
        setCurrentCoord(null);
        const ctx = overlay.getContext("2d");
        if (ctx) ctx.clearRect(0, 0, overlay.width, overlay.height);
    }, [connection, currentCoord, notify]);

    // --- Selection controls ---

    const handleStartSelection = () => {
        if (!connection.connected) {
            notify("Not connected to device. Cannot start selection.", {
                type: "error",
            });
            return;
        }
        setIsDrawing(true);
        setCurrentCoord(null);
        notify("Click on the stream to pick the object.", {
            type: "info",
            durationMs: 3000,
        });
    };

    const handleClearSelection = () => {
        if (!connection.connected) {
            notify("Not connected to device. Cannot clear selection.", {
                type: "error",
            });
            return;
        }

        console.log("[Selection] Clearing selection via service");
        // @ts-ignore - Custom service
        (connection as any).daiConnection?.postToService(
            "Clear Selection Service",
            {},
            (resp: any) => {
                console.log("[Selection] Clear selection ack:", resp);
                notify("Selection cleared.", {
                    type: "success",
                    durationMs: 2500,
                });
            }
        );
    };

    // --- effects ---

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
            console.log("[BBox] Overlay sized", {
                width: overlay.width,
                height: overlay.height,
            });
        };

        sizeOverlay();
        window.addEventListener("resize", sizeOverlay);
        return () => window.removeEventListener("resize", sizeOverlay);
    }, [isDrawing]);

    useEffect(() => {
        notify(
            connection.connected ? "Connected to device" : "Disconnected from device",
            {
                type: connection.connected ? "success" : "warning",
                durationMs: 1800,
            }
        );
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [connection.connected]);

    // --- overlay mouse events ---

    const onOverlayMouseDown = (e: any) => {
        if (!isDrawing) return;
        const canvas = overlayCanvasRef.current;
        if (!canvas) return;
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        setCurrentCoord({ x, y });
        console.log("[BBox] Mouse down", { x, y });
    };

    const onOverlayMouseUp = () => {
        if (!isDrawing) return;
        console.log("[BBox] Mouse up, finalizing bbox", currentCoord);
        finalizeBBox();
    };

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
            {/* Left: Stream Viewer */}
            <div
                className={css({ flex: 1, position: "relative" })}
                ref={streamContainerRef}
            >
                <Streams />
                {isDrawing && (
                    <canvas
                        ref={overlayCanvasRef}
                        data-role="overlay"
                        className={css({
                            position: "absolute",
                            inset: 0,
                            cursor: "crosshair",
                            zIndex: 10,
                        })}
                        onMouseDown={onOverlayMouseDown}
                        onMouseUp={onOverlayMouseUp}
                    />
                )}
            </div>

            {/* Vertical Divider */}
            <div
                className={css({
                    width: "2px",
                    backgroundColor: "gray.300",
                })}
            />

            {/* Right: Sidebar (Info and Controls) */}
            <div
                className={css({
                    width: "md",
                    display: "flex",
                    flexDirection: "column",
                    gap: "md",
                })}
            >
                <h1
                    className={css({
                        fontSize: "2xl",
                        fontWeight: "bold",
                    })}
                >
                    Dino Tracker
                </h1>

                {/* Short explanation */}
                <p
                    className={css({
                        fontSize: "sm",
                        color: "gray.600",
                        lineHeight: "normal",
                    })}
                >
                    1) Turn on outlines to see FastSAM segments. 2) Click{" "}
                    <strong>Pick object</strong> and then click on the stream to
                    select what to track. 3) Choose how to visualize tracking
                    (heatmap or bounding boxes) and, in BBox mode, tune the
                    confidence slider.
                </p>

                {/* 1) Outlines toggle */}
                <OutlinesToggle />

                {/* 2) Object selection (moved ABOVE annotation mode) */}
                <div
                    className={css({
                        display: "flex",
                        flexDirection: "column",
                        gap: "xs",
                    })}
                >
                    <h3 className={css({ fontWeight: "semibold" })}>
                        Object selection
                    </h3>
                    <p
                        className={css({
                            fontSize: "sm",
                            color: "gray.600",
                        })}
                    >
                        Press{" "}
                        <span className={css({ fontWeight: "semibold" })}>
                            Pick object
                        </span>{" "}
                        and click once on the object in the stream. Use{" "}
                        <span className={css({ fontWeight: "semibold" })}>
                            Clear selection
                        </span>{" "}
                        to reset and choose a new object.
                    </p>
                    <div
                        className={css({
                            display: "flex",
                            gap: "sm",
                        })}
                    >
                        <Button onClick={handleStartSelection}>
                            {isDrawing ? "Click on stream…" : "Pick object"}
                        </Button>
                        <Button variant="outline" onClick={handleClearSelection}>
                            Clear selection
                        </Button>
                    </div>
                </div>

                {/* 3) Annotation mode + (conditionally) confidence slider */}
                <AnnotationModeSelector />

                {/* Connection Status */}
                <div
                    className={css({
                        display: "flex",
                        alignItems: "center",
                        gap: "xs",
                        marginTop: "auto",
                        color: connection.connected ? "green.500" : "red.500",
                    })}
                >
                    <div
                        className={css({
                            width: "3",
                            height: "3",
                            borderRadius: "full",
                            backgroundColor: connection.connected
                                ? "green.500"
                                : "red.500",
                        })}
                    />
                    <span>
                        {connection.connected
                            ? "Connected to device"
                            : "Disconnected"}
                    </span>
                </div>
            </div>
        </main>
    );
}

export default App;
