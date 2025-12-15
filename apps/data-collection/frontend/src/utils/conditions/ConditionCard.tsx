import { ReactNode } from "react";
import { css } from "../../../styled-system/css/css.mjs";

interface ConditionCardProps {
  title: string;
  enabled: boolean;
  onToggle: (val: boolean) => void;
  disabled?: boolean;
  description?: string;
  children?: ReactNode;
}

export function ConditionCard({
  title,
  enabled,
  onToggle,
  disabled,
  description,
  children,
}: ConditionCardProps) {
  const Divider = () => (
    <div className={css({ width: "full", height: "1px", backgroundColor: "gray.200", my: "sm" })} />
  );

  return (
    <div className={css({ display: "flex", flexDirection: "column", gap: "sm" })}>
      <Divider />
      <div className={css({ display: "flex", alignItems: "center", justifyContent: "space-between" })}>
        <label className={css({ fontWeight: "semibold" })}>{title}</label>
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onToggle(e.target.checked)}
          disabled={!!disabled}
          className={css({ width: "5", height: "5", cursor: disabled ? "not-allowed" : "pointer" })}
        />
      </div>
      {enabled && description && (
        <p className={css({ fontSize: "sm", color: "gray.600" })}>{description}</p>
      )}
      {enabled && children}
    </div>
  );
}
