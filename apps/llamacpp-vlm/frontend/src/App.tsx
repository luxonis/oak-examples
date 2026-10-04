import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Badge, Button, Input, Slider, Textarea } from '@luxonis/ui-components';
import { type PointerEvent, useEffect, useRef, useState } from 'react';
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
		<main className="app-shell">
			<div className="workspace">
				<section className="camera-column">
					<div className="camera-panel">
						<div className={`live-stream ${snapshot ? 'stream-hidden' : ''}`}>
							<Streams allowedTopics={['Video']} defaultTopics={['Video']} />
						</div>
						{snapshot && (
							<div className="snapshot-wrap">
								<div
									className="selection-surface"
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
											className="selection-box"
											style={{
												left: `${region.x * 100}%`,
												top: `${region.y * 100}%`,
												width: `${region.width * 100}%`,
												height: `${region.height * 100}%`,
											}}
										>
											<span>Selected region</span>
										</div>
									)}
								</div>
							</div>
						)}
					</div>
					<section className="history-section" aria-labelledby="history-title">
						<div className="section-heading">
							<h2 id="history-title">Recent prompts</h2>
							<span>Last 3 · newest first</span>
						</div>
						{state?.history?.length ? (
							<ol className="history-list">
								{state.history.map((entry) => (
									<li key={entry.id} className="history-item">
										<img
											src={entry.input_image}
											alt={`Model input for: ${entry.prompt}`}
										/>
										<div className="history-content">
											<div className="history-meta">
												<Badge
													intent="gray"
													variant="light"
													label={
														entry.mode === 'region'
															? 'Selected region'
															: 'Full frame'
													}
												/>
												<span>
													{entry.input_width} × {entry.input_height} px
												</span>
											</div>
											<h3>{entry.prompt}</h3>
											<p
												className={
													entry.text ? 'history-answer' : 'history-pending'
												}
											>
												{entry.text ||
													(entry.state === 'error'
														? 'No answer received.'
														: 'Waiting for the first token…')}
											</p>
											{entry.error && <p className="error">{entry.error}</p>}
											{entry.finish_reason === 'length' && (
												<p className="status-note">
													Reached the {entry.max_tokens}-token limit.
												</p>
											)}
										</div>
									</li>
								))}
							</ol>
						) : (
							<p className="muted">
								Your last three prompts and answers will appear here.
							</p>
						)}
					</section>
				</section>
				<aside className="prompt-panel">
					<div>
						<div className="section-heading">
							<h1>llama.cpp VLM</h1>
							<Badge intent="gray" variant="light" label="Qwen3.5 · 0.8B" />
						</div>
						<p className="muted">
							Ask a question about the full frame or a selected region.
						</p>
					</div>
					<div className="camera-controls">
						<div className="mode-buttons">
							<Button
								variant={snapshot ? 'outline' : 'filled'}
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
						<p>
							{snapshot
								? 'Frozen snapshot · drag a box over the area to analyze.'
								: 'Live view · Analyze captures the latest full frame.'}
						</p>
					</div>
					<label htmlFor="prompt" className="control-label">
						Your prompt
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
					<div className="prompt-footer">
						<span>{snapshot ? 'Selected region' : 'Full frame'}</span>
						<span>Up to {state?.image_size ?? 448} px longest edge</span>
					</div>
					<div className="token-control">
						<label htmlFor="max-tokens" className="control-label">
							Maximum output tokens
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
						<p id="token-help" className="muted">
							1–256 tokens. The answer may finish sooner.
						</p>
					</div>
					<div className="temperature-control">
						<div className="temperature-label">
							<span id="temperature-label" className="control-label">
								Temperature
							</span>
							<span>{temperatureValue.toFixed(2)}</span>
						</div>
						<Slider
							value={temperatureValue}
							onChange={setTemperature}
							min={0}
							max={1}
							step={0.05}
							disabled={busy}
							aria-labelledby="temperature-label"
						/>
						<div className="temperature-scale">
							<span>0 · Focused</span>
							<span>1 · Varied</span>
						</div>
					</div>
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
						<output className="status-note">
							{state?.model.error ||
								state?.model.status ||
								'Connecting to the camera…'}
						</output>
					)}
					{(error || job?.error) && (
						<div className="error" role="alert">
							{error || job?.error}
						</div>
					)}
					<section className="answer-section">
						<div className="section-heading">
							<h2>Response</h2>
							{busy && (
								<Badge
									intent="active"
									variant="light"
									label={job?.ttft_ms ? 'Generating' : 'Processing image'}
								/>
							)}
						</div>
						<div
							className={`answer ${!job?.text ? 'empty-answer' : ''}`}
							aria-live="polite"
						>
							{job?.text ||
								(busy
									? 'Waiting for the first token…'
									: 'The answer will appear here as it is generated.')}
						</div>
						{job?.finish_reason === 'length' && (
							<p className="status-note">
								Output reached the {job.max_tokens}-token limit. Increase the
								limit or try a more specific prompt.
							</p>
						)}
					</section>
					<section className="latency-section" aria-labelledby="latency-title">
						<h2 id="latency-title">Latency</h2>{' '}
						<div className="timings">
							<div>
								<span>First token</span>
								<strong>{timeLabel(job?.ttft_ms)}</strong>
							</div>
							<div>
								<span>{busy ? 'Latest token' : 'Last token'}</span>
								<strong>{timeLabel(job?.total_ms)}</strong>
							</div>
						</div>
						<p className="timing-note">
							Model request to first and last answer tokens, including vision
							processing.
						</p>
					</section>
					<div
						className={`mt-auto flex items-center gap-2 border-t border-border pt-4 text-sm ${connection.connected ? 'text-success' : 'text-destructive'}`}
					>
						<div
							className={`h-3 w-3 rounded-full ${connection.connected ? 'bg-success' : 'bg-destructive'}`}
						/>
						<span>
							{connection.connected ? 'Connected to device' : 'Disconnected'}
						</span>
					</div>
				</aside>
			</div>
		</main>
	);
}
