import { css } from "../styled-system/css/css.mjs";
import { Streams, useDaiConnection } from "@luxonis/depthai-viewer-common";
import { AnnotationModeSelector } from "./AnnotationModeSelector.tsx";
import { OutlinesToggle } from "./OutlinesToggle.tsx";
import {useMemo, useRef, useCallback, useState} from "react";
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

function App() {
    const connection = useDaiConnection();
    const { notify } = useNotifications();

    // Use a ref for the internal picking flag to avoid frequent re-renders.
    // Keep a small UI state to trigger renders when the label/button needs to update.
    const isPickingRef = useRef(false);
    const [isPickingUi, setIsPickingUi] = useState(false);
    console.log("Available topics:", connection.topics);

    const handleStreamClick: OnClickHandler = useCallback(
        (_event, coords) => {
            console.log("[DINO FE] Correct clickable UV coordinates:", {
                coords,
                isPicking: isPickingRef.current,
            });

            if (!isPickingRef.current) return;

            if (!coords) {
                notify("Click was outside the video area.", { type: "warning" });

                setIsPickingUi(false);
                isPickingRef.current = false;
                return;
            }

            const { offsetX, offsetY } = coords;

            console.log("[DINO FE] Correct clickable UV coordinates:", {
                xNorm: offsetX,
                yNorm: offsetY,
            });

            // Send to DepthAI
            (connection as any).daiConnection?.postToService(
                "Click Prompt Service",
                { click: { x: offsetX, y: offsetY } },
                () => notify("Object selected!", { type: "success" })
            );

            setIsPickingUi(false);
            isPickingRef.current = false;
        },
        [connection, notify]
    );

    const clickHandlers = useMemo(() => {
        return new Map<string, OnClickHandler>([["Video", handleStreamClick]]);
    }, [handleStreamClick]);

    const handleStartPicking = () => {
        if (!connection.connected) {
            notify("Device is not connected.", { type: "error" });
            return;
        }
        notify("Click on the video to pick object.", { type: "info" });

        setIsPickingUi(true);
        isPickingRef.current = true;
    };

    const handleClearSelection = () => {
        (connection as any).daiConnection?.postToService(
            "Clear Click Prompt Service",
            {},
            () => notify("Selection cleared.", { type: "success" })
        );
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
            {/* LEFT: Streams Viewer */}
            <div className={css({ flex: 1, position: "relative" })}>
                <Streams topicOnClickHandlersMap={clickHandlers} />
            </div>

            {/* divider */}
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
                <h1 className={css({ fontSize: "2xl", fontWeight: "bold" })}>
                    Dino Tracker
                </h1>

                <OutlinesToggle />

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

                    <div className={css({ display: "flex", gap: "sm" })}>
                        <Button onClick={handleStartPicking}>
                            {isPickingUi
                                ? "Click on the stream…"
                                : "Pick object"}
                        </Button>

                        <Button variant="outline" onClick={handleClearSelection}>
                            Clear selection
                        </Button>
                    </div>
                </div>

                <AnnotationModeSelector />

                {/* Connection status */}
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
