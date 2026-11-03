import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { useEffect, useRef, useState } from 'react';
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
	const [enabled, setEnabled] = useState(false);
	const [refresh, setRefresh] = useState(2);
	const [questions, setQuestions] = useState<Draft[]>([
		{ ...structuredClone(defaults.noul), id: crypto.randomUUID() },
	]);
	const [error, setError] = useState('');
	const [savingDetection, setSavingDetection] = useState(false);
	const [savingDecision, setSavingDecision] = useState(false);

	// Poll lightweight state on every tick; receive images only on history changes.
	useEffect(() => {
		historyRevision.current = -1;
		hydrated.current = false;
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
					if (next.history) setHistory(next.history);
					historyRevision.current = next.history_revision;
					if (!hydrated.current) {
						setClasses(next.detection.classes.join(', '));
						setConfidence(next.detection.confidence);
						setIou(next.detection.iou);
						setEnabled(next.decision.enabled);
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

	async function applyDecision(
		nextEnabled = enabled,
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
			setEnabled(nextEnabled);
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setSavingDecision(false);
		}
	}

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

	return (
		<main className="workspace">
			<section className="camera-column">
				<div className="camera-panel">
					<Streams
						allowedTopics={['Video', 'Annotations']}
						defaultTopics={['Video', 'Annotations']}
					/>
				</div>
				<section className="tracks-panel">
					<div className="section-heading">
						<h2>Visible objects</h2>
						<span>
							{state?.tracks.length ?? 0} tracked ·{' '}
							{state?.decision.actual_per_second ?? 0} decisions/s
						</span>
					</div>
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
				validQuestions={validQuestions}
				error={error}
				applyDetection={applyDetection}
				applyDecision={applyDecision}
				updateQuestion={updateQuestion}
			/>
		</main>
	);
}
