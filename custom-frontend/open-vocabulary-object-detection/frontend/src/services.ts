import type {
	DAIConnection,
	DAIResponse,
	DAIService,
} from '@luxonis/depthai-viewer-common';

export const CUSTOM_SERVICES = [
	'Class Update Service',
	'Threshold Update Service',
	'Image Upload Service',
	'BBox Prompt Service',
	'Rename Image Prompt Service',
	'Delete Image Prompt Service',
	'Get Current Params Service',
] as const;

export type CustomService = (typeof CUSTOM_SERVICES)[number];

export const ACTIVE_SERVICES = [
	'Get Current Params Service',
] as unknown as DAIService[];

type ServiceBody = Record<string, unknown> | string | number;

export function fetchCustomService(
	connection: DAIConnection | null,
	service: CustomService,
	body?: unknown,
) {
	void connection?.fetchService(
		service as unknown as DAIService,
		body as ServiceBody | undefined,
	);
}

export function postToCustomService(
	connection: DAIConnection | null,
	service: CustomService,
	body: unknown,
	onResponse: (response: DAIResponse<unknown>) => void = () => {},
) {
	void connection?.postToService(
		service as unknown as DAIService,
		body as ServiceBody,
		onResponse,
	);
}
