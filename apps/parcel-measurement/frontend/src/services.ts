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
	overlays: z.object({ depth: z.boolean(), support_plane: z.boolean() }),
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

const dimensionsSchema = z.tuple([z.number(), z.number(), z.number()]);
const summarySchema = z.object({
	track_id: z.number().int().positive(),
	saved_at: z.string(),
	captured_at: z.string(),
	sequence: z.number().int(),
	dimensions_mm: dimensionsSchema,
	point_count: z.number().int().nonnegative(),
	revision: z.number().int().positive(),
	in_frame: z.boolean(),
});

const detailSchema = summarySchema.extend({
	in_frame: z.boolean().optional(),
	algorithm_id: z.string(),
	status: z.string(),
	candidate_id: z.number().int(),
	reference_frame: z.string(),
	source_timing: z.array(z.unknown()),
	support_plane: planeSchema,
	cuboid: z.object({
		base_center_mm: dimensionsSchema,
		length_axis: dimensionsSchema,
		width_axis: dimensionsSchema,
		up_axis: dimensionsSchema,
		dimensions_mm: dimensionsSchema,
		corners_mm: z.array(dimensionsSchema).length(8),
	}),
	point_cloud: z.object({
		encoding: z.literal('float32-le-base64'),
		count: z.number().int().nonnegative(),
		xyz: z.string(),
	}),
	capture_profile: z.record(z.unknown()),
	bbox_rgb: z.array(z.number()).length(4),
	video_sequence: z.number().int(),
	calibration_generation: z.number().int(),
	depth_correction: z.record(z.unknown()).nullable().optional(),
});

const trackRequestSchema = z
	.object({ track_id: z.number().int().positive() })
	.strict();

export type MeasurementSummary = z.infer<typeof summarySchema>;
export type MeasurementDetails = z.infer<typeof detailSchema>;

export const getMeasurements = {
	serviceName: 'getMeasurements',
	requestSchema: emptyBodySchema,
	responseSchema: z.object({
		items: z.array(summarySchema),
		saving_track_id: z.number().int().nullable(),
		pending_track_ids: z.array(z.number().int()),
		storage_error: z.string().nullable(),
	}),
} as const;

export const getMeasurement = {
	serviceName: 'getMeasurement',
	requestSchema: trackRequestSchema,
	responseSchema: z.object({ measurement: detailSchema }),
} as const;

export const requestMeasurementUpdate = {
	serviceName: 'requestMeasurementUpdate',
	requestSchema: trackRequestSchema,
	responseSchema: z.object({ ok: z.literal(true) }),
} as const;

export const setPreviewOptions = {
	serviceName: 'setPreviewOptions',
	requestSchema: z
		.object({ depth: z.boolean(), support_plane: z.boolean() })
		.strict(),
	responseSchema: z.object({ ok: z.literal(true) }),
} as const;
