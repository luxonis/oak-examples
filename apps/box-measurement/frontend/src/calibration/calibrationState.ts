export const CALIBRATION_STATES = [
    "RESTORING",
    "SEARCHING",
    "AWAITING_CONFIRMATION",
    "CONFIRMED",
] as const;

export type CalibrationState = (typeof CALIBRATION_STATES)[number];

export const CALIBRATION_STATUS_TEXT: Record<CalibrationState, string> = {
    RESTORING: "Checking saved calibration…",
    SEARCHING: "Searching for a support surface…",
    AWAITING_CONFIRMATION:
        "Confirm that the highlighted surface is where boxes will be placed.",
    CONFIRMED: "Support surface confirmed.",
};

// Mirrors the colours SupportPlaneCalibration paints onto the preview cloud
export const CALIBRATION_STATE_COLOR: Partial<
    Record<CalibrationState, string>
> = {
    AWAITING_CONFIRMATION: "rgb(255, 140, 0)",
    CONFIRMED: "rgb(0, 255, 0)",
};

/** Colour of the nav badge shown while calibration needs the operator. */
export const CALIBRATION_ATTENTION_COLOR = "rgb(255, 140, 0)";

/** Measurements are only produced once a support plane is confirmed. */
export function isCalibrated(state: CalibrationState | undefined): boolean {
    return state === "CONFIRMED";
}

/** Signed distance offset, e.g. "+2.0 cm". */
export function formatOffsetCm(offsetCm: number): string {
    return `${offsetCm > 0 ? "+" : ""}${offsetCm.toFixed(1)} cm`;
}

// Whether to actively draw the operator's attention to calibration.
export function needsCalibrationAttention(
    state: CalibrationState | undefined,
): boolean {
    return state === "SEARCHING" || state === "AWAITING_CONFIRMATION";
}
