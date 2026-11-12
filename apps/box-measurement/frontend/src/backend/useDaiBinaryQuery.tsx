import { useQuery, UseQueryOptions } from "@tanstack/react-query";

import {
    DAIBinaryServiceDefinition,
    DAIBinaryServiceRequest,
    DAIBinaryServiceResponse,
    runDaiBinaryServiceRequest,
} from "./daiService";
import { useAdvertisedDaiService } from "./useAdvertisedDaiService";

type UseDaiBinaryQueryOptions<TService extends DAIBinaryServiceDefinition> = {
    service: TService;
    request: DAIBinaryServiceRequest<TService>;
    queryOptions?: Omit<
        UseQueryOptions<DAIBinaryServiceResponse>,
        "queryKey" | "queryFn"
    >;
};

export const useDaiBinaryQuery = <
    TService extends DAIBinaryServiceDefinition,
>({
    service,
    request,
    queryOptions,
}: UseDaiBinaryQueryOptions<TService>) => {
    const { daiConnection, isServiceAdvertised } = useAdvertisedDaiService(
        service.serviceName,
    );

    return useQuery({
        queryKey: ["dai-binary-service", service.serviceName, request],
        queryFn: async () => {
            if (!daiConnection) {
                throw new Error("No DAI connection");
            }

            return runDaiBinaryServiceRequest(daiConnection, service, request);
        },
        ...queryOptions,
        enabled:
            !!daiConnection &&
            isServiceAdvertised &&
            (typeof queryOptions?.enabled === "function"
                ? queryOptions.enabled
                : queryOptions?.enabled ?? true),
    });
};
