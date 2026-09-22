import type {
	DAIConnection,
	DAIResponse,
	DAIService,
} from '@luxonis/depthai-viewer-common';

export const DINO_TRACKING_SERVICES = [
	'Click Prompt Service',
	'Clear Selection Service',
	'Threshold Update Service',
	'Outlines Trigger Service',
	'Annotation Mode Service',
	'BE State Service',
] as const;

export type DinoTrackingService = (typeof DINO_TRACKING_SERVICES)[number];

type ServiceBody = Record<string, unknown> | string | number;

export function postToDinoTrackingService(
	connection: DAIConnection | null,
	service: DinoTrackingService,
	body: unknown,
	onResponse: (response: DAIResponse<unknown>) => void = () => {},
) {
	void connection?.postToService(
		service as unknown as DAIService,
		body as ServiceBody,
		onResponse,
	);
}
