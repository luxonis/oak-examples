import type { DAIConnection, DAIService } from '@luxonis/depthai-viewer-common';

export const ROBOFLOW_SERVICES = [
	'Roboflow Workflow Interface Service',
	'Roboflow Parameter Update Service',
	'Roboflow Workflow Refresh Service',
] as const;

export type RoboflowService = (typeof ROBOFLOW_SERVICES)[number];

type ServiceBody = Record<string, unknown> | string | number;

export function postToRoboflowService(
	connection: DAIConnection | null,
	service: RoboflowService,
	body: unknown,
	onResponse: (response: unknown) => void,
	timeoutMs = 60_000,
	onError?: (response: unknown) => void,
) {
	void connection?.postToService(
		service as unknown as DAIService,
		body as ServiceBody,
		(response) => onResponse(response),
		onError ? (response) => onError(response) : undefined,
		timeoutMs,
	);
}
