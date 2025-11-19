import { useState, useEffect } from "react";
import { useDaiConnection } from "@luxonis/depthai-viewer-common";
import { SliderControl } from "../SliderControl.tsx";

interface ConfidenceSliderProps {
  initialValue?: number;
  disabled?: boolean;
}

export function ConfidenceSlider({ initialValue = 0.5, disabled }: ConfidenceSliderProps) {
  const connection = useDaiConnection();
  const [value, setValue] = useState(initialValue);

  // Update value from backend config
  useEffect(() => {
    if (initialValue !== undefined && Number.isFinite(initialValue)) {
      console.log("[ConfidenceSlider] Restoring value from backend:", initialValue);
      setValue(initialValue);
    }
  }, [initialValue]);

  const handleCommit = (new_threshold: number) => {
    if (Number.isFinite(new_threshold)) {
      connection.daiConnection?.postToService(
        // @ts-ignore - Custom service
        "Threshold Update Service",
          { threshold: new_threshold },
        (resp: any) => console.log("[ConfidenceSlider] BE ack:", resp)
      );
    }
  };

  return (
    <SliderControl
      label={`Confidence Threshold: ${(value * 100).toFixed(0)}%`}
      value={value}
      onChange={setValue}
      onCommit={handleCommit}
      min={0}
      max={1}
      step={0.01}
      disabled={disabled}
      aria-label="Confidence threshold"
    />
  );
}
