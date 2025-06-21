import { css } from "../styled-system/css/css.mjs";
import { useState } from "react";

interface ConfidenceSliderProps {
    initialValue?: number;
    onUpdate: (value: number) => void;
}

export function ConfidenceSlider({ initialValue = 0.5, onUpdate }: ConfidenceSliderProps) {
    const [value, setValue] = useState(initialValue);

    // Called only when interaction ends
    const handleCommit = () => {
        if (typeof value === "number" && !isNaN(value)) {
            onUpdate(value);
        } else {
            console.warn("Invalid value, skipping update:", value);
        }
    };

    return (
        <div className={css({ display: 'flex', flexDirection: 'column', gap: 'xs' })}>
            <label className={css({ fontWeight: 'medium' })}>
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
                    width: '100%',
                    appearance: 'none',
                    height: '4px',
                    borderRadius: 'full',
                    backgroundColor: 'gray.300',
                    '&::-webkit-slider-thumb': {
                        appearance: 'none',
                        width: '12px',
                        height: '12px',
                        borderRadius: 'full',
                        backgroundColor: 'blue.500',
                        cursor: 'pointer',
                    },
                    '&::-moz-range-thumb': {
                        appearance: 'none',
                        width: '12px',
                        height: '12px',
                        borderRadius: 'full',
                        backgroundColor: 'blue.500',
                        cursor: 'pointer',
                    }
                })}
            />
        </div>
    );
}
