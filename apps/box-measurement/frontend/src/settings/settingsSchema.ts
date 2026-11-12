import { z } from "zod/v3";

export const settingsSchema = z
    .object({
        fps: z.coerce.number().int().gte(5).lte(30),
        detection_confidence_threshold: z.coerce.number().gte(0).lte(1),
    })
    .strict();

export type Settings = z.output<typeof settingsSchema>;
export type SettingsFormValues = Settings;
