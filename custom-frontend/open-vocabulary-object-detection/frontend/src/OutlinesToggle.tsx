import { useState } from "react";
import { Flex, Button } from "@luxonis/common-fe-components";
import { useConnection } from "@luxonis/depthai-viewer-common";
import { css } from "../styled-system/css/css.mjs";
import { useNotifications } from "./Notifications.tsx";

export function OutlinesToggle() {
    const connection = useConnection();
    const { notify } = useNotifications();

    // FE state only. We assume BE starts with outlines OFF,
    // so default label is "Draw outlines".
    const [enabled, setEnabled] = useState(false);

    const handleToggle = () => {
        if (!connection.connected) {
            notify("Not connected to device. Unable to toggle outlines.", {
                type: "error",
                durationMs: 5000,
            });
            return;
        }

        const nextEnabled = !enabled;
        const mode = nextEnabled ? "on" : "off";

        console.log("[Outlines] Sending outlines mode to backend:", mode);
        notify(
            nextEnabled ? "Enabling FastSAM outlines…" : "Hiding outlines…",
            { type: "info", durationMs: 2500 }
        );

        // @ts-ignore - custom DepthAI service
        (connection as any).daiConnection?.postToService(
            "Outlines Mode Service",
            mode,
            () => {
                console.log("[Outlines] Backend acknowledged outlines mode:", mode);
                setEnabled(nextEnabled);
                notify(
                    nextEnabled ? "Outlines enabled." : "Outlines hidden.",
                    { type: "success", durationMs: 3000 }
                );
            }
        );
    };

    const label = enabled ? "Hide outlines" : "Draw outlines";

    return (
        <div className={css({ display: "flex", flexDirection: "column", gap: "sm" })}>
            <h3 className={css({ fontWeight: "semibold" })}>Outlines</h3>

            <Flex direction="row">
                <Button
                    onClick={handleToggle}
                    className={css({
                        flex: "1 1 0",
                        fontSize: "sm",
                        backgroundColor: enabled ? "gray.700" : "blue.500",
                        color: "white",
                        cursor: "pointer",
                    })}
                >
                    {label}
                </Button>
            </Flex>
        </div>
    );
}
