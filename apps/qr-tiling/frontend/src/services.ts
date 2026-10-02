import type {
	DAIConnection,
	DAIResponse,
	DAIService,
} from '@luxonis/depthai-viewer-common';

export const QR_TILING_SERVICES = [
	'Tiling Config Service',
	'QR Config Service',
	'Get Current Params Service',
] as const;

export type QRTilingService = (typeof QR_TILING_SERVICES)[number];

export const ACTIVE_SERVICES = [
	'Get Current Params Service',
] as unknown as DAIService[];

type ServiceBody = Record<string, unknown> | string | number;

export function fetchQRTilingService(
	connection: DAIConnection | null,
	service: QRTilingService,
	body?: unknown,
) {
	void connection?.fetchService(
		service as unknown as DAIService,
		body as ServiceBody | undefined,
	);
}

export function postToQRTilingService(
	connection: DAIConnection | null,
	service: QRTilingService,
	body: unknown,
	onResponse: (response: DAIResponse<unknown>) => void = () => {},
) {
	void connection?.postToService(
		service as unknown as DAIService,
		body as ServiceBody,
		onResponse,
	);
}
