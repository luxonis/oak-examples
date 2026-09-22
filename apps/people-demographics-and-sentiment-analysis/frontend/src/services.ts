import type {
	DAIConnection,
	DAIResponse,
	DAIService,
} from '@luxonis/depthai-viewer-common';

export const PEOPLE_ANALYTICS_SERVICES = ['Get Faces'] as const;

export type PeopleAnalyticsService = (typeof PEOPLE_ANALYTICS_SERVICES)[number];
export const PEOPLE_ANALYTICS_ACTIVE_SERVICES =
	PEOPLE_ANALYTICS_SERVICES as unknown as DAIService[];

type ServiceBody = Record<string, unknown> | string | number;

export function postToPeopleAnalyticsService(
	connection: DAIConnection | null,
	service: PeopleAnalyticsService,
	body: unknown,
	onResponse: (response: DAIResponse<unknown>) => void = () => {},
) {
	void connection?.postToService(
		service as unknown as DAIService,
		body as ServiceBody,
		onResponse,
	);
}
