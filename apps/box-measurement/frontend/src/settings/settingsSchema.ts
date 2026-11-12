import { z } from "zod/v3";

export const settingsSchema = z
    .object({
        fps: z.coerce.number().int().gte(5).lte(30),
        detection_confidence_threshold: z.coerce.number().gte(0).lte(1),
        continuous_recording_enabled: z.boolean(),
        continuous_recording_chunk_length_sec: z.coerce.number().int().positive(),
        continuous_recording_max_storage_gb: z.coerce.number().positive(),
    })
    .strict();

export type Settings = z.output<typeof settingsSchema>;
export type SettingsFormValues = Settings;
