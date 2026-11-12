import { z } from "zod/v3";

import { useDaiBinaryQuery } from "../backend/useDaiBinaryQuery";

const getEventFileRequestSchema = z.object({
    path: z.string().min(1),
});

const getEventFileService = {
    serviceName: "getEventFile",
    requestSchema: getEventFileRequestSchema,
} as const;

export const useEventFile = (path: string | null | undefined) => {
    const eventFileQuery = useDaiBinaryQuery({
        service: getEventFileService,
        request: {
            path: path ?? "",
        },
        queryOptions: {
            enabled: !!path,
            staleTime: Infinity,
            refetchOnWindowFocus: false,
            refetchOnReconnect: false,
            refetchOnMount: false,
            retry: false,
        },
    });

    return {
        eventFileQuery,
    };
};
