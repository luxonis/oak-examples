// State names match the backend's support plane calibration states.
export const SUPPORT_PLANE_CALIBRATION_STATES = [
	'SEARCHING',
	'AWAITING_CONFIRMATION',
	'CONFIRMED',
] as const;

export type SupportPlaneCalibrationState =
	(typeof SUPPORT_PLANE_CALIBRATION_STATES)[number];

export const SUPPORT_PLANE_CALIBRATION_STATUS_TEXT: Record<
	SupportPlaneCalibrationState,
	string
> = {
	SEARCHING: 'Searching for a support plane…',
	AWAITING_CONFIRMATION:
		'Confirm that the highlighted support plane is where boxes will be placed.',
	CONFIRMED: 'Support plane confirmed.',
};

/** Shown until the camera has reported a support plane calibration state. */
export const SUPPORT_PLANE_CALIBRATION_STATUS_PENDING_TEXT =
	'Waiting for the support plane calibration status from the camera…';

// Mirrors the colours the backend's SupportPlanePreview node paints onto the
// preview cloud (backend/src/depthai_pipeline/node/support_plane_preview.py)
export const SUPPORT_PLANE_CALIBRATION_STATE_COLOR: Partial<
	Record<SupportPlaneCalibrationState, string>
> = {
	AWAITING_CONFIRMATION: 'rgb(255, 140, 0)',
	CONFIRMED: 'rgb(0, 255, 0)',
};

/** Measurements are only produced once a support plane is confirmed. */
export function isSupportPlaneConfirmed(
	state: SupportPlaneCalibrationState | undefined,
): boolean {
	return state === 'CONFIRMED';
}
