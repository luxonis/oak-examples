import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button } from '@luxonis/ui-components';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ClickCatcher } from './ClickOverlay.tsx';
import { DistanceDisplay } from './DistanceDisplay.tsx';
import { postToP2PMeasurementService } from './services.ts';

interface DistanceResponse {
	ok?: boolean;
	distance?: number | null;
	std_deviation?: number | null;
	has_invalid_depth?: boolean;
}

interface TrackingStatusResponse {
	ok?: boolean;
	tracking_enabled?: boolean;
}

function decodePayload(response: unknown): unknown {
	let payload = response;

	if (
		typeof payload === 'object' &&
		payload !== null &&
		Object.hasOwn(payload, 'data')
	) {
		payload = (payload as { data: unknown }).data;
	}

	if (typeof payload === 'string') {
		return JSON.parse(payload);
	}

	if (payload instanceof DataView) {
		return JSON.parse(new TextDecoder().decode(payload));
	}

	if (payload instanceof ArrayBuffer) {
		return JSON.parse(new TextDecoder('utf-8').decode(payload));
	}

	if (ArrayBuffer.isView(payload)) {
		return JSON.parse(
			new TextDecoder('utf-8').decode(
				new Uint8Array(payload.buffer, payload.byteOffset, payload.byteLength),
			),
		);
	}

	return payload;
}

function parseObject<T extends object>(response: unknown): T | null {
	try {
		const payload = decodePayload(response);
		return typeof payload === 'object' && payload !== null
			? (payload as T)
			: null;
	} catch (error) {
		console.error('[P2P] Failed to parse service response:', error);
		return null;
	}
}

function App() {
	const connection = useDaiConnection();
	const viewerRef = useRef<HTMLDivElement>(null);
	const [pointCount, setPointCount] = useState(0);
	const [currentDistance, setCurrentDistance] = useState<number | null>(null);
	const [currentStdDeviation, setCurrentStdDeviation] = useState<number | null>(
		null,
	);
	const [hasInvalidDepth, setHasInvalidDepth] = useState(false);
	const [trackingEnabled, setTrackingEnabled] = useState(true);
	const [showInstructions, setShowInstructions] = useState(false);
	const topicGroups = useMemo(() => ({ images: 'Images', data: 'Data' }), []);

	const clearSelection = useCallback(() => {
		postToP2PMeasurementService(connection.daiConnection, 'Selection Service', {
			clear: true,
		});
		setPointCount(0);
		setCurrentDistance(null);
		setCurrentStdDeviation(null);
		setHasInvalidDepth(false);
	}, [connection.daiConnection]);

	const toggleTracking = () => {
		postToP2PMeasurementService(
			connection.daiConnection,
			'Toggle Tracking Service',
			{},
			(response) => {
				const parsedResponse = parseObject<TrackingStatusResponse>(response);

				if (parsedResponse?.ok) {
					setTrackingEnabled(parsedResponse.tracking_enabled ?? false);
				}
			},
		);
	};

	useEffect(() => {
		if (!connection.connected) return;

		const pollDistance = () => {
			postToP2PMeasurementService(
				connection.daiConnection,
				'Get Distance Service',
				{},
				(response) => {
					const parsedResponse = parseObject<DistanceResponse>(response);

					if (!parsedResponse?.ok) return;

					if (typeof parsedResponse.distance === 'number') {
						setCurrentDistance(parsedResponse.distance);
						setCurrentStdDeviation(parsedResponse.std_deviation ?? null);
						setHasInvalidDepth(parsedResponse.has_invalid_depth ?? false);
						return;
					}

					setCurrentDistance(null);
					setCurrentStdDeviation(null);
					setHasInvalidDepth(parsedResponse.has_invalid_depth ?? false);
				},
			);
		};

		const interval = window.setInterval(pollDistance, 50);
		return () => window.clearInterval(interval);
	}, [connection.connected, connection.daiConnection]);

	useEffect(() => {
		if (!connection.connected) return;

		postToP2PMeasurementService(
			connection.daiConnection,
			'Get Tracking Status Service',
			{},
			(response) => {
				const parsedResponse = parseObject<TrackingStatusResponse>(response);

				if (parsedResponse?.ok) {
					setTrackingEnabled(parsedResponse.tracking_enabled ?? false);
				}
			},
		);
	}, [connection.connected, connection.daiConnection]);

	useEffect(() => {
		const handleKeyPress = (event: KeyboardEvent) => {
			if (event.code === 'Space' && pointCount > 0) {
				event.preventDefault();
				clearSelection();
			}
		};

		window.addEventListener('keydown', handleKeyPress);
		return () => window.removeEventListener('keydown', handleKeyPress);
	}, [clearSelection, pointCount]);

	return (
		<main className="flex h-screen w-screen flex-row gap-6 overflow-auto bg-muted p-6">
			<div ref={viewerRef} className="relative min-w-[760px] flex-1 shrink-0">
				<Streams
					defaultTopics={['Video', 'Depth', 'Point Annotations']}
					topicGroups={topicGroups}
				/>
				<ClickCatcher
					containerRef={viewerRef}
					frameWidth={640}
					frameHeight={400}
					allowedPanelTitle="Video,Depth"
					onPointAdded={(count) => {
						if (count === -1) {
							setPointCount((previous) => previous + 1);
						} else {
							setPointCount(count);
						}
					}}
				/>
			</div>

			<div className="w-0.5 shrink-0 bg-border" />

			<aside className="flex max-h-full w-[420px] min-w-[360px] shrink-0 flex-col gap-5 overflow-y-auto pr-2 text-left">
				<h1 className="text-2xl font-bold">P2P Distance Measurement</h1>

				<section className="rounded-md border border-border bg-card p-4">
					<button
						className="flex w-full items-center justify-between text-left"
						type="button"
						onClick={() => setShowInstructions((visible) => !visible)}
					>
						<h2 className="m-0 font-semibold">Instructions</h2>
						<span className="text-sm font-semibold text-muted-foreground">
							{showInstructions ? 'Hide' : 'Show'}
						</span>
					</button>

					{showInstructions ? (
						<ol className="m-0 mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
							<li>Select the first point on the video or depth stream.</li>
							<li>Select the second point to calculate distance.</li>
							<li>Wait briefly for the measurement to stabilize.</li>
							<li>Press Space or right-click to clear points.</li>
						</ol>
					) : null}
				</section>

				<DistanceDisplay
					distance={currentDistance}
					stdDeviation={currentStdDeviation}
					pointCount={pointCount}
					hasInvalidDepth={hasInvalidDepth}
					trackingEnabled={trackingEnabled}
					onToggleTracking={toggleTracking}
				/>

				<Button
					className="w-fit"
					variant="outline"
					onClick={clearSelection}
					disabled={pointCount === 0}
				>
					Clear Points
				</Button>

				<div
					className={`mt-auto flex items-center gap-2 border-t border-border pt-4 text-sm ${
						connection.connected ? 'text-success' : 'text-destructive'
					}`}
				>
					<div
						className={`h-3 w-3 rounded-full ${
							connection.connected ? 'bg-success' : 'bg-destructive'
						}`}
					/>
					<span>
						{connection.connected ? 'Connected to device' : 'Disconnected'}
					</span>
				</div>
			</aside>
		</main>
	);
}

export default App;
