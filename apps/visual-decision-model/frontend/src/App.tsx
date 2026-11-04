import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { memo, useEffect, useRef, useState } from 'react';
import {
	type Decision,
	type DecisionResult,
	defaults,
	validDecision,
} from './Decision';
import { DecisionLog } from './DecisionLog';
import { SettingsPanel } from './SettingsPanel';
import { callService } from './services';
import type { Draft, Job, State } from './types';

const STREAM_TOPICS = ['Video', 'Annotations'];

/** Compare only the question fields retained by backend validation. */
function comparableQuestions(items: Decision[]) {
	return JSON.stringify(
		items.map((question) => ({
			type: question.type,
			instructions: question.instructions.trim(),
			options: question.options.map((option) => ({
				label: option.label.trim(),
				description: option.description.trim(),
			})),
		})),
	);
}

/** Keep live video subscribed while controls and history change. */
const LiveStream = memo(function LiveStream() {
	return (
		<Streams allowedTopics={STREAM_TOPICS} defaultTopics={STREAM_TOPICS} />
	);
});

/** Summarize the first question for the live object list. */
function shortAnswer(result: DecisionResult | null) {
	if (!result) return 'Waiting for first decision';
	if (result.type === 'noul')
		return `${result.probabilities[0].label}: ${((result.yes_probability ?? 0) * 100).toFixed(0)}%`;
	if (result.type === 'choice') return result.choice ?? 'Unknown';
	return `Score ${result.score?.toFixed(1) ?? '—'}`;
}

