import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod/v3";

import { useDaiMutation } from "../backend/useDaiMutation";
import { useDaiQuery } from "../backend/useDaiQuery";

const emptyBodySchema = z.object({}).strict();

const exportWarningSchema = z.object({
    code: z.string(),
    message: z.string(),
    suggested_action: z.string(),
    file: z.string().nullable(),
});

const eventArchiveSchema = z.object({
    filename: z.string(),
    host_path: z.string(),
    byte_size: z.number().int().nonnegative(),
    event_count: z.number().int().nonnegative(),
    created_at: z.coerce.date(),
    scp_command: z.string(),
    warnings: z.array(exportWarningSchema),
});

const eventExportStatusSchema = z.object({
    state: z.enum(["absent", "preparing", "ready", "failed"]),
    archive: eventArchiveSchema.nullable(),
    processed_event_count: z.number().int().nonnegative(),
    total_event_count: z.number().int().nonnegative(),
    failure_message: z.string().nullable(),
});

const getEventExportStatusService = {
    serviceName: "getEventExportStatus",
    requestSchema: emptyBodySchema,
    responseSchema: eventExportStatusSchema,
} as const;

const createEventExportService = {
    serviceName: "createEventExport",
    requestSchema: emptyBodySchema,
    responseSchema: eventExportStatusSchema,
} as const;

const deleteEventExportService = {
    serviceName: "deleteEventExport",
    requestSchema: emptyBodySchema,
    responseSchema: eventExportStatusSchema,
} as const;

const EXPORT_STATUS_POLL_INTERVAL_MS = 1_000;
const EXPORT_STATUS_IDLE_POLL_INTERVAL_MS = 5_000;

export type EventExportStatus = z.infer<typeof eventExportStatusSchema>;

export const useEventExport = () => {
    const queryClient = useQueryClient();
    // Must match the key useDaiQuery builds for getEventExportStatus
    const exportStatusQueryKey = [
        "dai-service",
        getEventExportStatusService.serviceName,
        {},
    ];

    const exportStatusQuery = useDaiQuery({
        service: getEventExportStatusService,
        request: {},
        queryOptions: {
            refetchInterval: (query) =>
                query.state.data?.state === "preparing"
                    ? EXPORT_STATUS_POLL_INTERVAL_MS
                    : EXPORT_STATUS_IDLE_POLL_INTERVAL_MS,
        },
    });

    // A status request already in flight must not overwrite the mutation result
    const cancelStatusRequests = () =>
        queryClient.cancelQueries({ queryKey: exportStatusQueryKey });

    // Both mutations return the new status: show it without waiting for a poll
    const createExportMutation = useDaiMutation({
        service: createEventExportService,
        mutationOptions: {
            onMutate: cancelStatusRequests,
            onSuccess: (status) => {
                queryClient.setQueryData(exportStatusQueryKey, status);
            },
        },
    });

    const deleteExportMutation = useDaiMutation({
        service: deleteEventExportService,
        mutationOptions: {
            onMutate: cancelStatusRequests,
            onSuccess: (status) => {
                queryClient.setQueryData(exportStatusQueryKey, status);
            },
        },
    });

    return { exportStatusQuery, createExportMutation, deleteExportMutation };
};
