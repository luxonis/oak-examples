// src/MeasurementMethodSelector.tsx
import { useState } from "react";
import { css } from "../styled-system/css/css.mjs";
import { useDaiConnection } from "@luxonis/depthai-viewer-common";

export type MeasurementMethod = "obb" | "heightgrid";

// Keep all copy in one place
const DESCRIPTIONS: Record<MeasurementMethod, string[]> = {
  obb: [
    "Minimal 3D box that encloses the segmented object.",
    "Volume is computed as L × W × H of the box.",
    "Provides a fast upper bound on the object's volume.",
  ],
  heightgrid: [
    "Requires the object to rest on a flat surface (e.g. desk or floor).",
    "Builds a height grid over the object's footprint on the support plane. Total volume is the sum of the grid cell volumes.",
    "Dimensions are still shown as a box (L, W, H), but the volume comes from the height grid integration.",
    "More accurate for irregular shapes, but sensitive to errors in plane fitting.",
  ],
};

export function MeasurementMethodSelector() {
  const connection = useDaiConnection();
  const [method, setMethod] = useState<MeasurementMethod>("obb");

  const sendToBackend = (next: MeasurementMethod) => {
    (connection as any)?.daiConnection?.postToService(
      "Measurement Method Service",
      { method: next },
      () => {
        // optional ack
      }
    );
  };

  const descriptionId = "measurement-method-desc";

  return (
    <div className={css({ display: "flex", flexDirection: "column", gap: "xs" })}>
      <label
        htmlFor="measurement-method"
        className={css({ fontWeight: "semibold" })}
      >
        Measurement method
      </label>

      <select
        id="measurement-method"
        aria-describedby={descriptionId}
        className={css({
          borderWidth: "1px",
          borderColor: "gray.300",
          rounded: "md",
          p: "2",
          bg: connection.connected ? "white" : "gray.100",
          cursor: connection.connected ? "pointer" : "not-allowed",
        })}
        disabled={!connection.connected}
        value={method}
        onChange={(e) => {
          const next = e.target.value as MeasurementMethod;
          setMethod(next);
          sendToBackend(next);
        }}
      >
        <option value="obb">Object-Oriented Bounding Box (min OBB)</option>
        <option value="heightgrid">Ground Plane + Height Grid</option>
      </select>

      {/* Bulleted description */}
        <ul
          id={descriptionId}
          className={css({
            fontSize: "sm",
            color: "gray.600",
            lineHeight: "tall",
            listStyleType: "disc",
            pl: "5",
            mt: "2",
            maxW: "60ch", // optional
          })}
        >
          {DESCRIPTIONS[method].map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
    </div>
  );
}
