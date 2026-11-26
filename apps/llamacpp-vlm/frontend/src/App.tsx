import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import {
	Alert,
	Badge,
	Button,
	Card,
	Flex,
	Input,
	Label,
	NormalText,
	Slider,
	SubHeader,
	SubLabel,
	Textarea,
} from '@luxonis/ui-components';
import { type PointerEvent, useEffect, useRef, useState } from 'react';
import { AppShell } from './AppShell.tsx';
import { callService } from './services';

type Region = { x: number; y: number; width: number; height: number };
type Snapshot = {
	snapshot_id: string;
	image: string;
	width: number;
	height: number;
};
type Job = {
	id: string;
	state: string;
	text: string;
	prompt: string;
	mode: string;
	max_tokens: number;
	temperature: number;
	error: string | null;
	ttft_ms: number | null;
	total_ms: number | null;
	finish_reason: string | null;
	input_image: string;
	input_width: number;
	input_height: number;
};
type State = {
	has_frame: boolean;
	image_size: number;
	default_max_tokens: number;
	default_temperature: number;
	job: Job | null;
	history: Job[];
	model: {
		ready: boolean;
		status: string;
		error: string | null;
		name: string;
		backend: string;
	};
};
const timeLabel = (milliseconds: number | null | undefined) =>
	milliseconds == null ? '—' : `${(milliseconds / 1000).toFixed(2)} s`;

