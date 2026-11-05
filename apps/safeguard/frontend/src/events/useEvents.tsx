import { z } from "zod/v3";

import { useDaiQuery } from "../backend/useDaiQuery";

const getEventsRequestSchema = z
    .object({
        offset: z.number().int().nonnegative().optional(),
        limit: z.number().int().positive().optional(),
    })
    .strict();

const eventFileSchema = z.object({
    name: z.string(),
    path: z.string(),
});

const eventTypeSchema = z.enum(["WARNING", "DANGER"]);

const eventSchema = z.object({
    id: z.number().int().nonnegative(),
    triggered_at: z.coerce.date(),
    frame_timestamp_seconds: z.number(),
    event_type: eventTypeSchema,
    files: z.array(eventFileSchema),
});

const getEventsResponseSchema = z.object({
    events: z.array(eventSchema),
    total_count: z.number().int().nonnegative(),
});

const getEventsService = {
    serviceName: "getEvents",
    requestSchema: getEventsRequestSchema,
    responseSchema: getEventsResponseSchema,
} as const;

export type EventFile = z.infer<typeof eventFileSchema>;
export type EventType = z.infer<typeof eventTypeSchema>;
export type EventRecord = z.infer<typeof eventSchema>;

type UseEventsParams = z.input<typeof getEventsRequestSchema>;

export const useEvents = (request: UseEventsParams = {}) => {
    const eventsQuery = useDaiQuery({
        service: getEventsService,
        request,
        queryOptions: { refetchInterval: 3000 },
    });

    return {
        eventsQuery,
    };
};
