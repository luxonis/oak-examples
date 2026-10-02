import type {
	DAIConnection,
	DAIResponse,
	DAIService,
} from '@luxonis/depthai-viewer-common';

export const DATA_COLLECTION_SERVICES = [
	'Class Update Service',
	'Threshold Update Service',
	'Image Upload Service',
	'BBox Prompt Service',
	'Snap Collection Service',
	'Get App Config Service',
] as const;

export type DataCollectionService = (typeof DATA_COLLECTION_SERVICES)[number];

type ServiceBody = Record<string, unknown> | string | number;

export function postToDataCollectionService(
	connection: DAIConnection | null,
	service: DataCollectionService,
	body: unknown,
	onResponse: (response: DAIResponse<unknown>) => void = () => {},
) {
	void connection?.postToService(
		service as unknown as DAIService,
		body as ServiceBody,
		onResponse,
	);
}
