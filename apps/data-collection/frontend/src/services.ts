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

export const QNN_PREPARATION_EVENT = 'qnn-preparation';
const QNN_SERVICES = new Set<DataCollectionService>([
	'Class Update Service',
	'Image Upload Service',
	'BBox Prompt Service',
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

export function postToDataCollectionService(
	connection: DAIConnection | null,
	service: DataCollectionService,
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
