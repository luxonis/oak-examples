import { Badge, Button, Input, Separator } from '@luxonis/ui-components';
import type { Dispatch, SetStateAction } from 'react';
import { type Decision, DecisionEditor, type Kind, defaults } from './Decision';
import { SettingsSlider } from './SettingsSlider';
import type { Draft, State } from './types';

type SettingsPanelProps = {
	state: State | null;
	connected: boolean;
	classes: string;
	setClasses: (value: string) => void;
	confidence: number;
	setConfidence: (value: number) => void;
	iou: number;
	setIou: (value: number) => void;
	refresh: number;
	setRefresh: (value: number) => void;
	questions: Draft[];
	setQuestions: Dispatch<SetStateAction<Draft[]>>;
	savingDetection: boolean;
	savingDecision: boolean;
	validQuestions: boolean;
	error: string;
	applyDetection: () => Promise<void>;
	applyDecision: (
		enabled?: boolean,
		questions?: Decision[],
		refresh?: number,
	) => Promise<void>;
	updateQuestion: (index: number, value: Decision) => void;
};

/** Keep detection and decision controls together in the app sidebar. */
export function SettingsPanel({
	state,
	connected,
	classes,
	setClasses,
	confidence,
	setConfidence,
	iou,
	setIou,
	refresh,
	setRefresh,
	questions,
	setQuestions,
	savingDetection,
	savingDecision,
	validQuestions,
	error,
	applyDetection,
	applyDecision,
	updateQuestion,
}: SettingsPanelProps) {
	return (
		<aside className="prompt-panel">
			<div className="panel-intro">
				<div className="section-heading">
					<h1>Visual Decisions</h1>
					<Badge intent="gray" variant="light" label="d3-lite" />
				</div>
				<p className="muted">
					YOLO-E finds the objects you choose. Ask the decision model questions
					about each detection crop.
				</p>
				{!state?.model.ready && (
					<p className="status-note">
						{state?.model.status ?? 'Connecting to the model…'}
					</p>
				)}
			</div>
			<Separator />
			<h2>Detection</h2>
			<label htmlFor="classes">Classes to search for</label>
			<Input
				id="classes"
				value={classes}
				onChange={(event) => setClasses(event.target.value)}
				placeholder="person"
			/>
			<p className="muted">Comma-separated text prompts · up to 16 classes.</p>
			<SettingsSlider
				id="confidence"
				label="Confidence"
				min={0}
				max={1}
				step={0.01}
				value={confidence}
				onChange={setConfidence}
			/>
			<SettingsSlider
				id="iou"
				label="IoU"
				min={0}
				max={1}
				step={0.01}
				value={iou}
				onChange={setIou}
			/>
			<Button
				disabled={!connected || savingDetection || state?.detection.updating}
				onClick={applyDetection}
			>
				{state?.detection.updating
					? 'Updating classes…'
					: 'Apply detection settings'}
			</Button>
			{state?.detection.error && (
				<p className="error">{state.detection.error}</p>
			)}
			<Separator />
			<div className="section-heading">
				<h2>Decision model</h2>
				<Badge
					intent="gray"
					variant="light"
					label={state?.decision.enabled ? 'Running' : 'Paused'}
				/>
			</div>
			<Button
				variant="outline"
				disabled={
					!connected ||
					savingDecision ||
					(!state?.model.ready && !state?.decision.enabled)
				}
				onClick={() =>
					void applyDecision(
						!state?.decision.enabled,
						state?.decision.questions ?? questions,
						state?.decision.refresh ?? refresh,
					)
				}
			>
				{state?.decision.enabled ? 'Pause decisions' : 'Start decisions'}
			</Button>
			<SettingsSlider
				id="refresh"
				label="Target refresh per object"
				min={0.5}
				max={30}
				step={0.5}
				unit=" s"
				value={refresh}
				onChange={setRefresh}
			/>
			<p className="muted">
				Best effort. If visible objects exceed model capacity, actual refresh
				takes longer. No old crops are queued.
			</p>
			<div className="section-heading">
				<h2>Questions</h2>
				<span>{questions.length} / 4</span>
			</div>
			{questions.map((question, index) => (
				<div className="question-card" key={question.id}>
					<div className="section-heading">
						<strong>Question {index + 1}</strong>
						<Button
							variant="outline"
							disabled={questions.length === 1}
							onClick={() =>
								setQuestions((current) => current.filter((_, i) => i !== index))
							}
						>
							Remove
						</Button>
					</div>
					<DecisionEditor
						idPrefix={question.id}
						value={question}
						disabled={savingDecision}
						onChange={(value) => updateQuestion(index, value)}
						onTypeChange={(kind: Kind) =>
							updateQuestion(index, structuredClone(defaults[kind]))
						}
					/>
				</div>
			))}
			<Button
				variant="outline"
				disabled={questions.length >= 4}
				onClick={() =>
					setQuestions((current) => [
						...current,
						{ ...structuredClone(defaults.choice), id: crypto.randomUUID() },
					])
				}
			>
				Add question
			</Button>
			<Button
				disabled={!connected || savingDecision || !validQuestions}
				onClick={() => void applyDecision()}
			>
				Apply decision settings
			</Button>
			{error && (
				<p className="error" role="alert">
					{error}
				</p>
			)}
			{state?.model.error && <p className="error">{state.model.error}</p>}
			<div className="connection">
				<span className={connected ? 'dot connected' : 'dot'} />
				{connected ? 'Connected to device' : 'Disconnected'}
			</div>
		</aside>
	);
}
