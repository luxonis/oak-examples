import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Card } from '@luxonis/ui-components';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AppShell, Steps } from './AppShell.tsx';
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
		<AppShell
			title="Point-to-Point Distance Measurement"
			streams={
				<div ref={viewerRef} className="relative flex min-h-0 flex-1 flex-col">
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
			}
		>
			<Card title="How to use" variant="outline" intent="white">
				<Steps
					items={[
						'Click the first point on the Video or Depth stream.',
						'Click the second point to measure the distance between them.',
						'Wait briefly for the measurement to settle.',
						'Press Space or right-click the stream to clear the points.',
					]}
				/>
			</Card>

			<DistanceDisplay
				distance={currentDistance}
				stdDeviation={currentStdDeviation}
				pointCount={pointCount}
				hasInvalidDepth={hasInvalidDepth}
				trackingEnabled={trackingEnabled}
				onToggleTracking={toggleTracking}
				onClear={clearSelection}
			/>
		</AppShell>
	);
}

export default App;
