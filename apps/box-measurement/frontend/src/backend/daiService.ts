import type {
	DAIConnection,
	DAIResponse,
} from '@luxonis/depthai-viewer-common';
import { z } from 'zod/v3';

export type DAIRequestBody = Record<string, unknown> | string | number;

export type DAIServiceDefinition<
	TRequest extends DAIRequestBody = DAIRequestBody,
	TResponse = unknown,
> = {
	serviceName: string;
	requestSchema: z.ZodType<TRequest>;
	responseSchema: z.ZodType<TResponse>;
};

/** Request or response body for services that take or return no fields. */
export const emptyBodySchema = z.object({}).strict();

export type DAIServiceRequest<TService extends DAIServiceDefinition> = z.input<
	TService['requestSchema']
>;

export type DAIServiceResponse<TService extends DAIServiceDefinition> =
	z.output<TService['responseSchema']>;

/** Query key prefix shared by every query of one service, for invalidation. */
export const daiServiceQueryKey = (
	service: Pick<DAIServiceDefinition, 'serviceName'>,
) => ['dai-service', service.serviceName] as const;

export const getDaiError = (
	serviceName: string,
	response?: DAIResponse<unknown> | null,
) => {
	const fallbackMessage = `${serviceName} request failed`;

	if (!response) {
		return new Error(fallbackMessage);
	}

	if (typeof response.error === 'string' && response.error.length > 0) {
		return new Error(response.error);
	}

	if (response.message) {
		return new Error(response.message);
	}

	return new Error(fallbackMessage);
};

export const isDaiServiceAdvertised = (
	daiConnection: DAIConnection,
	serviceName: string,
) => {
	return daiConnection.canPollService(serviceName as never);
};

export const assertDaiServiceAdvertised = (
	daiConnection: DAIConnection,
	serviceName: string,
) => {
	if (!isDaiServiceAdvertised(daiConnection, serviceName)) {
		throw new Error(`Service "${serviceName}" was not advertised`);
	}
};

export const runDaiServiceRequest = async <
	TService extends DAIServiceDefinition,
>(
	daiConnection: DAIConnection,
	service: TService,
	request: DAIServiceRequest<TService>,
): Promise<DAIServiceResponse<TService>> => {
	const validatedRequest = service.requestSchema.parse(request);

	const response = await new Promise<DAIResponse<unknown>>(
		(resolve, reject) => {
			daiConnection
				.postToService(
					service.serviceName as never,
					validatedRequest,
					resolve,
					(failedResponse) =>
						reject(getDaiError(service.serviceName, failedResponse)),
				)
				// Rejects when the request cannot be sent, e.g. while disconnected
				.catch(reject);
		},
	);

	if (response.error) {
		throw getDaiError(service.serviceName, response);
	}

	return service.responseSchema.parse(response) as DAIServiceResponse<TService>;
};
