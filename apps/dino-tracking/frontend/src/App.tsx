import { css } from "../styled-system/css/css.mjs";
import { Streams, useDaiConnection } from "@luxonis/depthai-viewer-common";
import { AnnotationModeSelector } from "./AnnotationModeSelector.tsx";
import { OutlinesToggle } from "./OutlinesToggle.tsx";
import { ConfidenceSlider } from "./ConfidenceSlider.tsx";
import { useCallback, useMemo, useEffect, useState } from "react";
import { useNotifications } from "./Notifications.tsx";
import { Button } from "@luxonis/common-fe-components";
import * as React from "react";

type OnClickHandler = (
    event: React.MouseEvent,
    coords:
        | {
              offsetX: number;
              offsetY: number;
          }
        | undefined
) => void;

interface BackendConfig {
    confidence: number;
    annotation_mode: "heatmap" | "bbox";
    outlines: boolean;
}

export default function App() {
    const connection = useDaiConnection();
    const { notify } = useNotifications();

    // ----------------------------------------------------
    // UI STATE
    // ----------------------------------------------------
    const [threshold, setThreshold] = useState(0.35);
    const [annotationMode, setAnnotationMode] =
        useState<"heatmap" | "bbox">("heatmap");
    const [outlinesEnabled, setOutlinesEnabled] = useState(false);

    // Backend config
    const [configLoaded, setConfigLoaded] = useState(false);

    // 🔒 STREAM LATCH (key fix)
    const [streamEverAvailable, setStreamEverAvailable] = useState(false);

    // ----------------------------------------------------
    // LATCH FIRST VIDEO STREAM APPEARANCE
    // ----------------------------------------------------
    useEffect(() => {
        if (streamEverAvailable) return;

        if (
            Array.isArray(connection.topics) &&
            connection.topics.some((t) => t.name === "Video")
        ) {
            console.log("[App] Video stream appeared → latching Streams ON");
            setStreamEverAvailable(true);
        }
    }, [connection.topics, streamEverAvailable]);

    // ----------------------------------------------------
    // STREAM CLICK HANDLER
    // ----------------------------------------------------
    const handleStreamClick: OnClickHandler = useCallback(
        (_event, coords) => {
            if (!coords) {
                notify("Click was outside the video area.", { type: "warning" });
                return;
            }

            const { offsetX, offsetY } = coords;

            (connection as any).daiConnection?.postToService(
                "Click Prompt Service",
                { x: offsetX, y: offsetY },
                () => notify("Object selected!", { type: "success" })
            );
        },
        [connection, notify]
    );

    const clickHandlers = useMemo(
        () => new Map<string, OnClickHandler>([["Video", handleStreamClick]]),
        [handleStreamClick]
    );

    // ----------------------------------------------------
    // CLEAR SELECTION
    // ----------------------------------------------------
    const handleClearSelection = () => {
        (connection as any).daiConnection?.postToService(
            "Clear Selection Service",
            {},
            () => notify("Selection cleared.", { type: "success" })
        );
    };

    // ----------------------------------------------------
    // LOAD CONFIG FROM BACKEND
    // ----------------------------------------------------
    useEffect(() => {
        if (!connection.connected || configLoaded) return;

        const timeoutId = setTimeout(() => {
            (connection as any).daiConnection?.postToService(
                "BE State Service",
                null,
                (response: any) => {
                    if (!response) {
                        notify("BE State Service unavailable", {
                            type: "warning",
                        });
                        return;
                    }

                    try {
                        let obj = response;

                        if (obj.buffer instanceof ArrayBuffer) {
                            const td = new TextDecoder("utf-8");
                            const view = new Uint8Array(
                                obj.buffer,
                                obj.byteOffset,
                                obj.byteLength
                            );
                            obj = JSON.parse(td.decode(view));
                        }

                        const cfg = obj as BackendConfig;
                        setConfigLoaded(true);

                        if (cfg.confidence !== undefined)
                            setThreshold(cfg.confidence);
                        if (cfg.annotation_mode)
                            setAnnotationMode(cfg.annotation_mode);
                        if (cfg.outlines !== undefined)
                            setOutlinesEnabled(cfg.outlines);

                        notify("Configuration restored from backend", {
                            type: "success",
                        });
                    } catch (e) {
                        console.error(e);
                        notify("Failed to load configuration", {
                            type: "error",
                        });
                    }
                }
            );
        }, 600);

        return () => clearTimeout(timeoutId);
    }, [connection.connected, configLoaded, notify]);

    useEffect(() => {
        if (!connection.connected) {
            setConfigLoaded(false);
        }
    }, [connection.connected]);

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
            {/* LEFT SIDE: STREAM */}
            <div className={css({ flex: 1, position: "relative" })}>
                {streamEverAvailable ? (
                    <Streams
                        topicOnClickHandlersMap={clickHandlers}
                        defaultTopics={["Video"]}
                    />
                ) : (
                    <div
                        className={css({
                            width: "100%",
                            height: "100%",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "gray.500",
                            fontSize: "sm",
                        })}
                    >
                        Downloading neural network models and waiting for video stream...
                    </div>
                )}
            </div>

            {/* DIVIDER */}
            <div className={css({ width: "2px", backgroundColor: "gray.300" })} />

            {/* RIGHT SIDEBAR */}
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

                <p
                    className={css({
                        fontSize: "sm",
                        color: "gray.600",
                        lineHeight: "normal",
                    })}
                >
                    1) Turn on outlines to see FastSAM segments. 2) Click on the stream to
                    select what to track. 3) Choose how to visualize tracking
                    (heatmap or bounding boxes) and, in BBox mode, tune the
                    confidence slider.
                </p>

                {/* OUTLINES */}
                <OutlinesToggle enabled={outlinesEnabled} setEnabled={setOutlinesEnabled}/>


                {/* SELECTION */}
                <p
                    className={css({
                        fontSize: "sm",
                        color: "gray.600",
                    })}
                >
                    Click once on the object in the stream. Use{" "}
                    <span className={css({fontWeight: "semibold"})}>
                            Clear selection
                        </span>{" "}
                    to reset and choose a new object.
                </p>

                <div className={css({display: "flex", gap: "sm"})}>
                    <Button variant="outline" onClick={handleClearSelection}>
                        Clear selection
                    </Button>
                </div>

                <AnnotationModeSelector
                    currentMode={annotationMode}
                    setCurrentMode={setAnnotationMode}
                />

                {annotationMode === "bbox" && (
                    <ConfidenceSlider value={threshold} setValue={setThreshold}/>
                )}

                {/* CONNECTION STATUS */}
                <div
                    className={css({
                        marginTop: "auto",
                        display: "flex",
                        gap: "xs",
                        alignItems: "center",
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
                        {connection.connected ? "Connected to device" : "Disconnected"}
                    </span>
                </div>
            </div>
        </main>
    );
}
