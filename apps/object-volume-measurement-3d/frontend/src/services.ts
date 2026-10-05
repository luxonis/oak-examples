import type {
	DAIConnection,
	DAIResponse,
	DAIService,
} from '@luxonis/depthai-viewer-common';

export const OBJECT_VOLUME_SERVICES = [
	'Selection Service',
	'Class Update Service',
	'Threshold Update Service',
	'Measurement Method Service',
] as const;

export type ObjectVolumeService = (typeof OBJECT_VOLUME_SERVICES)[number];

type ServiceBody = Record<string, unknown> | string | number;

export function postToObjectVolumeService(
	connection: DAIConnection | null,
	service: ObjectVolumeService,
	body: unknown,
	onResponse: (response: DAIResponse<unknown>) => void = () => {},
) {
	void connection?.postToService(
		service as unknown as DAIService,
		body as ServiceBody,
		onResponse,
	);
}
