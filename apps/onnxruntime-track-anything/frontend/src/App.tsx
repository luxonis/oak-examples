import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import {
	Badge,
	Button,
	Switch,
	dismissToast,
	toast,
} from '@luxonis/ui-components';
import { type PointerEvent, useEffect, useRef, useState } from 'react';
import { callService } from './services';

type Point = { x: number; y: number; label: number };
type Snapshot = {
	snapshot_id: string;
	image: string;
	width: number;
	height: number;
	selection_remaining_s: number;
};
type Options = {
	mask: boolean;
	outline: boolean;
	box: boolean;
	trail: boolean;
};
type State = {
	ready: boolean;
	phase: string;
	status: string;
	runtime_error: string | null;
	has_frame: boolean;
	snapshot_id: string | null;
	preview: string | null;
	points: Point[];
	mask_ready: boolean;
	selection_busy: boolean;
	selection_ms: number | null;
	selection_remaining_s: number | null;
	options: Options;
	metrics: Record<string, number>;
};
const ms = (value?: number | null) =>
	value == null ? '—' : `${value.toFixed(1)} ms`;
const groups = {
	Video: 'tracking',
	Target: 'tracking',
	'Outline and trail': 'tracking',
	_Mask: 'diagnostics',
};

export default function App() {
	const connection = useDaiConnection();
	const [state, setState] = useState<State | null>(null);
	const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
	const [mode, setMode] = useState<'include' | 'exclude' | 'box'>('include');
	const [error, setError] = useState('');
	const [sending, setSending] = useState(false);
	const [rect, setRect] = useState<{
		x: number;
		y: number;
		w: number;
		h: number;
	} | null>(null);
	const start = useRef<Point | null>(null);
	const revision = useRef(0);
	const notifiedSnapshot = useRef<string | null>(null);
	const expiryToast = useRef<string | null>(null);
	const expired = Boolean(snapshot && state?.selection_remaining_s === 0);
	const atPromptLimit = mode !== 'box' && (state?.points.length ?? 0) >= 8;
	const busy = sending || Boolean(state?.selection_busy);
	const tracking = state?.phase === 'tracking' || state?.phase === 'lost';

	useEffect(() => {
		if (!connection.connected) {
			setState(null);
			setSnapshot(null);
			return;
		}
		let disposed = false;
		let timer: number;
		const poll = async () => {
			try {
				const requestedRevision = revision.current;
				const next = await callService<State>(
					connection.daiConnection,
					'Track State',
				);
				if (!disposed && requestedRevision === revision.current) {
					setState(next);
					setSnapshot((current) =>
						current && current.snapshot_id === next.snapshot_id
							? current
							: null,
					);
				}
			} catch (err) {
				if (!disposed) setError(String(err));
			} finally {
				if (!disposed) timer = window.setTimeout(poll, 250);
			}
		};
		void poll();
		return () => {
			disposed = true;
			window.clearTimeout(timer);
		};
	}, [connection.connected, connection.daiConnection]);

	useEffect(() => {
		if (!expired || !snapshot) {
			if (expiryToast.current) dismissToast(expiryToast.current);
			expiryToast.current = null;
			return;
		}
		start.current = null;
		setRect(null);
		if (notifiedSnapshot.current !== snapshot.snapshot_id) {
			notifiedSnapshot.current = snapshot.snapshot_id;
			expiryToast.current = toast({
				title: 'Capture an updated frame',
				description:
					'This snapshot expired. Capture a new frame and select the object again.',
				colorVariant: 'warning',
				duration: 6000,
			});
		}
	}, [expired, snapshot]);

	async function action<T>(
		body: Record<string, unknown>,
	): Promise<T | undefined> {
		revision.current += 1;
		setSending(true);
		setError('');
		try {
			return await callService<T>(
				connection.daiConnection,
				'Track Action',
				body,
			);
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			if (message.startsWith('Selection expired.')) {
				setState((current) =>
					current ? { ...current, selection_remaining_s: 0 } : current,
				);
			} else setError(message);
		} finally {
			revision.current += 1;
			setSending(false);
		}
	}
	async function capture() {
		const result = await action<Snapshot>({ action: 'snapshot' });
		if (result) {
			setSnapshot(result);
			setMode('include');
			setRect(null);
			setState((current) =>
				current
					? {
							...current,
							snapshot_id: result.snapshot_id,
							selection_remaining_s: result.selection_remaining_s,
							preview: null,
							points: [],
							mask_ready: false,
							selection_busy: true,
							phase: 'selecting',
						}
					: current,
			);
		}
	}
	async function submit(points: Point[]) {
		if (expired) return;
		if (!snapshot || points.length > 8) {
			setError('Use up to 8 points, or capture a fresh selection.');
			return;
		}
		const result = await action({
			action: 'points',
			snapshot_id: snapshot.snapshot_id,
			points,
		});
		if (result)
			setState((current) =>
				current ? { ...current, selection_busy: true } : current,
			);
	}
	function point(event: PointerEvent<HTMLDivElement>): Point {
		const r = event.currentTarget.getBoundingClientRect();
		return {
			x: Math.max(0, Math.min(1, (event.clientX - r.left) / r.width)),
			y: Math.max(0, Math.min(1, (event.clientY - r.top) / r.height)),
			label: mode === 'exclude' ? 0 : 1,
		};
	}
	function move(event: PointerEvent<HTMLDivElement>) {
		if (!start.current || mode !== 'box') return;
		const p = point(event);
		const s = start.current;
		setRect({
			x: Math.min(p.x, s.x),
			y: Math.min(p.y, s.y),
			w: Math.abs(p.x - s.x),
			h: Math.abs(p.y - s.y),
		});
	}
	async function finish(event: PointerEvent<HTMLDivElement>) {
		if (!start.current || expired || busy || atPromptLimit) {
			start.current = null;
			return;
		}
		const p = point(event);
		const s = start.current;
		start.current = null;
		setRect(null);
		if (mode === 'box') {
			if (Math.abs(p.x - s.x) < 0.01 || Math.abs(p.y - s.y) < 0.01) {
				setError('Draw a larger box around the object.');
				return;
			}
			await submit([
				{ x: Math.min(p.x, s.x), y: Math.min(p.y, s.y), label: 2 },
				{ x: Math.max(p.x, s.x), y: Math.max(p.y, s.y), label: 3 },
			]);
		} else await submit([...(state?.points ?? []), p]);
	}
	const status =
		!connection.connected || !state
			? 'Connecting'
			: state?.phase === 'loading'
				? 'Loading models'
				: state?.phase === 'catching_up'
					? 'Catching up'
					: state?.phase === 'tracking'
						? 'Tracking'
						: state?.phase === 'error'
							? 'Needs attention'
							: state?.phase === 'lost'
								? 'Target not visible'
								: snapshot
									? expired
										? 'Update frame'
										: 'Select target'
									: 'Ready';

	return (
		<main className="app-shell">
			<div className="workspace">
				<section className="camera-column">
					<div className="camera-panel">
						<div className={`live-stream ${snapshot ? 'stream-hidden' : ''}`}>
							<Streams
								defaultTopics={['Video']}
								allowedTopics={['Video']}
								topicGroups={groups}
							/>
						</div>
						{snapshot && (
							<div className="snapshot-wrap">
								<div
									className={`selection-surface ${expired || atPromptLimit ? 'selection-disabled' : ''}`}
									style={{
										aspectRatio: `${snapshot.width}/${snapshot.height}`,
										width: `min(100cqw, calc(100cqh * ${snapshot.width} / ${snapshot.height}))`,
									}}
									onPointerDown={(event) => {
										if (busy || expired || atPromptLimit) return;
										event.currentTarget.setPointerCapture(event.pointerId);
										start.current = point(event);
									}}
									onPointerMove={move}
									onPointerUp={(event) => void finish(event)}
									onPointerCancel={() => {
										start.current = null;
										setRect(null);
									}}
								>
									<img
										src={snapshot.image}
										alt="Captured frame. Click the object to select it."
										draggable={false}
									/>
									{state?.preview && (
										<img
											className="mask-preview"
											src={state.preview}
											alt="Selection mask"
											draggable={false}
										/>
									)}
									{state?.points.map((p, i) => (
										<span
											key={`${i}-${p.x}-${p.y}`}
											className={`prompt-point ${p.label === 0 ? 'negative' : ''}`}
											style={{ left: `${p.x * 100}%`, top: `${p.y * 100}%` }}
										>
											{p.label === 0 ? '−' : '+'}
										</span>
									))}
									{rect && (
										<div
											className="selection-box"
											style={{
												left: `${rect.x * 100}%`,
												top: `${rect.y * 100}%`,
												width: `${rect.w * 100}%`,
												height: `${rect.h * 100}%`,
											}}
										/>
									)}
								</div>
							</div>
						)}
					</div>
				</section>
				<aside className="controls">
					<header className="sidebar-header">
						<div className="title-row">
							<h1>Track Anything</h1>
							<Badge
								intent={tracking ? 'success' : 'gray'}
								variant="light"
								label={status}
							/>
						</div>
						<p className="muted">
							Select an object and follow its mask through the scene. Powered by
							ONNX Runtime on OAK4.
						</p>
					</header>
					<section>
						<h2>
							{snapshot
								? 'Define your selection'
								: tracking
									? 'Following your object'
									: 'Pick something to follow'}
						</h2>
						<p className="muted">
							Select a mug, tool, toy, or another object. Keep it in view as it
							moves.
						</p>
						<Button
							type="button"
							className="w-full"
							onClick={() => void capture()}
							disabled={busy || !state?.ready || !state.has_frame}
						>
							{snapshot
								? expired
									? 'Capture updated frame'
									: 'Capture a fresh frame'
								: tracking
									? 'Reselect object'
									: 'Select object'}
						</Button>
						{snapshot && (
							<>
								<div className="segmented" aria-label="Selection mode">
									{(['include', 'exclude', 'box'] as const).map((v) => (
										<Button
											type="button"
											key={v}
											variant={mode === v ? 'filled' : 'outline'}
											aria-pressed={mode === v}
											disabled={busy || expired}
											onClick={() => setMode(v)}
										>
											{v === 'include'
												? '+ Include'
												: v === 'exclude'
													? '− Exclude'
													: 'Box'}
										</Button>
									))}
								</div>
								<p className="muted">
									{mode === 'box'
										? 'Drag a box around the target. Drawing a new box replaces the previous prompts.'
										: 'Click to refine the mask. Start with an Include point.'}{' '}
									{state?.points.length ?? 0}/8 prompts used. A box uses 2
									slots.
									{atPromptLimit &&
										' Limit reached: undo a point or draw a replacement box.'}
								</p>
								<div className="button-row">
									<Button
										type="button"
										variant="outline"
										className="w-full"
										disabled={
											busy ||
											expired ||
											(state?.points.length ?? 0) < 2 ||
											(state?.points.length === 2 &&
												state.points[0].label === 2)
										}
										onClick={() =>
											void submit((state?.points ?? []).slice(0, -1))
										}
									>
										Undo point
									</Button>
									<Button
										type="button"
										className="w-full"
										disabled={busy || expired || !state?.mask_ready}
										onClick={async () => {
											if (
												await action({
													action: 'start',
													snapshot_id: snapshot.snapshot_id,
												})
											) {
												setSnapshot(null);
												setState((s) =>
													s
														? {
																...s,
																phase: 'catching_up',
																selection_busy: true,
															}
														: s,
												);
											}
										}}
									>
										Start tracking
									</Button>
								</div>
								<p className={expired ? 'selection-expired' : 'footnote'}>
									{expired
										? 'Snapshot expired. Capture an updated frame and select the object again.'
										: `Snapshot is valid for ${Math.ceil(state?.selection_remaining_s ?? 0)} more seconds. Start tracking before it expires so the tracker can catch up to the live scene.`}
								</p>
							</>
						)}
						{(snapshot ||
							tracking ||
							state?.phase === 'catching_up' ||
							(state?.phase === 'error' && state.ready)) && (
							<Button
								type="button"
								variant="outline"
								className="w-full mt-2"
								disabled={sending}
								onClick={async () => {
									if (await action({ action: 'clear' })) {
										setSnapshot(null);
										setState((s) =>
											s ? { ...s, phase: 'idle', selection_busy: false } : s,
										);
									}
								}}
							>
								Clear target
							</Button>
						)}
					</section>
					<section>
						<h2>Choose your overlays</h2>
						{(['mask', 'outline', 'box', 'trail'] as const).map((key) => (
							<div className="toggle-row" key={key}>
								<span id={`overlay-${key}`}>
									{
										{
											mask: 'Segmentation mask',
											outline: 'Object outline',
											box: 'Bounding box',
											trail: 'Movement trail',
										}[key]
									}
								</span>
								<Switch
									aria-labelledby={`overlay-${key}`}
									showActiveLabelOnly
									value={
										state?.options[key] ?? (key === 'mask' || key === 'outline')
									}
									disabled={!state || sending}
									onChange={async (enabled) => {
										if (
											await action({
												action: 'options',
												options: { [key]: enabled },
											})
										)
											setState((s) =>
												s
													? { ...s, options: { ...s.options, [key]: enabled } }
													: s,
											);
									}}
								/>
							</div>
						))}
					</section>
					<section className="performance">
						<h2>Performance</h2>
						<div className="metrics-bar">
							<div>
								<span>Tracking rate</span>
								<strong>
									{state?.metrics.fps ? state.metrics.fps.toFixed(1) : '—'}{' '}
									<small>updates/s</small>
								</strong>
							</div>
							<div>
								<span>Processing</span>
								<strong>{ms(state?.metrics.processing_ms)}</strong>
							</div>
							<div>
								<span>Frame → result¹</span>
								<strong>{ms(state?.metrics.frame_age_ms)}</strong>
							</div>
						</div>
						<p className="footnote">
							¹ From receipt of the camera frame to its tracking result. Browser
							transport and display latency are additional.
						</p>
						<details className="runtime-details">
							<summary>ONNX Runtime details</summary>
							<div className="stage-grid">
								{[
									['Frame encoding', 'encode_ms'],
									['Memory matching', 'memory_ms'],
									['Mask decoding', 'decode_ms'],
									['Memory update', 'update_ms'],
								].map(([label, key]) => (
									<div key={key}>
										<span>{label}</span>
										<strong>{ms(state?.metrics[key])}</strong>
									</div>
								))}
							</div>
							<p>
								MobileSAM selects the object. XMem propagates its mask using
								bounded visual memory. {state?.metrics.memory_frames ?? 0}/5
								memory frames.
							</p>
							<p>
								Model inference and memory matching run on the device's NPU
								through ONNX Runtime QNN.
							</p>
						</details>
					</section>
					{state?.phase === 'error' && !state.ready && (
						<Button
							type="button"
							variant="outline"
							className="w-full"
							disabled={sending}
							onClick={() => void action({ action: 'retry' })}
						>
							Retry loading models
						</Button>
					)}
					<output className="status-card" aria-live="polite">
						<span className={state?.ready ? 'status-dot' : 'spinner'} />
						<p>
							{expired
								? 'Capture an updated frame to continue.'
								: state?.status || 'Connecting to the camera…'}
						</p>
					</output>
					{(error || state?.runtime_error) && (
						<div className="error" role="alert">
							{error || state?.runtime_error}
						</div>
					)}
				</aside>
			</div>
		</main>
	);
}
