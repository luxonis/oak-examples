import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod/v3";

import { useDaiMutation } from "../backend/useDaiMutation";

const deleteEventRequestSchema = z.object({
    id: z.number().int().nonnegative(),
});

const deleteEventResponseSchema = z.object({
    deleted: z.boolean(),
});

const deleteEventService = {
    serviceName: "deleteEvent",
    requestSchema: deleteEventRequestSchema,
    responseSchema: deleteEventResponseSchema,
} as const;

export const useDeleteEvent = () => {
    const queryClient = useQueryClient();

    const deleteEventMutation = useDaiMutation({
        service: deleteEventService,
        mutationOptions: {
            onSuccess: () => {
                queryClient.invalidateQueries({
                    queryKey: ["dai-service", "getEvents"],
                });
            },
        },
    });

    return {
        deleteEventMutation,
    };
};
