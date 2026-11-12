import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { z } from "zod/v3";

import { useDaiMutation } from "../backend/useDaiMutation";
import { useSettings } from "../settings/useSettings";

const setThresholdService = {
    serviceName: "setDetectionConfidenceThreshold",
    requestSchema: z.object({ threshold: z.number().gte(0).lte(1) }).strict(),
    responseSchema: z.object({}).strict(),
} as const;

// Applied to the running pipeline without a restart; also persisted in settings.
export const useSetDetectionConfidenceThreshold = () => {
    const queryClient = useQueryClient();

    return useDaiMutation({
        service: setThresholdService,
        mutationOptions: {
            onSettled: async () => {
                await queryClient.invalidateQueries({
                    queryKey: ["dai-service", "getSettings"],
                });
            },
        },
    });
};

// A slider draft; only apply() changes the saved and running threshold.
export const useDetectionConfidenceThresholdDraft = () => {
    const { settingsQuery } = useSettings();
    const setThresholdMutation = useSetDetectionConfidenceThreshold();
    const [draft, setDraft] = useState<number | null>(null);

    const apply = (threshold: number) => {
        setThresholdMutation.mutate(
            { threshold },
            {
                // Keep a newer drag that started while this request was pending.
                onSettled: () =>
                    setDraft((current) => (current === threshold ? null : current)),
            },
        );
    };

    return {
        value: draft ?? settingsQuery.data?.detection_confidence_threshold,
        setValue: setDraft,
        apply,
        error: setThresholdMutation.error,
    };
};
