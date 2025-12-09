import { Flex, Button } from "@luxonis/common-fe-components";
import { useState } from "react";
import { css } from "../styled-system/css/css.mjs";
import { useDaiConnection } from "@luxonis/depthai-viewer-common";
import { useNotifications } from "./Notifications.tsx";
import { ConfidenceSlider } from "./ConfidenceSlider.tsx";

type Mode = "heatmap" | "bbox";

type Props = {
    onModeChanged?: (mode: Mode) => void;
};

export function AnnotationModeSelector({ onModeChanged }: Props) {
    const connection = useDaiConnection();
    const { notify } = useNotifications();

    // Default mode – startup is "heatmap"
    const [currentMode, setCurrentMode] = useState<Mode>("heatmap");

    const modes: { id: Mode; label: string }[] = [
        { id: "heatmap", label: "Heatmap" },
        { id: "bbox", label: "BBoxes" },
    ];

    const handleClick = (mode: Mode) => {
        if (mode === currentMode) {
            return;
        }

        if (!connection.connected) {
            notify("Not connected to device. Unable to change annotation mode.", {
                type: "error",
                durationMs: 5000,
            });
            return;
        }

        console.log("Sending annotation mode to backend:", mode);
        notify(`Switching visualization mode to "${mode}"…`, { type: "info" });

        // Name the service however you wired it on BE
        // e.g. in Python service: "Annotation Mode Service"
        connection.daiConnection?.postToService(
            // @ts-ignore - custom DepthAI service
            "Annotation Mode Service",
            mode,
            () => {
                console.log("Backend acknowledged annotation mode update");
                setCurrentMode(mode);
                notify(`Annotation mode set to "${mode}"`, {
                    type: "success",
                    durationMs: 4000,
                });
                onModeChanged?.(mode);
            }
        );
    };

    return (
        <div
            className={css({
                display: "flex",
                flexDirection: "column",
                gap: "sm",
            })}
        >
            <h3 className={css({ fontWeight: "semibold" })}>Annotation mode</h3>

            <Flex direction="row" gap="sm">
                {modes.map(({ id, label }) => {
                    const isActive = id === currentMode;

                    return (
                        <Button
                            key={id}
                            onClick={() => handleClick(id)}
                            disabled={isActive}
                            className={css({
                                flex: "1 1 0",
                                fontSize: "sm",
                                ...(isActive
                                    ? {
                                          backgroundColor: "gray.400",
                                          color: "white",
                                          cursor: "default",
                                      }
                                    : {
                                          backgroundColor: "blue.500",
                                          color: "white",
                                          cursor: "pointer",
                                      }),
                            })}
                        >
                            {label}
                        </Button>
                    );
                })}
            </Flex>

            {/* Only show confidence slider when BBox mode is active */}
            {currentMode === "bbox" && (
                <div
                    className={css({
                        marginTop: "xs",
                    })}
                >
                    <ConfidenceSlider initialValue={0.5} />
                </div>
            )}
        </div>
    );
}
