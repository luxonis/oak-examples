import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { useToast } from '@luxonis/ui-components';
import {
	type MouseEvent,
	type ReactNode,
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from 'react';
import { postToDataCollectionService } from './services.ts';
import { ClassSelector } from './utils/classes/ClassSelector.tsx';
import { ConfidenceSlider } from './utils/classes/ConfidenceSlider.tsx';
import { ImageUploader } from './utils/classes/ImageUploader.tsx';
import { SnapConditionsPanel } from './utils/conditions/SnapConditionsPanel.tsx';

interface BackendConfig {
	classes: string[];
	confidence_threshold: number;
	snapping: {
		running: boolean;
		timed: { enabled: boolean; cooldown: number };
		noDetections: { enabled: boolean; cooldown: number };
		lowConfidence: {
			enabled: boolean;
			threshold: number;
			cooldown: number;
		};
		lostMid: { enabled: boolean; cooldown: number; margin: number };
	};
}

type StreamMedia = {
	type: 'video' | 'canvas';
	width: number;
	height: number;
	displayWidth: number;
	displayHeight: number;
	offsetX: number;
	offsetY: number;
};

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
		Array.isArray((value as BackendConfig).classes) &&
		typeof (value as BackendConfig).confidence_threshold === 'number' &&
		typeof (value as BackendConfig).snapping === 'object'
	);
}

function parseBackendConfig(response: unknown): BackendConfig | null {
	try {
		let payload = decodePayload(response);

		if (
			typeof payload === 'object' &&
			payload !== null &&
			Object.hasOwn(payload, 'data')
		) {
			payload = (payload as { data: unknown }).data;
		}

		return isBackendConfig(payload) ? payload : null;
	} catch (error) {
		console.error('[App] Failed to parse service response:', error);
		return null;
	}
}

function SectionTitle({ children }: { children: ReactNode }) {
	return <h2 className="mt-2 mb-1 text-base font-semibold">{children}</h2>;
}

