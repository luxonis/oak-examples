import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Switch } from '@luxonis/ui-components';
import { useCallback, useEffect, useRef, useState } from 'react';
import { CircleLoader } from './CircleLoader.tsx';
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

	const streamContainerRef = useRef<HTMLDivElement>(null);

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
		<main className="flex h-screen w-screen overflow-hidden p-8">
			<div className="relative min-w-0 flex-1" ref={streamContainerRef}>
				<Streams allowedTopics={['Video']} defaultTopics={['Video']} />
			</div>

			<div className="mx-8 w-px shrink-0 bg-border" />

			<aside className="flex max-h-full w-[360px] shrink-0 flex-col gap-6 overflow-y-auto pr-3">
				<div className="flex flex-col gap-3">
					<h1 className="text-2xl font-bold">QR Tiling Detector</h1>
					<p className="text-sm leading-6 text-muted-foreground">
						High-resolution QR detection with configurable tiled inference.
					</p>
				</div>

				{!paramsLoaded || !tilingParams ? (
					<div className="flex min-h-[260px] flex-col items-center justify-center gap-4 text-muted-foreground">
						<CircleLoader />
						<span>Loading tiling configuration...</span>
					</div>
				) : (
					<>
						<section className="flex flex-col gap-4 border-t border-border pt-4">
							<div className="flex items-center justify-between gap-4">
								<div className="flex flex-col gap-1">
									<h2 className="font-semibold">QR Code Configuration</h2>
									<span className="text-sm text-muted-foreground">
										Decode QR contents from detected tiles.
									</span>
								</div>
								<Switch
									value={decodeEnabled}
									onChange={(newState) => {
										setDecodeEnabled(newState);
										sendQRConfig(newState);
									}}
								/>
							</div>
						</section>

						<TilingControl initialParams={tilingParams} />
					</>
				)}

				<div
					className={`mt-auto flex items-center gap-2 pt-4 ${
						connection.connected ? 'text-success' : 'text-destructive'
					}`}
				>
					<div
						className={`h-3 w-3 rounded-full ${
							connection.connected ? 'bg-success' : 'bg-destructive'
						}`}
					/>
					<span>{connection.connected ? 'Connected' : 'Disconnected'}</span>
				</div>
			</aside>
		</main>
	);
}

export default App;
