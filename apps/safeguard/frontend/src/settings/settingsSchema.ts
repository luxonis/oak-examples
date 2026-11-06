import { z } from "zod/v3";

type ValidationContext = {
    addIssue: (issue: {
        code: "custom";
        message: string;
        path: Array<string | number>;
    }) => void;
};

type RoiLike = {
    distance_mm: number;
    x_min_mm: number;
    x_max_mm: number;
};

type SettingsCrossFieldValues = {
    danger_roi: RoiLike;
    warning_roi: RoiLike;
};

const addRoiOrderingIssues = (
    { x_min_mm, x_max_mm }: RoiLike,
    context: ValidationContext,
) => {
    if (x_min_mm >= x_max_mm) {
        context.addIssue({
            code: "custom",
            message: "x_min_mm must be less than x_max_mm",
            path: ["x_min_mm"],
        });
        context.addIssue({
            code: "custom",
            message: "x_min_mm must be less than x_max_mm",
            path: ["x_max_mm"],
        });
    }
};

const addSettingsCrossFieldIssues = (
    {
        danger_roi,
        warning_roi,
    }: SettingsCrossFieldValues,
    context: ValidationContext,
) => {
    if (danger_roi.distance_mm >= warning_roi.distance_mm) {
        context.addIssue({
            code: "custom",
            message: "Danger distance must be less than warning distance",
            path: ["danger_roi", "distance_mm"],
        });
    }

};

const roiSchema = z
    .object({
        distance_mm: z.coerce.number().positive(),
        x_min_mm: z.coerce.number(),
        x_max_mm: z.coerce.number(),
    })
    .strict()
    .superRefine(addRoiOrderingIssues);

export const settingsSchema = z
    .object({
        fps: z.coerce.number().int().gte(10).lte(30),
        generic_object_detection_enabled: z.boolean(),
        awareness_escalation_sec: z.coerce.number().int().positive(),
        deescalation_sec: z.coerce.number().int().positive(),
        danger_roi: roiSchema,
        warning_roi: roiSchema,
    })
    .strict()
    .superRefine(addSettingsCrossFieldIssues);

export type Settings = z.output<typeof settingsSchema>;
export type SettingsFormValues = Settings;