function App() {
	const connection = useDaiConnection();
	const streamContainerRef = useRef<HTMLDivElement>(null);
	const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
	const previousConnectedRef = useRef<boolean | null>(null);
	const [isDrawing, setIsDrawing] = useState(false);
	const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(
		null,
	);
	const [currentRect, setCurrentRect] = useState<{
		x: number;
		y: number;
		w: number;
		h: number;
	} | null>(null);
	const [backendConfig, setBackendConfig] = useState<BackendConfig | null>(
		null,
	);
	const [configLoaded, setConfigLoaded] = useState(false);
	const { toast } = useToast();
	const topicGroups = useMemo(() => ({ images: 'Video' }), []);
	const allowedTopics = useMemo(() => ['Video'], []);

	const getUnderlyingMediaAndSize = useCallback((): StreamMedia | null => {
		const container = streamContainerRef.current;
		if (!container) return null;

		const videoEl = container.querySelector('video') as HTMLVideoElement | null;
		const canvases = Array.from(
			container.querySelectorAll('canvas'),
		) as HTMLCanvasElement[];
		const canvasEl =
			canvases.find(
				(canvas) => canvas.getAttribute('data-role') !== 'overlay',
			) || null;
		const containerRect = container.getBoundingClientRect();

		if (videoEl?.videoWidth && videoEl.videoHeight) {
			const rect = videoEl.getBoundingClientRect();
			return {
				type: 'video',
				width: videoEl.videoWidth,
				height: videoEl.videoHeight,
				displayWidth: rect.width,
				displayHeight: rect.height,
				offsetX: rect.left - containerRect.left,
				offsetY: rect.top - containerRect.top,
			};
		}

		if (canvasEl?.width && canvasEl.height) {
			const rect = canvasEl.getBoundingClientRect();
			return {
				type: 'canvas',
				width: canvasEl.width,
				height: canvasEl.height,
				displayWidth: rect.width,
				displayHeight: rect.height,
				offsetX: rect.left - containerRect.left,
				offsetY: rect.top - containerRect.top,
			};
		}

		return null;
	}, []);

	const clearOverlay = useCallback(() => {
		const overlay = overlayCanvasRef.current;
		const ctx = overlay?.getContext('2d');
		if (overlay && ctx) {
			ctx.clearRect(0, 0, overlay.width, overlay.height);
		}
	}, []);

	const resetDrawing = useCallback(() => {
		setIsDrawing(false);
		setCurrentRect(null);
		setDragStart(null);
		clearOverlay();
	}, [clearOverlay]);

	const finalizeBBox = useCallback(() => {
		if (!currentRect) return;
		const overlay = overlayCanvasRef.current;
		if (!overlay) return;
		const { x, y, w, h } = currentRect;

		if (w <= 0 || h <= 0) {
			resetDrawing();
			toast({
				description: 'Selection too small. Please draw a larger box.',
				colorVariant: 'warning',
			});
			return;
		}

		const media = getUnderlyingMediaAndSize();
		if (!media) {
			toast({
				description: 'No video/canvas found. Reset the view and try again.',
				colorVariant: 'error',
				duration: 'long',
			});
			return;
		}

		const overlayW = overlay.width;
		const overlayH = overlay.height;
		const srcW = media.width;
		const srcH = media.height;
		const mediaOffsetX = media.offsetX;
		const mediaOffsetY = media.offsetY;
		const mediaDispW = media.displayWidth || overlayW;
		const mediaDispH = media.displayHeight || overlayH;

		let contentX = mediaOffsetX;
		let contentY = mediaOffsetY;
		let contentW = mediaDispW;
		let contentH = mediaDispH;

		if (media.type === 'canvas') {
			const side = Math.min(mediaDispW, mediaDispH);
			contentX = mediaOffsetX + (mediaDispW - side) / 2;
			contentY = mediaOffsetY + (mediaDispH - side) / 2;
			contentW = side;
			contentH = side;
		}

		const rx0 = Math.max(x, contentX);
		const ry0 = Math.max(y, contentY);
		const rx1 = Math.min(x + w, contentX + contentW);
		const ry1 = Math.min(y + h, contentY + contentH);
		const rw = Math.max(0, rx1 - rx0);
		const rh = Math.max(0, ry1 - ry0);

		if (rw <= 1 || rh <= 1) {
			toast({
				description:
					'Box outside of content area. Try again within the stream.',
				colorVariant: 'warning',
				duration: 'long',
			});
			return;
		}

		const scaleX = srcW / contentW;
		const scaleY = srcH / contentH;
		const sx0 = Math.max(
			0,
			Math.min(srcW - 1, Math.round((rx0 - contentX) * scaleX)),
		);
		const sy0 = Math.max(
			0,
			Math.min(srcH - 1, Math.round((ry0 - contentY) * scaleY)),
		);
		const sx1 = Math.max(
			0,
			Math.min(srcW, Math.round((rx1 - contentX) * scaleX)),
		);
		const sy1 = Math.max(
			0,
			Math.min(srcH, Math.round((ry1 - contentY) * scaleY)),
		);
		const sw = Math.max(1, sx1 - sx0);
		const sh = Math.max(1, sy1 - sy0);

		const xNorm = sx0 / srcW;
		const yNorm = sy0 / srcH;
		const wNorm = sw / srcW;
		const hNorm = sh / srcH;

		toast({
			description: `Sending box [${xNorm.toFixed(2)}, ${yNorm.toFixed(2)}, ${wNorm.toFixed(2)}, ${hNorm.toFixed(2)}]`,
			colorVariant: 'gray',
		});

		postToDataCollectionService(
			connection.daiConnection,
			'BBox Prompt Service',
			{
				x: xNorm,
				y: yNorm,
				width: wNorm,
				height: hNorm,
			},
			(resp) => {
				console.log('[BBox] Service ack:', resp);
				toast({
					description: 'Bounding box sent',
					colorVariant: 'success',
				});
			},
		);

		resetDrawing();
	}, [
		connection.daiConnection,
		currentRect,
		getUnderlyingMediaAndSize,
		resetDrawing,
		toast,
	]);

	const handleBeginBBoxDraw = useCallback(() => {
		setIsDrawing(true);
		setCurrentRect(null);
		setDragStart(null);
	}, []);

	useEffect(() => {
		if (!isDrawing) return;
		const container = streamContainerRef.current;
		const overlay = overlayCanvasRef.current;
		if (!container || !overlay) return;

		const sizeOverlay = () => {
			const rect = container.getBoundingClientRect();
			overlay.width = Math.max(1, Math.round(rect.width));
			overlay.height = Math.max(1, Math.round(rect.height));
			const ctx = overlay.getContext('2d');
			if (ctx) ctx.clearRect(0, 0, overlay.width, overlay.height);
		};

		sizeOverlay();
		window.addEventListener('resize', sizeOverlay);
		return () => window.removeEventListener('resize', sizeOverlay);
	}, [isDrawing]);

	useEffect(() => {
		const previousConnected = previousConnectedRef.current;
		previousConnectedRef.current = connection.connected;

		if (connection.connected && previousConnected !== true) {
			toast({
				description: 'Connected to device',
				colorVariant: 'success',
				duration: 1800,
			});
		}

		if (!connection.connected && previousConnected === true) {
			toast({
				description: 'Disconnected from device',
				colorVariant: 'warning',
				duration: 1800,
			});
		}
	}, [connection.connected, toast]);

	useEffect(() => {
		if (!connection.connected || configLoaded) return;

		const timeoutId = window.setTimeout(() => {
			console.log('[App] Fetching backend configuration...');
			postToDataCollectionService(
				connection.daiConnection,
				'Get App Config Service',
				{},
				(response) => {
					if (response === null || response === undefined) {
						console.log('[App] Config service not available - using defaults');
						return;
					}

					const config = parseBackendConfig(response);

					if (config) {
						setBackendConfig(config);
						setConfigLoaded(true);
						console.log('[App] Config restored from backend');
						toast({
							description: 'Configuration restored from backend',
							colorVariant: 'success',
						});
					} else {
						console.log('[App] Invalid config format - using defaults');
					}
				},
			);
		}, 1500);

		return () => window.clearTimeout(timeoutId);
	}, [connection.connected, connection.daiConnection, configLoaded, toast]);

	useEffect(() => {
		if (!connection.connected) {
			setConfigLoaded(false);
			setBackendConfig(null);
		}
	}, [connection.connected]);

	const onOverlayMouseDown = (event: MouseEvent<HTMLCanvasElement>) => {
		if (!isDrawing) return;
		const canvas = overlayCanvasRef.current;
		if (!canvas) return;
		const rect = canvas.getBoundingClientRect();
		const x = event.clientX - rect.left;
		const y = event.clientY - rect.top;
		setDragStart({ x, y });
		setCurrentRect({ x, y, w: 0, h: 0 });
	};

	const onOverlayMouseMove = (event: MouseEvent<HTMLCanvasElement>) => {
		if (!isDrawing || !dragStart) return;
		const canvas = overlayCanvasRef.current;
		if (!canvas) return;
		const rect = canvas.getBoundingClientRect();
		const x = event.clientX - rect.left;
		const y = event.clientY - rect.top;
		const x0 = Math.min(dragStart.x, x);
		const y0 = Math.min(dragStart.y, y);
		const w = Math.abs(x - dragStart.x);
		const h = Math.abs(y - dragStart.y);
		setCurrentRect({ x: x0, y: y0, w, h });

		const ctx = canvas.getContext('2d');
		if (!ctx) return;
		ctx.clearRect(0, 0, canvas.width, canvas.height);
		ctx.strokeStyle = '#22c55e';
		ctx.lineWidth = 2;
		ctx.strokeRect(x0, y0, w, h);
	};

	const onOverlayMouseUp = () => {
		if (!isDrawing) return;
		finalizeBBox();
	};

	return (
		<main className="flex h-screen w-screen flex-row gap-6 p-6">
			<div
				className="relative min-w-0 flex-1 overflow-hidden"
				ref={streamContainerRef}
			>
				<Streams
					allowedTopics={allowedTopics}
					defaultTopics={allowedTopics}
					topicGroups={topicGroups}
				/>
				{isDrawing ? (
					<canvas
						ref={overlayCanvasRef}
						data-role="overlay"
						className="absolute inset-0 z-10 cursor-crosshair"
						onMouseDown={onOverlayMouseDown}
						onMouseMove={onOverlayMouseMove}
						onMouseUp={onOverlayMouseUp}
					/>
				) : null}
			</div>

			<div className="w-0.5 shrink-0 bg-border" />

			<aside className="flex max-h-full w-[420px] min-w-[340px] max-w-[520px] shrink-0 flex-col gap-4 overflow-y-auto pr-2 text-left">
				<h1 className="text-2xl font-bold">Data Collection</h1>
				<p className="mb-2 text-sm leading-6 text-muted-foreground">
					Detect by name or example and auto-capture snaps based on conditions.
				</p>

				<SectionTitle>Labels by Text</SectionTitle>
				<p className="text-xs text-muted-foreground">
					Enter labels to find (e.g., person, chair, TV).
				</p>
				<ClassSelector initialClasses={backendConfig?.classes} />

				<SectionTitle>Labels by Image</SectionTitle>
				<p className="text-xs text-muted-foreground">
					Upload a photo or draw a box on the stream.
				</p>
				<ImageUploader onDrawBBox={handleBeginBBoxDraw} />

				<SectionTitle>Confidence Filter</SectionTitle>
				<p className="text-xs text-muted-foreground">
					Detections below this confidence are dropped.
				</p>
				<ConfidenceSlider
					initialValue={backendConfig?.confidence_threshold ?? 0.4}
				/>

				<section className="flex flex-col gap-3 rounded-md border border-border bg-background p-4 shadow-sm">
					<h2 className="text-lg font-semibold">Snap conditions</h2>
					<p className="text-xs leading-5 text-muted-foreground">
						Choose when to auto-capture a snap.
					</p>
					<SnapConditionsPanel initialConfig={backendConfig?.snapping} />
				</section>

				<div
					className={`sticky bottom-0 mt-2 flex items-center gap-2 border-t border-border bg-background py-3 text-xs ${
						connection.connected ? 'text-success' : 'text-destructive'
					}`}
				>
					<div
						className={`h-2 w-2 shrink-0 rounded-full ${
							connection.connected ? 'bg-success' : 'bg-destructive'
						}`}
					/>
					<span className="whitespace-nowrap">
						{connection.connected ? 'Connected to device' : 'Disconnected'}
					</span>
				</div>
			</aside>
		</main>
	);
}

export default App;