export default function App() {
	const connection = useDaiConnection();
	const [state, setState] = useState<State | null>(null);
	const [prompt, setPrompt] = useState(
		'Describe what you see in one or two sentences.',
	);
	const [temperature, setTemperature] = useState<number | null>(null);
	const [maxTokens, setMaxTokens] = useState<string | null>(null);
	const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
	const [region, setRegion] = useState<Region | null>(null);
	const [error, setError] = useState('');
	const [sending, setSending] = useState(false);
	const [capturing, setCapturing] = useState(false);
	const dragStart = useRef<{ x: number; y: number } | null>(null);
	const busy =
		sending ||
		state?.job?.state === 'preparing' ||
		state?.job?.state === 'running';

	useEffect(() => {
		if (!connection.connected) {
			setState(null);
			return;
		}
		let disposed = false;
		let timer: number;
		const poll = async () => {
			try {
				const next = await callService<State>(
					connection.daiConnection,
					'Qwen State',
				);
				if (!disposed) setState(next);
			} catch (err) {
				if (!disposed)
					setError(err instanceof Error ? err.message : String(err));
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

	async function capture() {
		setCapturing(true);
		setError('');
		try {
			setSnapshot(
				await callService<Snapshot>(connection.daiConnection, 'Qwen Snapshot'),
			);
			setRegion(null);
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setCapturing(false);
		}
	}

	function point(event: PointerEvent<HTMLDivElement>) {
		const bounds = event.currentTarget.getBoundingClientRect();
		return {
			x: Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
			y: Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)),
		};
	}
	function drag(event: PointerEvent<HTMLDivElement>) {
		if (!dragStart.current) return;
		const end = point(event);
		const start = dragStart.current;
		setRegion({
			x: Math.min(start.x, end.x),
			y: Math.min(start.y, end.y),
			width: Math.abs(end.x - start.x),
			height: Math.abs(end.y - start.y),
		});
	}
	async function send() {
		setSending(true);
		setError('');
		try {
			await callService(connection.daiConnection, 'Qwen Submit', {
				prompt,
				max_tokens: tokenLimit,
				temperature: temperatureValue,
				...(snapshot ? { snapshot_id: snapshot.snapshot_id, region } : {}),
			});
			setState(
				await callService<State>(connection.daiConnection, 'Qwen State'),
			);
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setSending(false);
		}
	}
	const validRegion =
		region &&
		snapshot &&
		region.width * snapshot.width >= 16 &&
		region.height * snapshot.height >= 16;
	const temperatureValue = temperature ?? state?.default_temperature ?? 0;
	const tokenValue = maxTokens ?? String(state?.default_max_tokens ?? 128);
	const tokenLimit = Number(tokenValue);
	const validTokenLimit =
		Number.isInteger(tokenLimit) && tokenLimit >= 1 && tokenLimit <= 256;
	const job = state?.job;
	return (
		<AppShell
			title="llama.cpp VLM"
			status={<Badge intent="gray" variant="light" label="Qwen3.5-0.8B" />}
			streams={
				<div className="vlm-viewer">
					<div className="vlm-camera">
						<div className={`vlm-live ${snapshot ? 'vlm-live-hidden' : ''}`}>
							<Streams allowedTopics={['Video']} defaultTopics={['Video']} />
						</div>
						{snapshot && (
							<div className="vlm-snapshot">
								<div
									className="vlm-selection-surface"
									style={{
										aspectRatio: `${snapshot.width} / ${snapshot.height}`,
									}}
									onPointerDown={(event) => {
										if (busy) return;
										event.currentTarget.setPointerCapture(event.pointerId);
										dragStart.current = point(event);
										setRegion(null);
									}}
									onPointerMove={drag}
									onPointerUp={(event) => {
										drag(event);
										dragStart.current = null;
									}}
									onPointerCancel={() => {
										dragStart.current = null;
									}}
								>
									<img
										src={snapshot.image}
										alt="Captured camera frame. Drag to select the region to analyze."
										draggable={false}
									/>
									{region && (
										<div
											className="vlm-selection-box"
											style={{
												left: `${region.x * 100}%`,
												top: `${region.y * 100}%`,
												width: `${region.width * 100}%`,
												height: `${region.height * 100}%`,
											}}
										>
											<Badge
												intent="active"
												variant="filled"
												label="Selected region"
											/>
										</div>
									)}
								</div>
							</div>
						)}
					</div>
				</div>
			}
			below={
				<Card
					title="Recent prompts"
					subtitle="Last 3, newest first"
					variant="outline"
					intent="white"
				>
					{state?.history?.length ? (
						<ol className="vlm-history">
							{state.history.map((entry) => (
								<li key={entry.id} className="vlm-history-item">
									<img
										src={entry.input_image}
										alt={`Model input for: ${entry.prompt}`}
									/>
									<Flex direction="column" gap="xs" className="min-w-0 flex-1">
										<Flex direction="row" align="center" gap="xs" wrap="wrap">
											<Badge
												intent="gray"
												variant="light"
												label={
													entry.mode === 'region'
														? 'Selected region'
														: 'Full frame'
												}
											/>
											<SubLabel
												text={`${entry.input_width} by ${entry.input_height} px`}
											/>
										</Flex>
										<h4>
											<NormalText
												text={entry.prompt}
												weight="bold"
												spaces="preserve"
												break="word"
											/>
										</h4>
										{entry.text ? (
											<NormalText
												text={entry.text}
												spaces="preserve"
												break="word"
											/>
										) : (
											<Label
												text={
													entry.state === 'error'
														? 'No answer received.'
														: 'Waiting for the first token…'
												}
											/>
										)}
										{entry.error && (
											<Alert
												role="note"
												intent="error"
												variant="light"
												description={entry.error}
											/>
										)}
										{entry.finish_reason === 'length' && (
											<SubLabel
												text={`Reached the ${entry.max_tokens}-token limit.`}
											/>
										)}
									</Flex>
								</li>
							))}
						</ol>
					) : (
						<Label text="Your last three prompts and answers will appear here." />
					)}
				</Card>
			}
		>
			<Card
				title="Prompt"
				subtitle="Ask a question about the full frame or a selected region."
				variant="outline"
				intent="white"
			>
				<Flex direction="column" gap="sm">
					<fieldset className="flex flex-col gap-1">
						<legend>
							<Label text="Image input" />
						</legend>
						<div className="grid grid-cols-2 gap-2">
							<Button
								variant={snapshot ? 'outline' : 'filled'}
								intent={snapshot ? 'gray' : 'active'}
								aria-pressed={!snapshot}
								onClick={() => {
									setSnapshot(null);
									setRegion(null);
								}}
								disabled={busy}
							>
								Full frame
							</Button>
							<Button
								variant={snapshot ? 'filled' : 'outline'}
								intent={snapshot ? 'active' : 'gray'}
								aria-pressed={!!snapshot}
								onClick={capture}
								disabled={busy || capturing || !state?.has_frame}
							>
								{capturing
									? 'Capturing…'
									: snapshot
										? 'New snapshot'
										: 'Select region'}
							</Button>
						</div>
						<SubLabel
							text={
								snapshot
									? 'Frozen snapshot. Drag a box over the area to analyze.'
									: 'Live view. Analyze captures the latest full frame.'
							}
						/>
					</fieldset>
					<Flex direction="column" gap="xs">
						<label htmlFor="prompt">
							<Label text="Your prompt" />
						</label>
						<Textarea
							id="prompt"
							value={prompt}
							onChange={(event) => setPrompt(event.target.value)}
							rows={3}
							maxLength={2000}
							placeholder="What would you like to know about this image?"
							disabled={busy}
						/>
						<Flex direction="row" justify="between" gap="xs">
							<SubLabel text={snapshot ? 'Selected region' : 'Full frame'} />
							<SubLabel
								text={`Up to ${state?.image_size ?? 448} px longest edge`}
							/>
						</Flex>
					</Flex>
					<Flex direction="column" gap="xs">
						<div className="vlm-token-row">
							<label htmlFor="max-tokens">
								<Label text="Maximum output tokens" />
							</label>
							<Input
								id="max-tokens"
								type="number"
								min={1}
								max={256}
								step={1}
								value={tokenValue}
								onChange={(event) => setMaxTokens(event.target.value)}
								disabled={busy}
								aria-invalid={!validTokenLimit}
								aria-describedby="token-help"
							/>
						</div>
						<SubLabel
							id="token-help"
							text="1–256 tokens. The answer may finish sooner."
						/>
					</Flex>
					<Flex direction="column" gap="xs">
						<Label id="temperature-label" text="Temperature" />
						<Slider
							value={temperatureValue}
							onChange={setTemperature}
							min={0}
							max={1}
							step={0.05}
							disabled={busy}
							aria-labelledby="temperature-label"
							showLabels
							minLabelText="Focused"
							maxLabelText="Varied"
							valueText={temperatureValue.toFixed(2)}
						/>
					</Flex>
					<Button
						onClick={send}
						disabled={
							busy ||
							!connection.connected ||
							!state?.model.ready ||
							!state?.has_frame ||
							!prompt.trim() ||
							!validTokenLimit ||
							(!!snapshot && !validRegion)
						}
					>
						{busy ? 'Analyzing…' : 'Analyze image'}
					</Button>
					{(!state?.model.ready || state.model.error) && (
						<Alert
							role="status"
							intent={state?.model.error ? 'error' : 'active'}
							variant="light"
							description={
								state?.model.error ||
								state?.model.status ||
								'Connecting to the camera…'
							}
						/>
					)}
					{(error || job?.error) && (
						<Alert
							intent="error"
							variant="light"
							description={error || job?.error}
						/>
					)}
				</Flex>
			</Card>
			<Card
				title="Response"
				variant="outline"
				intent="white"
				actions={
					busy ? (
						<Badge
							intent="active"
							variant="light"
							label={job?.ttft_ms ? 'Generating' : 'Processing image'}
						/>
					) : undefined
				}
			>
				<Flex direction="column" gap="sm">
					<div className="vlm-answer" aria-live="polite">
						{job?.text ? (
							<NormalText text={job.text} spaces="preserve" break="word" />
						) : (
							<Label
								text={
									busy
										? 'Waiting for the first token…'
										: 'The answer will appear here as it is generated.'
								}
							/>
						)}
					</div>
					{job?.finish_reason === 'length' && (
						<Alert
							intent="warning"
							variant="light"
							description={`Output reached the ${job.max_tokens}-token limit. Increase the limit or try a more specific prompt.`}
						/>
					)}
				</Flex>
			</Card>
			<Card title="Latency" variant="outline" intent="white">
				<Flex direction="column" gap="sm">
					<dl className="grid grid-cols-2 gap-4">
						<div>
							<dt>
								<SubLabel text="First token" />
							</dt>
							<dd>
								<SubHeader text={timeLabel(job?.ttft_ms)} />
							</dd>
						</div>
						<div>
							<dt>
								<SubLabel text={busy ? 'Latest token' : 'Last token'} />
							</dt>
							<dd>
								<SubHeader text={timeLabel(job?.total_ms)} />
							</dd>
						</div>
					</dl>
					<SubLabel text="Model request to first and last answer tokens, including vision processing." />
				</Flex>
			</Card>
		</AppShell>
	);
}
