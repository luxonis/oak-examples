import type {
	DAIConnection,
	DAIResponse,
	DAIService,
} from '@luxonis/depthai-viewer-common';

export const P2P_MEASUREMENT_SERVICES = [
	'Selection Service',
	'Clear Points Service',
	'Get Distance Service',
	'Toggle Tracking Service',
	'Get Tracking Status Service',
] as const;

export type P2PMeasurementService = (typeof P2P_MEASUREMENT_SERVICES)[number];
export const P2P_MEASUREMENT_ACTIVE_SERVICES =
	P2P_MEASUREMENT_SERVICES as unknown as DAIService[];

type ServiceBody = Record<string, unknown> | string | number;

export function postToP2PMeasurementService(
	connection: DAIConnection | null,
	service: P2PMeasurementService,
	body: unknown,
	onResponse: (response: DAIResponse<unknown>) => void = () => {},
) {
	void connection?.postToService(
		service as unknown as DAIService,
		body as ServiceBody,
		onResponse,
	);
}
