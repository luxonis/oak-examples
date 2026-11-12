import { z } from "zod/v3";

type ValidationContext = {
    addIssue: (issue: {
        code: "custom";
        message: string;
        path: Array<string | number>;
    }) => void;
};

type SettingsCrossFieldValues = {
    event_video_pre_trigger_sec: number;
    event_video_duration_sec: number;
};

const addSettingsCrossFieldIssues = (
    {
        event_video_pre_trigger_sec,
        event_video_duration_sec,
    }: SettingsCrossFieldValues,
    context: ValidationContext,
) => {
    if (event_video_duration_sec <= event_video_pre_trigger_sec) {
        context.addIssue({
            code: "custom",
            message:
                "Event video length must be greater than the pre-trigger length",
            path: ["event_video_duration_sec"],
        });
    }
};

export const settingsSchema = z
    .object({
        fps: z.coerce.number().int().gte(5).lte(30),
        detection_confidence_threshold: z.coerce.number().gte(0).lte(1),
        event_saving_enabled: z.boolean(),
        save_failed_events: z.boolean(),
        event_storage_max_gb: z.coerce.number().positive(),
        event_video_pre_trigger_sec: z.coerce.number().int().gte(0),
        event_video_duration_sec: z.coerce.number().int().positive(),
    })
    .strict()
    .superRefine(addSettingsCrossFieldIssues);

export type Settings = z.output<typeof settingsSchema>;
export type SettingsFormValues = Settings;
