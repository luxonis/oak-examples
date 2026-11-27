import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Card, Flex, Label, SubLabel, Switch } from '@luxonis/ui-components';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AppShell, LoadingState, Steps } from './AppShell.tsx';
import { useNotifications } from './Notifications.tsx';
import { TilingControl, type TilingParams } from './TilingControl.tsx';
import { fetchQRTilingService, postToQRTilingService } from './services.ts';

export type CurrentParamsResponse = {
	tiling: TilingParams;
	decoder: boolean;
};

function App() {
	const connection = useDaiConnection();
	const { notify } = useNotifications();
	const previousConnectedRef = useRef<boolean | null>(null);

	const [paramsLoaded, setParamsLoaded] = useState(false);
	const [tilingParams, setTilingParams] = useState<TilingParams | null>(null);
	const [decodeEnabled, setDecodeEnabled] = useState(false);

	const onCurrentParams = useCallback((response: CurrentParamsResponse) => {
		console.log('[Init] Returned tiling params:', response);
		setTilingParams(response.tiling);
		setDecodeEnabled(response.decoder);
		setParamsLoaded(true);
	}, []);

	useEffect(() => {
		connection.daiConnection?.setOnService(
			'Get Current Params Service',
			onCurrentParams,
		);
	}, [connection.daiConnection, onCurrentParams]);

	useEffect(() => {
		if (!connection.connected) {
			setParamsLoaded(false);
			return;
		}

		console.log('[Init] Fetching tiling params...');
		fetchQRTilingService(
			connection.daiConnection,
			'Get Current Params Service',
		);
	}, [connection.connected, connection.daiConnection]);

	useEffect(() => {
		const previousConnected = previousConnectedRef.current;
		previousConnectedRef.current = connection.connected;

		if (connection.connected && previousConnected !== true) {
			notify('Connected to device', { type: 'success', durationMs: 1800 });
		}
		if (!connection.connected && previousConnected === true) {
			notify('Disconnected from device', {
				type: 'warning',
				durationMs: 1800,
			});
		}
	}, [connection.connected, notify]);

	const sendQRConfig = useCallback(
		(state: boolean) => {
			if (!connection.connected) {
				notify('Not connected to device. Unable to update QR decoding.', {
					type: 'error',
				});
				return;
			}

			postToQRTilingService(
				connection.daiConnection,
				'QR Config Service',
				{ state },
				() => {
					notify(`QR decoding ${state ? 'enabled' : 'disabled'}`, {
						type: 'success',
						durationMs: 2500,
					});
				},
			);
		},
		[connection.connected, connection.daiConnection, notify],
	);

	return (
		<AppShell
			title="QR Tiling Detector"
			streams={<Streams allowedTopics={['Video']} defaultTopics={['Video']} />}
		>
			<>
				<Card title="How to use" variant="outline" intent="white">
					<Steps
						items={[
							'Set the rows, columns, and overlap of the tile grid.',
							'Optionally merge neighboring tiles into larger tiles.',
							'Select Update tiling to apply the grid to the stream.',
						]}
					/>
				</Card>

				{!paramsLoaded || !tilingParams ? (
					<LoadingState title="Loading tiling configuration" />
				) : (
					<>
						<Card title="QR decoding" variant="outline" intent="white">
							<Flex direction="row" align="center" justify="between" gap="sm">
								<Flex direction="column">
									<Label id="qr-decode-label" text="Decode QR contents" />
									<SubLabel text="Read the contents of QR codes found in the tiles." />
								</Flex>
								<Switch
									aria-labelledby="qr-decode-label"
									value={decodeEnabled}
									showActiveLabelOnly
									onChange={(newState) => {
										setDecodeEnabled(newState);
										sendQRConfig(newState);
									}}
								/>
							</Flex>
						</Card>

						<Card title="Tiling" variant="outline" intent="white">
							<TilingControl initialParams={tilingParams} />
						</Card>
					</>
				)}
			</>
		</AppShell>
	);
}

export default App;
