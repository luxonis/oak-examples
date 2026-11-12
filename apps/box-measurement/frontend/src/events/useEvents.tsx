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

const eventTypeSchema = z.enum([
    "SUCCESS",
    "INCOMPLETE",
    "FAILED_LOW_COVERAGE",
]);

const eventSchema = z.object({
    id: z.number().int().nonnegative(),
    created_at: z.coerce.date(),
    event_type: eventTypeSchema,
    track_id: z.number().int(),
    length_mm: z.number().nullable(),
    width_mm: z.number().nullable(),
    height_mm: z.number().nullable(),
    volume_mm3: z.number().nullable(),
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
    });

    return {
        eventsQuery,
    };
};
