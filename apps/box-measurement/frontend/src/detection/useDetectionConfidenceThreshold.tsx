import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { z } from 'zod/v3';

import { useDaiMutation } from '../backend/useDaiMutation';
import { useDaiQuery } from '../backend/useDaiQuery';

const thresholdSchema = z
	.object({ threshold: z.number().gte(0).lte(1) })
	.strict();

const getThresholdService = {
	serviceName: 'getDetectionConfidenceThreshold',
	requestSchema: z.object({}).strict(),
	responseSchema: thresholdSchema,
} as const;

const setThresholdService = {
	serviceName: 'setDetectionConfidenceThreshold',
	requestSchema: thresholdSchema,
	responseSchema: z.object({}).strict(),
} as const;

// Applied to the running pipeline without a restart; kept in memory only.
export const useSetDetectionConfidenceThreshold = () => {
	const queryClient = useQueryClient();

	return useDaiMutation({
		service: setThresholdService,
		mutationOptions: {
			onSettled: async () => {
				await queryClient.invalidateQueries({
					queryKey: ['dai-service', getThresholdService.serviceName],
				});
			},
		},
	});
};

// A slider draft; only apply() changes the running threshold.
export const useDetectionConfidenceThresholdDraft = () => {
	const thresholdQuery = useDaiQuery({
		service: getThresholdService,
		request: {},
	});
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
		value: draft ?? thresholdQuery.data?.threshold,
		setValue: setDraft,
		apply,
		error: setThresholdMutation.error,
	};
};
