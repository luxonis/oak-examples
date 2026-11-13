import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { z } from 'zod/v3';
import {
	type DAIServiceDefinition,
	daiServiceQueryKey,
	emptyBodySchema,
	runDaiServiceRequest,
} from '../backend/daiService';
import { useAdvertisedDaiService } from '../backend/useAdvertisedDaiService';
import { useDaiMutation } from '../backend/useDaiMutation';
import { useDaiQuery } from '../backend/useDaiQuery';
import { cmToMm } from '../units';
import { SUPPORT_PLANE_CALIBRATION_STATES } from './supportPlaneCalibrationState';

const supportPlaneCalibrationStatusSchema = z.object({
	state: z.enum(SUPPORT_PLANE_CALIBRATION_STATES),
	candidate_count: z.number(),
	selected_index: z.number(),
	camera_tilt_deg: z.number().nullable(),
	camera_distance_mm: z.number().nullable(),
	distance_offset_mm: z.number(),
	corrected_camera_distance_mm: z.number().nullable(),
});

export const MAX_DISTANCE_OFFSET_CM = 10;

const selectSupportPlaneCandidateRequestSchema = z
	.object({ direction: z.union([z.literal(1), z.literal(-1)]) })
	.strict();

const getStatusService = {
	serviceName: 'getSupportPlaneCalibrationStatus',
	requestSchema: emptyBodySchema,
	responseSchema: supportPlaneCalibrationStatusSchema,
} as const;

const confirmSupportPlaneService = {
	serviceName: 'confirmSupportPlane',
	requestSchema: emptyBodySchema,
	responseSchema: emptyBodySchema,
} as const;

const retrySupportPlaneCalibrationService = {
	serviceName: 'retrySupportPlaneCalibration',
	requestSchema: emptyBodySchema,
	responseSchema: emptyBodySchema,
} as const;

const selectSupportPlaneCandidateService = {
	serviceName: 'selectSupportPlaneCandidate',
	requestSchema: selectSupportPlaneCandidateRequestSchema,
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
				.gte(-cmToMm(MAX_DISTANCE_OFFSET_CM))
				.lte(cmToMm(MAX_DISTANCE_OFFSET_CM)),
		})
		.strict(),
	responseSchema: emptyBodySchema,
} as const;

// Asks the pipeline to publish the support plane preview cloud while mounted
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
			// Publish the preview cloud only while the support plane calibration view requests it.
			setPreviewActive(false).catch(() => {});
		};
	}, [daiConnection, isServiceAdvertised]);

	return error;
};

// Status-only view of support plane calibration. Picks the view in App.
export const useSupportPlaneCalibrationStatus = () =>
	useDaiQuery({
		service: getStatusService,
		request: {},
		queryOptions: {
			refetchInterval: 1000,
			refetchIntervalInBackground: true,
		},
	});

// A mutation that refreshes the polled status once the backend has applied it
const useStatusChangingMutation = <TService extends DAIServiceDefinition>(
	service: TService,
) => {
	const queryClient = useQueryClient();

	return useDaiMutation({
		service,
		mutationOptions: {
			onSuccess: async () => {
				await queryClient.invalidateQueries({
					queryKey: daiServiceQueryKey(getStatusService),
				});
			},
		},
	});
};

export const useSupportPlaneCalibration = () => {
	const statusQuery = useSupportPlaneCalibrationStatus();
	const confirmMutation = useStatusChangingMutation(confirmSupportPlaneService);
	const retryMutation = useStatusChangingMutation(
		retrySupportPlaneCalibrationService,
	);
	const selectMutation = useStatusChangingMutation(
		selectSupportPlaneCandidateService,
	);

	return {
		statusQuery,
		confirmMutation,
		retryMutation,
		selectMutation,
	};
};

// The backend clears the distance offset whenever support plane calibration
// restarts, and the polled status reports the cleared value.
export const useSetDistanceOffset = () =>
	useStatusChangingMutation(setDistanceOffsetService);
