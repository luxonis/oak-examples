// Visualizer topic names published by the backend pipeline.
export const COLOR_STREAM_TOPIC = 'Color stream';
export const DETECTIONS_TOPIC = 'Detections';
export const SUPPORT_PLANE_PREVIEW_TOPIC = 'Support plane preview';

export const MEASUREMENT_TOPICS = [COLOR_STREAM_TOPIC, DETECTIONS_TOPIC];
// Only the preview topic is shown while calibrating.
export const CALIBRATION_TOPICS = [SUPPORT_PLANE_PREVIEW_TOPIC];

// Sorts stream panels in the given topic order; unknown topics go last.
export const sortTopicsBy =
	(order: readonly string[]) => (a: { name: string }, b: { name: string }) => {
		const rank = (name: string) => {
			const index = order.indexOf(name);
			return index === -1 ? Number.MAX_SAFE_INTEGER : index;
		};
		return rank(a.name) - rank(b.name);
	};
