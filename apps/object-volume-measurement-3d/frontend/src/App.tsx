import { css } from "../styled-system/css/css.mjs";
import { Streams, useDaiConnection } from "@luxonis/depthai-viewer-common";
import { ConfidenceSlider } from "./ConfidenceSlider.tsx";
import { ClickCatcher } from "./ClickOverlay.tsx";
import { ClassSelector } from "./ClassSelector.tsx";
import { useRef } from "react";
import { MeasurementMethodSelector } from "./MeasurementMethodSelector";
import { Button } from "@luxonis/common-fe-components";
import { TopBar } from "./TopBar.tsx";

function App() {
  const connection = useDaiConnection();
  const viewerRef = useRef<HTMLDivElement>(null);

  const clearSelection = () => {
    (connection as any)?.daiConnection?.postToService("Selection Service", { clear: true });
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
      <div
        className={css({
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
          minHeight: 0,
          borderRadius: "md",
          overflow: "hidden",
          borderWidth: "1px",
          borderColor: "gray.300",
          backgroundColor: "white",
        })}
      >
        <TopBar />

        <div ref={viewerRef} className={css({ position: "relative", flex: 1, minHeight: 0 })}>
          <Streams
            defaultTopics={["Video", "Pointclouds"]}
            topicGroups={{ images: "Images", point_clouds: "Pointclouds" }}
          />

          <ClickCatcher
            containerRef={viewerRef}
            frameWidth={640}
            frameHeight={400}
            debug
            allowedPanelTitle="Video"
          />
        </div>
      </div>

      <div className={css({ width: "2px", backgroundColor: "gray.300" })} />

      <div className={css({ width: "md", display: "flex", flexDirection: "column", gap: "md" })}>
        <h1 className={css({ fontSize: "xl", fontWeight: "bold" })}>Object Volume Measurement 3D</h1>
        <p>
            This example combines a YOLOE segmentation model with DepthAI point clouds to measure real-world objects in 3D.
            Click any detected object in the Video panel to segment it and get its dimensions and volume.
        </p>
        <ClassSelector />
        <ConfidenceSlider initialValue={0.15} />
        <Button onClick={clearSelection} alignSelf="start">Clear selected object</Button>
        <MeasurementMethodSelector />
        <div className={css({ display: "flex", alignItems: "center", gap: "xs", marginTop: "auto",
          color: connection.connected ? "green.500" : "red.500" })}>
          <div className={css({ width: "3", height: "3", borderRadius: "full",
            backgroundColor: connection.connected ? "green.500" : "red.500" })}/>
          <span>{connection.connected ? "Connected to device" : "Disconnected"}</span>
        </div>
      </div>
    </main>
  );
}

export default App;