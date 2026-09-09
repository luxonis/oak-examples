import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button } from '@luxonis/ui-components';
import {
	type MouseEvent,
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from 'react';
import { AnnotationModeSelector } from './AnnotationModeSelector.tsx';
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
				() => notify('Object selected!', { type: 'success' }),
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
			() => notify('Selection cleared.', { type: 'success' }),
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
		<main className="flex h-screen w-screen flex-row gap-6 p-6">
			<div className="relative min-w-0 flex-1 overflow-hidden">
				{streamEverAvailable ? (
					<Streams
						topicOnClickHandlersMap={clickHandlers}
						defaultTopics={['Video']}
					/>
				) : (
					<div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
						Downloading neural network models and waiting for video stream...
					</div>
				)}
			</div>

			<div className="w-0.5 shrink-0 bg-border" />

			<aside className="flex max-h-full w-[380px] shrink-0 flex-col gap-5 overflow-y-auto pr-2 text-left">
				<h1 className="text-2xl font-bold">Dino Tracker</h1>

				<p className="text-sm leading-6 text-muted-foreground">
					1) Turn on outlines to see FastSAM segments. 2) Click on the stream to
					select what to track. 3) Choose how to visualize tracking (heatmap or
					bounding boxes) and, in BBox mode, tune the confidence slider.
				</p>

				<OutlinesToggle
					enabled={outlinesEnabled}
					setEnabled={setOutlinesEnabled}
				/>

				<div className="flex flex-col gap-3">
					<p className="text-sm text-muted-foreground">
						Click once on the object in the stream. Use{' '}
						<span className="font-semibold text-foreground">
							Clear selection
						</span>{' '}
						to reset and choose a new object.
					</p>

					<Button variant="outline" onClick={handleClearSelection}>
						Clear Selection
					</Button>
				</div>

				<AnnotationModeSelector
					currentMode={annotationMode}
					setCurrentMode={setAnnotationMode}
				/>

				{annotationMode === 'bbox' ? (
					<ConfidenceSlider value={threshold} setValue={setThreshold} />
				) : null}

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
