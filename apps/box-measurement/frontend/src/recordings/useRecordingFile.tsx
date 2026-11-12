import { z } from "zod/v3";

import { useDaiBinaryQuery } from "../backend/useDaiBinaryQuery";

const getRecordingFileRequestSchema = z.object({
    filename: z.string().min(1),
});

const getRecordingFileService = {
    serviceName: "getRecordingFile",
    requestSchema: getRecordingFileRequestSchema,
} as const;

export const useRecordingFile = (filename: string | null | undefined) => {
    const recordingFileQuery = useDaiBinaryQuery({
        service: getRecordingFileService,
        request: {
            filename: filename ?? "",
        },
        queryOptions: {
            enabled: !!filename,
            staleTime: Infinity,
            refetchOnWindowFocus: false,
            refetchOnReconnect: false,
            refetchOnMount: false,
            retry: false,
        },
    });

    return { recordingFileQuery };
};
