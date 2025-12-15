import { Flex, Button } from "@luxonis/common-fe-components";
import { css } from "../styled-system/css/css.mjs";
import { useDaiConnection } from "@luxonis/depthai-viewer-common";
import { useNotifications } from "./Notifications.tsx";

type Mode = "heatmap" | "bbox";

type Props = {
    currentMode: Mode;
    setCurrentMode: (m: Mode) => void;
};

export function AnnotationModeSelector({ currentMode, setCurrentMode }: Props) {
    const connection = useDaiConnection();
    const { notify } = useNotifications();

    const modes: { id: Mode; label: string }[] = [
        { id: "heatmap", label: "Heatmap" },
        { id: "bbox", label: "BBoxes" },
    ];

    const handleClick = (mode: Mode) => {
        if (mode === currentMode) return;

        if (!connection.connected) {
            notify("Not connected to device.", { type: "error" });
            return;
        }

        notify(`Switching to "${mode}"…`, { type: "info" });

        (connection as any).daiConnection?.postToService(
            "Annotation Mode Service",
            { "mode": mode },
            () => {
                console.log("[Annotation] BE acknowledged:", mode);
                setCurrentMode(mode);   // <-- update FE
                notify(`Annotation mode set to "${mode}"`, { type: "success" });
            }
        );
    };

    return (
        <div className={css({ display: "flex", flexDirection: "column", gap: "sm" })}>
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
        </div>
    );
}
