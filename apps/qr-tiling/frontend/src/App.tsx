import { css } from "../styled-system/css/css.mjs";
import { Streams, useDaiConnection } from "@luxonis/depthai-viewer-common";
import { TilingControl, TilingParams } from "./TilingControl";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNotifications } from "./Notifications";
import { CircleLoader } from "./CircleLoader.tsx";

export type CurrentParamsResponse = {
    tiling: TilingParams;
    decoder: boolean;
};

function App() {
    const connection = useDaiConnection();
    const { notify } = useNotifications();

    const [paramsLoaded, setParamsLoaded] = useState(false);
    const [tilingParams, setTilingParams] = useState<TilingParams | null>(null);
    const [decodeEnabled, setDecodeEnabled] = useState<boolean>(false);

    const streamContainerRef = useRef<HTMLDivElement>(null);

    const onCurrentParams = useCallback((response: CurrentParamsResponse) => {
        console.log("[Init] Returned tiling params:", response);
        setTilingParams(response.tiling);
        setDecodeEnabled(response.decoder)
        setParamsLoaded(true);
    }, []);

    useEffect(() => {
        const dai = (connection as any).daiConnection;
        if (!dai) return;

        dai.setOnService("Get Current Params Service", onCurrentParams);
    }, [connection, onCurrentParams]);

    useEffect(() => {
        if (!connection.connected) {
            notify("Not connected to device", { type: "error" });
            setParamsLoaded(false);
            return;
        }

        console.log("[Init] Fetching tiling params…");
        (connection as any).daiConnection?.fetchService(
            "Get Current Params Service"
        );
    }, [connection, notify]);

    const sendQRConfig = useCallback(
    (state: boolean) => {
        (connection as any).daiConnection?.postToService(
            "QR Config Service",
            { state }
        );
    },
    [connection]
);

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
            {/* Stream */}
            <div
                className={css({ flex: 1, position: "relative" })}
                ref={streamContainerRef}
            >
                <Streams allowedTopics={["Video"]} defaultTopics={["Video"]} />
            </div>

            <div
                className={css({
                    width: "2px",
                    backgroundColor: "gray.300",
                })}
            />

            {/* Sidebar */}
            <div
                className={css({
                    width: "md",
                    display: "flex",
                    flexDirection: "column",
                    gap: "md",
                    height: "100vh",
                    overflowY: "auto",
                    paddingRight: "sm",
                })}
            >
                <h1 className={css({ fontSize: "2xl", fontWeight: "bold" })}>
                    Configuration
                </h1>

                {!paramsLoaded || !tilingParams ? (
                    <div className={css({
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 'sm',
                        height: 'full',
                        color: 'gray.500'
                    })}>
                        <CircleLoader />
                        <span>Loading tiling configuration…</span>
                    </div>
                ) : (
                    <div>
                        <span style={{ fontSize: 16, fontWeight: "bold" }}>
                                QR Code Configuration
                            </span>
                        <div
                            className={css({
                                display: "flex",
                                alignItems: "center",
                                gap: "sm",
                                padding: "sm",
                                borderRadius: "md",
                                backgroundColor: "gray.50",
                                border: "1px solid",
                                borderColor: "gray.200",
                                marginBottom: "md",
                                marginTop: "md",
                            })}
                        >
                            <input
                                type="checkbox"
                                checked={decodeEnabled}
                                onChange={(e) => {
                                    const newState = e.target.checked;
                                    setDecodeEnabled(newState);
                                    sendQRConfig(newState);
                                }}
                            />
                            <span
                                className={css({
                                    fontSize: "sm",
                                    fontWeight: "medium",
                                })}
                            >
                                Enable QR decoding
                            </span>
                        </div>

                        <div
                            className={css({
                                flex: 1,
                                overflowY: "auto",
                                paddingRight: "xs",
                                minHeight: 0,
                            })}
                        >
                            <TilingControl initialParams={tilingParams} />
                        </div>
                    </div>
                )}

                <div
                    className={css({
                        display: "flex",
                        alignItems: "center",
                        gap: "xs",
                        marginTop: "auto",
                        color: connection.connected
                            ? "green.500"
                            : "red.500",
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
                            ? "Connected"
                            : "Disconnected"}
                    </span>
                </div>
            </div>
        </main>
    );
}

export default App;
