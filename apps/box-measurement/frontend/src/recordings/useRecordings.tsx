import { z } from "zod/v3";

import { useDaiQuery } from "../backend/useDaiQuery";

const getRecordingsRequestSchema = z.object({}).strict();

const recordingSchema = z.object({
    filename: z.string(),
    started_at: z.coerce.date(),
    ended_at: z.coerce.date(),
    size_bytes: z.number().int().nonnegative(),
});

const getRecordingsResponseSchema = z.object({
    recordings: z.array(recordingSchema),
});

const getRecordingsService = {
    serviceName: "getRecordings",
    requestSchema: getRecordingsRequestSchema,
    responseSchema: getRecordingsResponseSchema,
} as const;

export type Recording = z.infer<typeof recordingSchema>;

export const useRecordings = () => {
    const recordingsQuery = useDaiQuery({
        service: getRecordingsService,
        request: {},
    });

    return { recordingsQuery };
};
