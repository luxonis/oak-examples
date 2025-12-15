import { css } from "../../../styled-system/css/css.mjs";

interface EdgeBufferPercentInputProps {
  value: string;
  onChange: (v: string) => void;
  onBlur?: () => void;
  valid: boolean;
  disabled?: boolean;
}

export function EdgeBufferPercentInput({
  value,
  onChange,
  onBlur,
  valid,
  disabled,
}: EdgeBufferPercentInputProps) {
  return (
    <label className={css({ display: "flex", flexDirection: "column", gap: "xs" })}>
      <span className={css({ fontWeight: "medium" })}>Edge buffer (each side) — 0–49%</span>
      <input
        type="number"
        min={0}
        max={49}
        step={1}
        inputMode="numeric"
        pattern="\\d*"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        disabled={!!disabled}
        className={css({
          px: "sm",
          py: "xs",
          borderWidth: "1px",
          borderColor: disabled ? "gray.300" : valid ? "gray.300" : "red.500",
          rounded: "md",
          _disabled: { bg: "gray.100", color: "gray.500", cursor: "not-allowed" },
        })}
        aria-invalid={!valid && !disabled}
        aria-label="Lost-in-middle edge buffer percent (0–49)"
      />
      <span className={css({ fontSize: "xs", color: "gray.600" })}>
        We ignore the outer margin on every edge; only losses inside the remaining center fire snaps.
      </span>
    </label>
  );
}
