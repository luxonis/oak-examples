import { css } from "../../../styled-system/css/css.mjs";

interface CooldownMinutesInputProps {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  onBlur?: () => void;
  valid: boolean;
  disabled?: boolean;
  ariaLabel?: string;
}

export function CooldownMinutesInput({
  label = "Cooldown (minutes)",
  value,
  onChange,
  onBlur,
  valid,
  disabled,
  ariaLabel,
}: CooldownMinutesInputProps) {
  return (
    <label className={css({ display: "flex", flexDirection: "column", gap: "xs" })}>
      <span className={css({ fontWeight: "medium" })}>{label}</span>
      <div className={css({ display: "flex", alignItems: "center", gap: "sm" })}>
        <input
          type="number"
          min={0}
          step={0.1}
          inputMode="decimal"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          disabled={!!disabled}
          className={css({
            flex: "1",
            px: "sm",
            py: "xs",
            borderWidth: "1px",
            borderColor: disabled ? "gray.300" : valid ? "gray.300" : "red.500",
            rounded: "md",
            _disabled: { bg: "gray.100", color: "gray.500", cursor: "not-allowed" },
          })}
          aria-invalid={!valid && !disabled}
          aria-label={ariaLabel || "Cooldown (minutes, max 1 decimal)"}
        />
        <span className={css({ color: "gray.600" })}>minutes</span>
      </div>
      {!valid && (
        <span className={css({ fontSize: "xs", color: "red.600" })}>
          Enter a non-negative number with at most one decimal place.
        </span>
      )}
    </label>
  );
}