export default function App() {
	const connection = useDaiConnection();

	const [state, setState] = useState<State | null>(null);
	const [history, setHistory] = useState<Job[]>([]);
	const historyRevision = useRef(-1);
	const hydrated = useRef(false);

	// Keep editable controls separate from the last confirmed backend state.
	const [classes, setClasses] = useState('person');
	const [confidence, setConfidence] = useState(0.35);
	const [iou, setIou] = useState(0.5);
	const [refresh, setRefresh] = useState(2);
	const [questions, setQuestions] = useState<Draft[]>([
		{ ...structuredClone(defaults.noul), id: crypto.randomUUID() },
	]);
	const [error, setError] = useState('');
	const [savingDetection, setSavingDetection] = useState(false);
	const [savingDecision, setSavingDecision] = useState(false);
	const lastAutoThresholds = useRef('');
	const lastAutoInterval = useRef('');

	// Poll lightweight state on every tick; receive images only on history changes.
	useEffect(() => {
		historyRevision.current = -1;
		hydrated.current = false;
		lastAutoThresholds.current = '';
		lastAutoInterval.current = '';
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
					'Decision State',
					{ history_revision: historyRevision.current },
				);
				if (!disposed) {
					setState(next);
					if (next.history) {
						setHistory((current) =>
							next.history_reset
								? (next.history ?? [])
								: [...(next.history ?? []), ...current].slice(0, 20),
						);
					}
					historyRevision.current = next.history_revision;
					if (!hydrated.current) {
						setClasses(next.detection.classes.join(', '));
						setConfidence(next.detection.confidence);
						setIou(next.detection.iou);
						setRefresh(next.decision.refresh);
						setQuestions(
							next.decision.questions.map((question) => ({
								...question,
								id: crypto.randomUUID(),
							})),
						);
						hydrated.current = true;
					}
				}
			} catch (err) {
				if (!disposed)
					setError(err instanceof Error ? err.message : String(err));
			} finally {
				if (!disposed) timer = window.setTimeout(poll, 500);
			}
		};
		void poll();
		return () => {
			disposed = true;
			window.clearTimeout(timer);
		};
	}, [connection.connected, connection.daiConnection]);

	/** Submit class edits explicitly; thresholds are also sent with this request. */
	async function applyDetection() {
		setError('');
		setSavingDetection(true);
		try {
			await callService(connection.daiConnection, 'Detection Config', {
				classes: classes
					.split(',')
					.map((name) => name.trim())
					.filter(Boolean),
				confidence,
				iou,
			});
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setSavingDetection(false);
		}
	}

	// Slider edits settle before reaching the device; unsaved class text is excluded.
	const appliedClasses = state?.detection.classes.join('\u0000') ?? '';
	const appliedConfidence = state?.detection.confidence;
	const appliedIou = state?.detection.iou;
	const detectionUpdating = state?.detection.updating;
	useEffect(() => {
		if (
			!hydrated.current ||
			!connection.connected ||
			!appliedClasses ||
			savingDetection ||
			detectionUpdating ||
			(confidence === appliedConfidence && iou === appliedIou)
		)
			return;
		const key = `${appliedClasses}:${confidence}:${iou}`;
		if (lastAutoThresholds.current === key) return;
		const timer = window.setTimeout(async () => {
			lastAutoThresholds.current = key;
			setSavingDetection(true);
			try {
				await callService(connection.daiConnection, 'Detection Config', {
					classes: appliedClasses.split('\u0000'),
					confidence,
					iou,
				});
			} catch (err) {
				lastAutoThresholds.current = '';
				setError(err instanceof Error ? err.message : String(err));
			} finally {
				setSavingDetection(false);
			}
		}, 450);
		return () => window.clearTimeout(timer);
	}, [
		appliedClasses,
		appliedConfidence,
		appliedIou,
		confidence,
		connection.connected,
		connection.daiConnection,
		detectionUpdating,
		iou,
		savingDetection,
	]);

	async function applyDecision(
		nextEnabled = state?.decision.enabled ?? false,
		submittedQuestions: Decision[] = questions,
		submittedRefresh = refresh,
	) {
		setError('');
		setSavingDecision(true);
		try {
			await callService(connection.daiConnection, 'Decision Config', {
				enabled: nextEnabled,
				refresh: submittedRefresh,
				questions: submittedQuestions,
			});
		} catch (err) {
			lastAutoInterval.current = '';
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setSavingDecision(false);
		}
	}

	// Keep the editable questions untouched when the interval changes.
	const appliedEnabled = state?.decision.enabled;
	const appliedRefresh = state?.decision.refresh;
	const appliedQuestions = JSON.stringify(state?.decision.questions ?? []);
	useEffect(() => {
		if (
			!hydrated.current ||
			!connection.connected ||
			appliedEnabled === undefined ||
			appliedRefresh === undefined ||
			savingDecision ||
			refresh === appliedRefresh
		)
			return;
		const key = `${appliedEnabled}:${refresh}:${appliedQuestions}`;
		if (lastAutoInterval.current === key) return;
		const timer = window.setTimeout(async () => {
			lastAutoInterval.current = key;
			setSavingDecision(true);
			try {
				await callService(connection.daiConnection, 'Decision Config', {
					enabled: appliedEnabled,
					questions: JSON.parse(appliedQuestions) as Decision[],
					refresh,
				});
			} catch (err) {
				lastAutoInterval.current = '';
				setError(err instanceof Error ? err.message : String(err));
			} finally {
				setSavingDecision(false);
			}
		}, 450);
		return () => window.clearTimeout(timer);
	}, [
		appliedEnabled,
		appliedQuestions,
		appliedRefresh,
		connection.connected,
		connection.daiConnection,
		refresh,
		savingDecision,
	]);

	function updateQuestion(index: number, value: Decision) {
		setQuestions((current) =>
			current.map((item, i) =>
				i === index ? { ...value, id: item.id } : item,
			),
		);
	}

	const validQuestions =
		questions.length >= 1 &&
		questions.length <= 4 &&
		questions.every(validDecision);
	const classesDirty =
		classes
			.split(',')
			.map((name) => name.trim())
			.filter(Boolean)
			.join('\u0000') !== appliedClasses;
	const questionsDirty =
		comparableQuestions(questions) !==
		comparableQuestions(state?.decision.questions ?? []);

	return (
		<main className="workspace">
			<section className="camera-column">
				<div className="camera-panel">
					<LiveStream />
				</div>
				<section className="tracks-panel">
					<div className="section-heading">
						<h2>Visible objects</h2>
						<span>
							{state?.tracks.length ?? 0} tracked ·{' '}
							{state?.decision.actual_per_second ?? 0} decisions/s
						</span>
					</div>
					<div className="tracks-list">
						{state?.tracks.length ? (
							state.tracks.map((track) => (
								<div className="track-row" key={track.id}>
									<strong>
										{track.class_name} #{track.id}
									</strong>
									<span>YOLO-E {(track.confidence * 100).toFixed(0)}%</span>
									<span>
										{shortAnswer(track.last_result)}
										{track.decision_age != null
											? ` · ${track.decision_age.toFixed(1)}s old`
											: ''}
									</span>
								</div>
							))
						) : (
							<div className="empty">Waiting for YOLO-E detections.</div>
						)}
					</div>
				</section>
				<DecisionLog history={history} />
			</section>
			<SettingsPanel
				state={state}
				connected={connection.connected}
				classes={classes}
				setClasses={setClasses}
				confidence={confidence}
				setConfidence={setConfidence}
				iou={iou}
				setIou={setIou}
				refresh={refresh}
				setRefresh={setRefresh}
				questions={questions}
				setQuestions={setQuestions}
				savingDetection={savingDetection}
				savingDecision={savingDecision}
				classesDirty={classesDirty}
				questionsDirty={questionsDirty}
				validQuestions={validQuestions}
				error={error}
				applyDetection={applyDetection}
				applyDecision={applyDecision}
				updateQuestion={updateQuestion}
			/>
		</main>
	);
}
