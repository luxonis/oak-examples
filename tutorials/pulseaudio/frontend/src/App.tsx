import { useEffect, useState } from "react";

import { css } from "../styled-system/css/css.mjs";
import { Streams, useDaiConnection } from "@luxonis/depthai-viewer-common";
import { Button } from "@luxonis/common-fe-components";

function App() {
  const connection = useDaiConnection();
  const connected = connection.connected;
  const svc = (name: string, body: any, cb: (resp: any) => void) =>
    (connection as any).daiConnection?.postToService?.(name, body, cb);

  const [recording, setRecording] = useState(false);
  const [lastFile, setLastFile] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!connected) {
      setRecording(false);
      setLastFile(null);
    }
  }, [connected]);

  const setRec = (on: boolean) => {
    if (!connected) return;
    svc(on ? "Start Recording" : "Stop Recording", {}, (resp: any) => {
      if (!resp?.ok) return;
      setRecording(on);
      setLastFile(resp.path ?? null);
    });
  };

  const downloadLastRecording = () => {
    if (!connected || !lastFile || downloading || recording) return;

    const filename = lastFile.split("/").pop() || "recording.wav";
    setDownloading(true);

    svc("Download Recording", { filename }, (resp: any) => {
      try {
        if (!resp?.ok) return;
        const b64 = resp.b64 as string;
        const mime = (resp.mime as string) || "audio/wav";
        const outName = (resp.filename as string) || filename;

        const bin = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);

        const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
        const a = Object.assign(document.createElement("a"), { href: url, download: outName });
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } finally {
        setDownloading(false);
      }
    });
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
      <div className={css({ flex: 1, position: "relative", minWidth: 0 })}>
        <Streams defaultTopics={["Video"]} />
      </div>

      {/* Vertical Divider */}
      <div className={css({ width: "2px", backgroundColor: "gray.300" })} />

      {/* Right: Sidebar */}
      <aside
        className={css({
          width: "md",
          display: "flex",
          flexDirection: "column",
          gap: "md",
          maxHeight: "100vh",
          paddingRight: "sm",
          overflowY: "auto",
        })}
      >
        <h1 className={css({ fontSize: "2xl", fontWeight: "bold" })}>
          Audio Recorder
        </h1>

        <p className={css({ color: "gray.600" })}>
          Record audio on the device using PulseAudio.
        </p>

        <div
          className={css({
            display: "flex",
            flexDirection: "column",
            gap: "sm",
            padding: "md",
            borderRadius: "lg",
            border: "1px solid",
            borderColor: "gray.200",
            backgroundColor: "white",
          })}
        >
          <div className={css({ display: "flex", gap: "sm", flexWrap: "wrap" })}>
            <Button
              onClick={() => setRec(true)}
              disabled={!connected || recording}
            >
              Start recording
            </Button>

            <Button
              variant="outline"
              onClick={() => setRec(false)}
              disabled={!connected || !recording}
            >
              Stop
            </Button>
          </div>

          <div
            className={css({
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            })}
          >
            <span className={css({ color: "gray.600", fontSize: "sm" })}>
              Status
            </span>
            <span
              className={css({
                fontSize: "sm",
                fontWeight: "semibold",
                color: !connected
                  ? "gray.500"
                  : recording
                    ? "red.600"
                    : "green.600",
              })}
            >
              {!connected ? "Disconnected" : recording ? "Recording…" : "Idle"}
            </span>
          </div>

          {lastFile && (
            <div className={css({ display: "flex", flexDirection: "column", gap: "xs" })}>
              <div className={css({ color: "gray.500", fontSize: "xs" })}>
                Last recording: {lastFile}
              </div>
              <Button
                variant="outline"
                onClick={downloadLastRecording}
                disabled={!connected || recording || downloading}
              >
                {recording ? "Recording…" : downloading ? "Downloading…" : "Download"}
              </Button>
            </div>
          )}
        </div>

        {/* Connection Status */}
        <div
          className={css({
            display: "flex",
            alignItems: "center",
            gap: "xs",
            marginTop: "auto",
            color: connected ? "green.500" : "red.500",
          })}
        >
          <div
            className={css({
              width: "3",
              height: "3",
              borderRadius: "full",
              backgroundColor: connected ? "green.500" : "red.500",
            })}
          />
          <span>
            {connected ? "Connected to device" : "Disconnected"}
          </span>
        </div>
      </aside>
    </main>
  );
}

export default App;