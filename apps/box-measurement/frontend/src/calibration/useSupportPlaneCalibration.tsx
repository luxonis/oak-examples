import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { z } from 'zod/v3';
import { runDaiServiceRequest } from '../backend/daiService';
import { useAdvertisedDaiService } from '../backend/useAdvertisedDaiService';
import { useDaiMutation } from '../backend/useDaiMutation';
import { useDaiQuery } from '../backend/useDaiQuery';
import { CALIBRATION_STATES } from './calibrationState';

const emptyBodySchema = z.object({}).strict();

const calibrationStatusSchema = z.object({
	state: z.enum(CALIBRATION_STATES),
	candidate_count: z.number(),
	selected_index: z.number(),
	camera_tilt_deg: z.number().nullable(),
	camera_distance_mm: z.number().nullable(),
	distance_offset_mm: z.number(),
	corrected_camera_distance_mm: z.number().nullable(),
});

export const MAX_DISTANCE_OFFSET_CM = 10;

const selectCandidateRequestSchema = z
	.object({ direction: z.union([z.literal(1), z.literal(-1)]) })
	.strict();

const getStatusService = {
	serviceName: 'getSupportPlaneCalibrationStatus',
	requestSchema: emptyBodySchema,
	responseSchema: calibrationStatusSchema,
} as const;

const confirmPlaneService = {
	serviceName: 'confirmSupportPlane',
	requestSchema: emptyBodySchema,
	responseSchema: emptyBodySchema,
} as const;

const retryCalibrationService = {
	serviceName: 'retrySupportPlaneCalibration',
	requestSchema: emptyBodySchema,
	responseSchema: emptyBodySchema,
} as const;

const selectCandidateService = {
	serviceName: 'selectSupportPlaneCandidate',
	requestSchema: selectCandidateRequestSchema,
	responseSchema: emptyBodySchema,
} as const;

const setPreviewActiveService = {
	serviceName: 'setSupportPlanePreviewActive',
	requestSchema: z.object({ active: z.boolean() }).strict(),
	responseSchema: emptyBodySchema,
} as const;

const setDistanceOffsetService = {
	serviceName: 'setSupportPlaneDistanceOffset',
	requestSchema: z
		.object({
			offset_mm: z
				.number()
				.gte(-MAX_DISTANCE_OFFSET_CM * 10)
				.lte(MAX_DISTANCE_OFFSET_CM * 10),
		})
		.strict(),
	responseSchema: emptyBodySchema,
} as const;

// Asks the pipeline to publish the plane preview cloud while mounted
export const useSupportPlanePreview = () => {
	const [error, setError] = useState<Error | null>(null);
	const { daiConnection, isServiceAdvertised } = useAdvertisedDaiService(
		setPreviewActiveService.serviceName,
	);

	useEffect(() => {
		if (!daiConnection || !isServiceAdvertised) {
			return;
		}

		const setPreviewActive = (active: boolean) =>
			runDaiServiceRequest(daiConnection, setPreviewActiveService, {
				active,
			});

		setPreviewActive(true).then(
			() => setError(null),
			(reason: Error) => setError(reason),
		);

		return () => {
			// Publish the preview cloud only while the calibration view requests it.
			setPreviewActive(false).catch(() => {});
		};
	}, [daiConnection, isServiceAdvertised]);

	return error;
};

// Status-only view of the calibration. Picks the view in App.
export const useSupportPlaneCalibrationStatus = () =>
	useDaiQuery({
		service: getStatusService,
		request: {},
		queryOptions: {
			refetchInterval: 1000,
			refetchIntervalInBackground: true,
		},
	});

export const useSupportPlaneCalibration = () => {
	const queryClient = useQueryClient();

	const statusQuery = useSupportPlaneCalibrationStatus();

	const invalidateStatus = async () => {
		await queryClient.invalidateQueries({
			queryKey: ['dai-service', getStatusService.serviceName],
		});
	};

	const confirmMutation = useDaiMutation({
		service: confirmPlaneService,
		mutationOptions: {
			onSuccess: invalidateStatus,
		},
	});

	const retryMutation = useDaiMutation({
		service: retryCalibrationService,
		mutationOptions: {
			onSuccess: invalidateStatus,
		},
	});

	const selectMutation = useDaiMutation({
		service: selectCandidateService,
		mutationOptions: {
			onSuccess: invalidateStatus,
		},
	});

	const distanceOffsetMutation = useDaiMutation({
		service: setDistanceOffsetService,
		mutationOptions: {
			onSuccess: invalidateStatus,
		},
	});

	return {
		statusQuery,
		confirmMutation,
		retryMutation,
		selectMutation,
		distanceOffsetMutation,
	};
};
