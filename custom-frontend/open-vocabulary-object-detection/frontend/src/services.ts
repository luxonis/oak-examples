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

export const QNN_PREPARATION_EVENT = 'qnn-preparation';
const QNN_SERVICES = new Set<CustomService>([
	'Class Update Service',
	'Image Upload Service',
	'BBox Prompt Service',
	'Delete Image Prompt Service',
]);
const pendingQnnRequests = new Set<symbol>();

function emitQnnPreparation() {
	window.dispatchEvent(
		new CustomEvent(QNN_PREPARATION_EVENT, {
			detail: pendingQnnRequests.size > 0,
		}),
	);
}

export function clearQnnPreparation() {
	pendingQnnRequests.clear();
	emitQnnPreparation();
}

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
	if (!connection) return;
	const requestId = QNN_SERVICES.has(service) ? Symbol(service) : null;
	if (requestId) {
		pendingQnnRequests.add(requestId);
		emitQnnPreparation();
	}
	const finish = () => {
		if (requestId && pendingQnnRequests.delete(requestId)) emitQnnPreparation();
	};
	try {
		const request = connection.postToService(
			service as unknown as DAIService,
			body as ServiceBody,
			(response) => {
				finish();
				onResponse(response);
			},
		);
		void Promise.resolve(request).catch(finish);
	} catch (error) {
		finish();
		throw error;
	}
}
