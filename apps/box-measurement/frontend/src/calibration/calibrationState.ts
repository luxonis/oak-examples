export const CALIBRATION_STATES = [
	'SEARCHING',
	'AWAITING_CONFIRMATION',
	'CONFIRMED',
] as const;

export type CalibrationState = (typeof CALIBRATION_STATES)[number];

export const CALIBRATION_STATUS_TEXT: Record<CalibrationState, string> = {
	SEARCHING: 'Searching for a support plane…',
	AWAITING_CONFIRMATION:
		'Confirm that the highlighted support plane is where boxes will be placed.',
	CONFIRMED: 'Support plane confirmed.',
};

// Mirrors the colours SupportPlaneCalibration paints onto the preview cloud
export const CALIBRATION_STATE_COLOR: Partial<
	Record<CalibrationState, string>
> = {
	AWAITING_CONFIRMATION: 'rgb(255, 140, 0)',
	CONFIRMED: 'rgb(0, 255, 0)',
};

/** Measurements are only produced once a support plane is confirmed. */
export function isCalibrated(state: CalibrationState | undefined): boolean {
	return state === 'CONFIRMED';
}
