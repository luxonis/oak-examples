import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
	AddIcon,
	Alert,
	Badge,
	Button,
	Card,
	Flex,
	Label,
	NormalText,
	SubLabel,
	Switch,
	dismissToast,
	toast,
} from '@luxonis/ui-components';
import { type PointerEvent, useEffect, useRef, useState } from 'react';
import { AppShell } from './AppShell.tsx';
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
const overlayLabels = {
	mask: 'Segmentation mask',
	outline: 'Object outline',
	box: 'Bounding box',
	trail: 'Movement trail',
};
const stages = [
	['Frame encoding', 'encode_ms'],
	['Memory matching', 'memory_ms'],
	['Mask decoding', 'decode_ms'],
	['Memory update', 'update_ms'],
];
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
				? 'Preparing models for QNN'
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

	const preparing =
		!state ||
		(!state.ready && state.phase !== 'error') ||
		state.status.startsWith('Preparing ');
	const promptCount = state?.points.length ?? 0;

	return (
		<AppShell
			title="Track Anything"
			status={
				<Badge
					intent={tracking ? 'success' : 'gray'}
					variant="light"
					label={status}
				/>
			}
			streams={
				<div className="track-camera">
					<div className={`track-live ${snapshot ? 'track-live-hidden' : ''}`}>
						<Streams
							defaultTopics={['Video']}
							allowedTopics={['Video']}
							topicGroups={groups}
						/>
					</div>
					{snapshot && (
						<div className="track-snapshot">
							<div
								className={`track-surface ${expired || atPromptLimit ? 'track-surface-disabled' : ''}`}
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
										className="track-mask"
										src={state.preview}
										alt="Selection mask"
										draggable={false}
									/>
								)}
								{state?.points.map((p, i) => (
									<span
										key={`${i}-${p.x}-${p.y}`}
										className={`track-point ${p.label === 0 ? 'track-point-exclude' : ''}`}
										style={{ left: `${p.x * 100}%`, top: `${p.y * 100}%` }}
									>
										{p.label === 0 ? null : <AddIcon aria-hidden />}
									</span>
								))}
								{rect && (
									<div
										className="track-box"
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
			}
		>
			{preparing && (
				<Alert
					role="status"
					intent="active"
					variant="light"
					title={state ? state.status : 'Connecting to the camera'}
					description={
						state
							? undefined
							: 'Initial QNN preparation may take a few minutes.'
					}
				/>
			)}
			<Card
				title={
					snapshot
						? 'Define your selection'
						: tracking
							? 'Following your object'
							: 'Pick something to follow'
				}
				variant="outline"
				intent="white"
			>
				<Flex direction="column" gap="sm">
					<output aria-live="polite">
						{!preparing && (
							<NormalText
								text={
									expired
										? 'Capture an updated frame to continue.'
										: state.status
								}
							/>
						)}
					</output>
					{(error || state?.runtime_error) && (
						<Alert
							intent="error"
							variant="light"
							description={error || state?.runtime_error}
						/>
					)}
					{state?.phase === 'error' && !state.ready && (
						<Button
							type="button"
							variant="outline"
							intent="gray"
							disabled={sending}
							onClick={() => void action({ action: 'retry' })}
						>
							Retry loading models
						</Button>
					)}
					<Label text="Select a mug, tool, toy, or another object and follow its mask through the scene. Keep it in view as it moves." />
					<Button
						type="button"
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
							<fieldset className="flex flex-col gap-1">
								<legend>
									<Label text="Selection mode" />
								</legend>
								<div className="grid grid-cols-3 gap-2">
									{(['include', 'exclude', 'box'] as const).map((v) => (
										<Button
											type="button"
											key={v}
											variant={mode === v ? 'filled' : 'outline'}
											intent={mode === v ? 'active' : 'gray'}
											aria-pressed={mode === v}
											disabled={busy || expired}
											onClick={() => setMode(v)}
										>
											{v === 'include'
												? 'Include'
												: v === 'exclude'
													? 'Exclude'
													: 'Box'}
										</Button>
									))}
								</div>
							</fieldset>
							<Label
								text={
									mode === 'box'
										? 'Drag a box around the target. Drawing a new box replaces the previous prompts.'
										: 'Click to refine the mask. Start with an Include point.'
								}
							/>
							<SubLabel
								text={`${promptCount} of 8 prompts used. A box uses 2 slots.${
									atPromptLimit
										? ' Limit reached: undo a point or draw a replacement box.'
										: ''
								}`}
							/>
							<div className="grid grid-cols-2 gap-2">
								<Button
									type="button"
									variant="outline"
									intent="gray"
									disabled={
										busy ||
										expired ||
										promptCount < 2 ||
										(state?.points.length === 2 && state.points[0].label === 2)
									}
									onClick={() =>
										void submit((state?.points ?? []).slice(0, -1))
									}
								>
									Undo point
								</Button>
								<Button
									type="button"
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
							{expired ? (
								<Alert
									role="status"
									intent="warning"
									variant="light"
									description="Snapshot expired. Capture an updated frame and select the object again."
								/>
							) : (
								<SubLabel
									text={`Snapshot is valid for ${Math.ceil(state?.selection_remaining_s ?? 0)} more seconds. Start tracking before it expires so the tracker can catch up to the live scene.`}
								/>
							)}
						</>
					)}
					{(snapshot ||
						tracking ||
						state?.phase === 'catching_up' ||
						(state?.phase === 'error' && state.ready)) && (
						<Button
							type="button"
							variant="outline"
							intent="gray"
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
				</Flex>
			</Card>
			<Card title="Overlays" variant="outline" intent="white">
				<Flex direction="column" gap="sm">
					{(['mask', 'outline', 'box', 'trail'] as const).map((key) => (
						<Flex
							key={key}
							direction="row"
							align="center"
							justify="between"
							gap="sm"
						>
							<Label id={`overlay-${key}`} text={overlayLabels[key]} />
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
						</Flex>
					))}
				</Flex>
			</Card>
			<Card title="Performance" variant="outline" intent="white">
				<Flex direction="column" gap="sm">
					<dl className="track-metrics">
						<Metric
							label="Tracking rate"
							value={state?.metrics.fps || null}
							unit="updates/s"
						/>
						<Metric
							label="Processing"
							value={state?.metrics.processing_ms}
							unit="ms"
						/>
						<Metric
							label="Frame to result"
							value={state?.metrics.frame_age_ms}
							unit="ms"
						/>
					</dl>
					<SubLabel text="Frame to result runs from receipt of the camera frame to its tracking result. Browser transport and display latency are additional." />
					<Accordion type="single" collapsible>
						<AccordionItem value="runtime">
							<AccordionTrigger>
								<Label text="ONNX Runtime details" />
							</AccordionTrigger>
							<AccordionContent>
								<Flex direction="column" gap="sm">
									<dl className="track-metrics track-stages">
										{stages.map(([label, key]) => (
											<Metric
												key={key}
												label={label}
												value={state?.metrics[key]}
												unit="ms"
											/>
										))}
									</dl>
									<SubLabel
										text={`MobileSAM selects the object. XMem propagates its mask using bounded visual memory. ${state?.metrics.memory_frames ?? 0} of 5 memory frames.`}
									/>
									<SubLabel text="Model inference and memory matching run on the device's NPU through ONNX Runtime QNN." />
								</Flex>
							</AccordionContent>
						</AccordionItem>
					</Accordion>
				</Flex>
			</Card>
		</AppShell>
	);
}

type MetricProps = {
	label: string;
	value?: number | null;
	unit: string;
};

function Metric({ label, value, unit }: MetricProps) {
	return (
		<div>
			<dt>
				<SubLabel text={label} />
			</dt>
			<dd>
				{value == null ? (
					<NormalText text="No data" />
				) : (
					<>
						<NormalText
							weight="bold"
							className="tabular-nums"
							text={value.toFixed(1)}
						/>{' '}
						<SubLabel text={unit} />
					</>
				)}
			</dd>
		</div>
	);
}
