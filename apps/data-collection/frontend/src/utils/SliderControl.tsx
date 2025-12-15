import { css } from "../../styled-system/css/css.mjs";
import { ReactNode, useCallback } from "react";

export interface SliderControlProps {
  label?: ReactNode;
  value: number;
  onChange: (v: number) => void;
  onCommit?: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  id?: string;
  "aria-label"?: string;
}

export function SliderControl({
  label,
  value,
  onChange,
  onCommit,
  min = 0,
  max = 1,
  step = 0.01,
  disabled,
  id,
  ...aria
}: SliderControlProps) {
  const commit = useCallback(() => onCommit?.(value), [onCommit, value]);

  return (
    <div className={css({ display: "flex", flexDirection: "column", gap: "xs" })}>
      {label && <label htmlFor={id} className={css({ fontWeight: "medium" })}>{label}</label>}
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        onMouseUp={commit}
        onTouchEnd={commit}
        onBlur={commit}
        onKeyUp={(e) => (e.key === "Enter" || e.key === " ") && commit()}
        disabled={disabled}
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
        {...aria}
      />
    </div>
  );
}
