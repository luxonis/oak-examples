import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod/v3";
import { useDaiMutation } from "../backend/useDaiMutation";
import { useDaiQuery } from "../backend/useDaiQuery";
import { settingsSchema } from "./settingsSchema";

const emptyBodySchema = z.object({}).strict();

const getSettingsService = {
    serviceName: "getSettings",
    requestSchema: emptyBodySchema,
    responseSchema: settingsSchema,
} as const;

const updateSettingsService = {
    serviceName: "updateSettings",
    requestSchema: settingsSchema,
    responseSchema: emptyBodySchema,
} as const;

export const useSettings = () => {
    const queryClient = useQueryClient();

    const settingsQuery = useDaiQuery({
        service: getSettingsService,
        request: {},
    });

    const updateSettingsMutation = useDaiMutation({
        service: updateSettingsService,
        mutationOptions: {
            onSuccess: async () => {
                await queryClient.invalidateQueries({
                    queryKey: ["dai-service", getSettingsService.serviceName],
                });
            },
        },
    });

    return {
        settingsQuery,
        updateSettingsMutation,
    };
};
