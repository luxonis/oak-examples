import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button, Card, Flex } from '@luxonis/ui-components';
import {
	type MouseEvent,
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from 'react';
import { AnnotationModeSelector } from './AnnotationModeSelector.tsx';
import { AppShell, LoadingState, Steps } from './AppShell.tsx';
import { ConfidenceSlider } from './ConfidenceSlider.tsx';
import { useNotifications } from './Notifications.tsx';
import { OutlinesToggle } from './OutlinesToggle.tsx';
import { postToDinoTrackingService } from './services.ts';

type OnClickHandler = (
	event: MouseEvent,
	coords:
		| {
				offsetX: number;
				offsetY: number;
		  }
		| undefined,
) => void;

type AnnotationMode = 'heatmap' | 'bbox';

interface BackendConfig {
	confidence: number;
	annotation_mode: AnnotationMode;
	outlines: boolean;
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

function isBackendConfig(value: unknown): value is BackendConfig {
	return (
		typeof value === 'object' &&
		value !== null &&
		typeof (value as BackendConfig).confidence === 'number' &&
		((value as BackendConfig).annotation_mode === 'heatmap' ||
			(value as BackendConfig).annotation_mode === 'bbox') &&
		typeof (value as BackendConfig).outlines === 'boolean'
	);
}

function parseBackendConfig(response: unknown): BackendConfig | null {
	try {
		const payload = decodePayload(response);
		return isBackendConfig(payload) ? payload : null;
	} catch (error) {
		console.error('[App] Failed to parse service response:', error);
		return null;
	}
}

export default function App() {
	const connection = useDaiConnection();
	const { notify } = useNotifications();
	const previousConnectedRef = useRef<boolean | null>(null);

	const [threshold, setThreshold] = useState(0.35);
	const [annotationMode, setAnnotationMode] =
		useState<AnnotationMode>('heatmap');
	const [outlinesEnabled, setOutlinesEnabled] = useState(false);
	const [hasSelection, setHasSelection] = useState(false);
	const [configLoaded, setConfigLoaded] = useState(false);
	const [streamEverAvailable, setStreamEverAvailable] = useState(false);

	useEffect(() => {
		if (streamEverAvailable) return;

		if (
			Array.isArray(connection.topics) &&
			connection.topics.some((topic) => topic.name === 'Video')
		) {
			console.log('[App] Video stream appeared, latching Streams ON');
			setStreamEverAvailable(true);
		}
	}, [connection.topics, streamEverAvailable]);

	const handleStreamClick: OnClickHandler = useCallback(
		(_event, coords) => {
			if (!coords) {
				notify('Click was outside the video area.', { type: 'warning' });
				return;
			}

			if (!connection.connected) {
				notify('Not connected to device.', { type: 'error' });
				return;
			}

			postToDinoTrackingService(
				connection.daiConnection,
				'Click Prompt Service',
				{ x: coords.offsetX, y: coords.offsetY },
				() => {
					setHasSelection(true);
					notify('Object selected!', { type: 'success' });
				},
			);
		},
		[connection.connected, connection.daiConnection, notify],
	);

	const clickHandlers = useMemo(
		() => new Map<string, OnClickHandler>([['Video', handleStreamClick]]),
		[handleStreamClick],
	);

	const handleClearSelection = () => {
		if (!connection.connected) {
			notify('Not connected to device.', { type: 'error' });
			return;
		}

		postToDinoTrackingService(
			connection.daiConnection,
			'Clear Selection Service',
			{},
			() => {
				setHasSelection(false);
				notify('Selection cleared.', { type: 'success' });
			},
		);
	};

	useEffect(() => {
		if (!connection.connected || configLoaded) return;

		const timeoutId = window.setTimeout(() => {
			postToDinoTrackingService(
				connection.daiConnection,
				'BE State Service',
				{},
				(response) => {
					if (!response) {
						notify('BE State Service unavailable', {
							type: 'warning',
						});
						return;
					}

					const config = parseBackendConfig(response);

					if (!config) {
						notify('Failed to load configuration', {
							type: 'error',
						});
						return;
					}

					setConfigLoaded(true);
					setThreshold(config.confidence);
					setAnnotationMode(config.annotation_mode);
					setOutlinesEnabled(config.outlines);

					notify('Configuration restored from backend', {
						type: 'success',
					});
				},
			);
		}, 600);

		return () => window.clearTimeout(timeoutId);
	}, [connection.connected, connection.daiConnection, configLoaded, notify]);

	useEffect(() => {
		if (!connection.connected) {
			setConfigLoaded(false);
			setHasSelection(false);
		}
	}, [connection.connected]);

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

	return (
		<AppShell
			title="Dino Tracker"
			streams={
				streamEverAvailable ? (
					<Streams
						topicOnClickHandlersMap={clickHandlers}
						defaultTopics={['Video']}
					/>
				) : (
					<LoadingState
						title="Waiting for the video stream"
						subtitle="The app downloads its neural network models before the first frame."
					/>
				)
			}
		>
			<Card title="How to use" variant="outline" intent="white">
				<Steps
					items={[
						'Turn on outlines to see FastSAM segments.',
						'Click the object you want to track in the stream.',
						'Pick heatmap or bounding boxes. In bounding box mode, tune the confidence threshold.',
					]}
				/>
			</Card>

			<Card title="Tracking" variant="outline" intent="white">
				<Flex direction="column" gap="sm">
					<OutlinesToggle
						enabled={outlinesEnabled}
						setEnabled={setOutlinesEnabled}
					/>
					<AnnotationModeSelector
						currentMode={annotationMode}
						setCurrentMode={setAnnotationMode}
					/>
					{annotationMode === 'bbox' ? (
						<ConfidenceSlider value={threshold} setValue={setThreshold} />
					) : null}
					<Button
						variant="outline"
						intent="gray"
						onClick={handleClearSelection}
						disabled={!hasSelection}
					>
						Clear selection
					</Button>
				</Flex>
			</Card>
		</AppShell>
	);
}
