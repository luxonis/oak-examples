import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { type UseMutationOptions, useMutation } from '@tanstack/react-query';

import {
	type DAIServiceDefinition,
	type DAIServiceRequest,
	type DAIServiceResponse,
	assertDaiServiceAdvertised,
	runDaiServiceRequest,
} from './daiService';

type UseDaiMutationOptions<
	TService extends DAIServiceDefinition,
	TContext = unknown,
> = {
	service: TService;
	mutationOptions?: Omit<
		UseMutationOptions<
			DAIServiceResponse<TService>,
			Error,
			DAIServiceRequest<TService>,
			TContext
		>,
		'mutationFn'
	>;
};

export const useDaiMutation = <
	TService extends DAIServiceDefinition,
	TContext = unknown,
>({
	service,
	mutationOptions,
}: UseDaiMutationOptions<TService, TContext>) => {
	const { daiConnection } = useDaiConnection();

	return useMutation({
		...mutationOptions,
		mutationFn: async (request) => {
			if (!daiConnection) {
				throw new Error('No DAI connection');
			}

			assertDaiServiceAdvertised(daiConnection, service.serviceName);

			return runDaiServiceRequest(daiConnection, service, request);
		},
	});
};
