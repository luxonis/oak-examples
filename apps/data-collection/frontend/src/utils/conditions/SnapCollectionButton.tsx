import { Button } from "@luxonis/common-fe-components";
import { css } from "../../../styled-system/css/css.mjs";

interface SnapActionButtonProps {
  running: boolean;
  busy: boolean;
  disabled?: boolean;
  onClick: () => void;
}

export function SnapCollectionButton({ running, busy, disabled, onClick }: SnapActionButtonProps) {
  return (
    <Button
      onClick={onClick}
      disabled={!!disabled}
      className={css({
        width: "full",
        py: "sm",
        fontWeight: "semibold",
        backgroundColor: running ? "red.600" : "blue.600",
        color: "white",
        _hover: { backgroundColor: running ? "red.700" : "blue.700" },
        _active: { backgroundColor: running ? "red.800" : "blue.800" },
        _disabled: { opacity: 0.6, cursor: "not-allowed" },
      })}
    >
      {busy ? (running ? "Stopping…" : "Starting…") : running ? "Stop Snapping" : "Start Snapping"}
    </Button>
  );
}
