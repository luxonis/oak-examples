import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import {
    DAIServiceDefinition,
    DAIServiceResponse,
    DAIServiceRequest,
    runDaiServiceRequest,
} from "./daiService";
import { useAdvertisedDaiService } from "./useAdvertisedDaiService";

type UseDaiQueryOptions<TService extends DAIServiceDefinition> = {
    service: TService;
    request: DAIServiceRequest<TService>;
    queryOptions?: Omit<
        UseQueryOptions<DAIServiceResponse<TService>>,
        "queryKey" | "queryFn"
    >;
};

export const useDaiQuery = <TService extends DAIServiceDefinition>({
    service,
    request,
    queryOptions,
}: UseDaiQueryOptions<TService>) => {
    const { daiConnection, isServiceAdvertised } = useAdvertisedDaiService(
        service.serviceName,
    );

    return useQuery({
        queryKey: ["dai-service", service.serviceName, request],
        queryFn: async () => {
            if (!daiConnection) {
                throw new Error("No DAI connection");
            }

            const res = await runDaiServiceRequest(
                daiConnection,
                service,
                request,
            );
            return res;
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
