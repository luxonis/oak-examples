import { z } from 'zod/v3';
import { emptyBodySchema } from './backend/daiService';

const planeSchema = z.object({
	normal: z.array(z.number()),
	offset_mm: z.number(),
});

const candidateSchema = z.object({
	index: z.number().int().nonnegative(),
	plane: planeSchema,
	inlier_count: z.number(),
	inlier_ratio: z.number(),
	recommended: z.boolean(),
});

const stateSchema = z.object({
	calibration: z.object({
		phase: z.enum(['idle', 'calibrating', 'choosing', 'ready', 'failed']),
		generation: z.number().int().nonnegative(),
		message: z.string(),
		selected: z.number().int().nullable(),
		plane: planeSchema.nullable(),
		candidates: z.array(candidateSchema),
	}),
	error: z.string().nullable(),
	frame_sequence: z.number().nullable(),
	frame: z.object({ message: z.string() }).nullable(),
	capture: z.object({
		configured_fps: z.number(),
	}),
	rates: z.object({
		source_fps: z.number().nullable(),
		measurement_fps: z.number().nullable(),
	}),
});

export type ParcelState = z.infer<typeof stateSchema>;
export type PlaneCandidate = z.infer<typeof candidateSchema>;

const candidateRequestSchema = z
	.object({
		generation: z.number().int().nonnegative(),
		index: z.number().int().nonnegative(),
	})
	.strict();

export const getParcelState = {
	serviceName: 'getParcelState',
	requestSchema: emptyBodySchema,
	responseSchema: stateSchema,
} as const;

export const calibrateSupportPlane = {
	serviceName: 'calibrateSupportPlane',
	requestSchema: emptyBodySchema,
	responseSchema: z.object({ ok: z.literal(true) }),
} as const;

export const selectSupportPlane = {
	serviceName: 'selectSupportPlane',
	requestSchema: candidateRequestSchema,
	responseSchema: z.object({ ok: z.literal(true) }),
} as const;

export const getSupportPlanePreview = {
	serviceName: 'getSupportPlanePreview',
	requestSchema: candidateRequestSchema,
	responseSchema: z.object({ jpeg: z.string() }),
} as const;
