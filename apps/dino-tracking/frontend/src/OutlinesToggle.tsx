import { Flex, Button } from "@luxonis/common-fe-components";
import { css } from "../styled-system/css/css.mjs";
import { useNotifications } from "./Notifications.tsx";
import { useDaiConnection } from "@luxonis/depthai-viewer-common";

type Props = {
    enabled: boolean;
    setEnabled: (v: boolean) => void;
};

export function OutlinesToggle({ enabled, setEnabled }: Props) {
    const connection = useDaiConnection();
    const { notify } = useNotifications();

    const handleToggle = () => {
        if (!connection.connected) {
            notify("Not connected to device.", { type: "error" });
            return;
        }

        notify(!enabled ? "Enabling outlines…" : "Hiding outlines…", {
            type: "info",
        });

        (connection as any).daiConnection?.postToService(
            "Outlines Trigger Service",
            { "active": !enabled },
            () => {
                console.log("[Outlines] BE ack:", !enabled);
                setEnabled(!enabled);
                notify(!enabled ? "Outlines enabled." : "Outlines disabled.", {
                    type: "success",
                });
            }
        );
    };

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
                    {enabled ? "Hide outlines" : "Draw outlines"}
                </Button>
            </Flex>
        </div>
    );
}
