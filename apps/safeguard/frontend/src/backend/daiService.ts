import { DAIConnection, DAIResponse } from "@luxonis/depthai-viewer-common";
import { z } from "zod/v3";

export type DAIRequestBody = Record<string, unknown> | string | number;

export type DAIServiceDefinition<
    TRequest extends DAIRequestBody = DAIRequestBody,
    TResponse = unknown,
> = {
    serviceName: string;
    requestSchema: z.ZodType<TRequest>;
    responseSchema: z.ZodType<TResponse>;
};

export type DAIServiceRequest<TService extends DAIServiceDefinition> = z.input<
    TService["requestSchema"]
>;

export type DAIServiceResponse<TService extends DAIServiceDefinition> =
    z.output<TService["responseSchema"]>;

export const getDaiError = (
    serviceName: string,
    response?: DAIResponse<unknown> | null,
) => {
    const fallbackMessage = `${serviceName} request failed`;

    if (!response) {
        return new Error(fallbackMessage);
    }

    if (typeof response.error === "string" && response.error.length > 0) {
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

export const runDaiServiceRequest = async <TService extends DAIServiceDefinition>(
    daiConnection: DAIConnection,
    service: TService,
    request: DAIServiceRequest<TService>,
): Promise<DAIServiceResponse<TService>> => {
    const validatedRequest = service.requestSchema.parse(request);

    const response = await new Promise<DAIResponse<unknown>>(
        (resolve, reject) => {
            daiConnection.postToService(
                service.serviceName as never,
                validatedRequest,
                resolve,
                (failedResponse) =>
                    reject(getDaiError(service.serviceName, failedResponse)),
            );
        },
    );

    if (response.error) {
        throw getDaiError(service.serviceName, response);
    }

    return service.responseSchema.parse(
        response,
    ) as DAIServiceResponse<TService>;
};
