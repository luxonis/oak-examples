import { z } from "zod/v3";

import { useDaiQuery } from "../backend/useDaiQuery";

const emptyBodySchema = z.object({}).strict();

const storageInfoSchema = z.object({
    total_bytes: z.number().nonnegative(),
    free_bytes: z.number().nonnegative(),
    available_bytes: z.number().nonnegative(),
    recordings_bytes: z.number().nonnegative(),
    events_bytes: z.number().nonnegative(),
    min_free_floor_bytes: z.number().nonnegative(),
});

const getStorageInfoService = {
    serviceName: "getStorageInfo",
    requestSchema: emptyBodySchema,
    responseSchema: storageInfoSchema,
} as const;

export type StorageInfo = z.infer<typeof storageInfoSchema>;

export const useStorageInfo = () => {
    const storageInfoQuery = useDaiQuery({
        service: getStorageInfoService,
        request: {},
        queryOptions: {
            staleTime: 5_000,
        },
    });

    return { storageInfoQuery };
};
