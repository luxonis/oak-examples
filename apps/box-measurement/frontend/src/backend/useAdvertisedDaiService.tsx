import {
	type DAIConnection,
	useDaiConnection,
} from '@luxonis/depthai-viewer-common';
import { useEffect, useState } from 'react';

import { isDaiServiceAdvertised } from './daiService';

type AdvertisedServiceState = {
	connection: DAIConnection;
	serviceName: string;
};

export const useAdvertisedDaiService = (serviceName: string) => {
	const { daiConnection } = useDaiConnection();
	const [advertisedService, setAdvertisedService] =
		useState<AdvertisedServiceState | null>(null);

	const isServiceAdvertised =
		daiConnection !== undefined &&
		daiConnection !== null &&
		advertisedService?.connection === daiConnection &&
		advertisedService?.serviceName === serviceName;

	useEffect(() => {
		if (!daiConnection) {
			return;
		}

		const stopPolling = (
			intervalId: number | null,
			timeoutId: number | null,
		) => {
			if (intervalId !== null) {
				window.clearInterval(intervalId);
			}

			if (timeoutId !== null) {
				window.clearTimeout(timeoutId);
			}
		};

		const checkServiceAdvertisement = () => {
			const isAdvertised = isDaiServiceAdvertised(daiConnection, serviceName);

			if (isAdvertised) {
				setAdvertisedService((current) => {
					if (
						current?.connection === daiConnection &&
						current?.serviceName === serviceName
					) {
						return current;
					}

					return {
						connection: daiConnection,
						serviceName,
					};
				});
			}

			return isAdvertised;
		};

		const pollServiceAdvertisement = () => {
			if (checkServiceAdvertisement()) {
				stopPolling(intervalId, timeoutId);
			}
		};

		const intervalId = window.setInterval(pollServiceAdvertisement, 100);
		const timeoutId = window.setTimeout(pollServiceAdvertisement, 0);

		return () => {
			stopPolling(intervalId, timeoutId);
		};
	}, [daiConnection, serviceName]);

	return {
		daiConnection,
		isServiceAdvertised,
	};
};
