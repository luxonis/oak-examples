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

    // UI state
    const [threshold, setThreshold] = useState(0.35);
    const [annotationMode, setAnnotationMode] = useState<"heatmap" | "bbox">("heatmap");
    const [outlinesEnabled, setOutlinesEnabled] = useState(false);

    // Backend config
    const [configLoaded, setConfigLoaded] = useState(false);

    console.log("Available topics:", connection.topics);

    const handleStreamClick: OnClickHandler = useCallback(
        (_event, coords) => {

            if (!coords) {
                notify("Click was outside the video area.", { type: "warning" });
                return;
            }

            const { offsetX, offsetY } = coords;

            (connection as any).daiConnection?.postToService(
                "Click Prompt Service",
                { click: { x: offsetX, y: offsetY } },
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
            "Clear Click Prompt Service",
            {},
            () => notify("Selection cleared.", { type: "success" })
        );
    };

    // ----------------------------------------------------
    // LOAD CONFIG FROM BACKEND (like Export Service)
    // ----------------------------------------------------
    useEffect(() => {
        if (!connection.connected || configLoaded) return;

        const timeoutId = setTimeout(() => {
            console.log("[DinoTracker] Fetching backend configuration…");

            (connection as any).daiConnection?.postToService(
                "BE State Service",
                null,
                (response: any) => {
                    console.log("[DinoTracker] Raw state payload:", response);
                    if (!response) {
                        notify("BE State Service unavailable", { type: "warning" });
                        return;
                    }

                    try {
                        let obj = response;

                        // If device returned ArrayBuffer
                        if (obj.buffer instanceof ArrayBuffer) {
                            const td = new TextDecoder("utf-8");
                            const view = new Uint8Array(obj.buffer, obj.byteOffset, obj.byteLength);
                            obj = JSON.parse(td.decode(view));
                        }

                        const cfg = obj as BackendConfig;
                        setConfigLoaded(true);

                        notify("Configuration restored from backend", { type: "success" });

                        if (cfg.confidence !== undefined) setThreshold(cfg.confidence);
                        if (cfg.annotation_mode) setAnnotationMode(cfg.annotation_mode);
                        if (cfg.outlines) setOutlinesEnabled(cfg.outlines);

                        setConfigLoaded(true);

                        console.log("[DinoTracker] Applied config:", cfg);

                    } catch (e) {
                        console.error("[DinoTracker] Failed parsing config:", e);
                        notify("Failed to load configuration", { type: "error" });
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
                <Streams topicOnClickHandlersMap={clickHandlers} defaultTopics={["Video"]}/>
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
                <h1 className={css({fontSize: "2xl", fontWeight: "bold"})}>
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

                {/* MODE */}
                <AnnotationModeSelector
                    currentMode={annotationMode}
                    setCurrentMode={setAnnotationMode}
                />

                {/* THRESHOLD */}
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
