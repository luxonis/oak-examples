import { css } from "../styled-system/css/css.mjs";
import { useDaiConnection } from "@luxonis/depthai-viewer-common";

interface ConfidenceSliderProps {
    value: number;
    setValue: (v: number) => void;
}

export function ConfidenceSlider({ value, setValue }: ConfidenceSliderProps) {
    const connection = useDaiConnection();

    const handleCommit = () => {
        if (typeof value === "number" && !isNaN(value)) {
            console.log("[Threshold] Sending to backend:", value);

            (connection as any).daiConnection?.postToService(
                "Threshold Update Service",
                { "threshold": value },
                (response: any) => {
                    console.log("[Threshold] Backend acknowledged:", response);
                }
            );
        } else {
            console.warn("[Threshold] Invalid value:", value);
        }
    };

    return (
        <div
            className={css({
                display: "flex",
                flexDirection: "column",
                gap: "xs",
            })}
        >
            <label className={css({ fontWeight: "medium" })}>
                Confidence Threshold: {value.toFixed(2)}
            </label>

            <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={value}
                onChange={(e) => setValue(parseFloat(e.target.value))}
                onMouseUp={handleCommit}
                onTouchEnd={handleCommit}
                className={css({
                    width: "100%",
                    appearance: "none",
                    height: "4px",
                    borderRadius: "full",
                    backgroundColor: "gray.300",
                    "&::-webkit-slider-thumb": {
                        appearance: "none",
                        width: "12px",
                        height: "12px",
                        borderRadius: "full",
                        backgroundColor: "blue.500",
                        cursor: "pointer",
                    },
                    "&::-moz-range-thumb": {
                        appearance: "none",
                        width: "12px",
                        height: "12px",
                        borderRadius: "full",
                        backgroundColor: "blue.500",
                        cursor: "pointer",
                    },
                })}
            />
        </div>
    );
}
