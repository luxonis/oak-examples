import {
	AddIcon,
	Alert,
	Badge,
	Button,
	Card,
	DeleteIcon,
	Flex,
	Input,
	Label,
	NormalText,
	Separator,
	SubLabel,
} from '@luxonis/ui-components';
import type { Dispatch, SetStateAction } from 'react';
import { Steps } from './AppShell';
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
	classesDirty: boolean;
	questionsDirty: boolean;
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
	classesDirty,
	questionsDirty,
	validQuestions,
	error,
	applyDetection,
	applyDecision,
	updateQuestion,
}: SettingsPanelProps) {
	const running = state?.decision.enabled ?? false;

	return (
		<>
			{!state?.model.ready && (
				<Alert
					role="status"
					intent="active"
					variant="light"
					description={state?.model.status ?? 'Connecting to the model...'}
				/>
			)}
			{error && <Alert intent="error" variant="light" description={error} />}
			{state?.model.error && (
				<Alert intent="error" variant="light" description={state.model.error} />
			)}

			<Card title="How to use" variant="outline" intent="white">
				<Steps
					items={[
						'Enter the classes for YOLO-E to find, then apply them.',
						'Edit up to four questions, then apply them.',
						'Start decisions. The decision model answers your questions about each detection crop.',
					]}
				/>
			</Card>

			<Card title="Detection" variant="outline" intent="white">
				<Flex direction="column" gap="sm">
					<Flex direction="column" gap="xs">
						<label htmlFor="classes">
							<Label text="Classes to search for" />
						</label>
						<Input
							id="classes"
							value={classes}
							onChange={(event) => setClasses(event.target.value)}
							placeholder="person"
							aria-describedby="classes-help"
						/>
						<SubLabel
							id="classes-help"
							text="Comma-separated text prompts, up to 16 classes."
						/>
					</Flex>
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
					<SubLabel text="Confidence and IoU apply after you stop adjusting." />
					<Button
						disabled={
							!connected ||
							!classesDirty ||
							savingDetection ||
							state?.detection.updating
						}
						onClick={applyDetection}
					>
						{state?.detection.updating
							? 'Updating classes...'
							: 'Apply classes'}
					</Button>
					{classesDirty && (
						<Alert
							role="status"
							intent="warning"
							variant="light"
							description="Class edits are not applied yet."
						/>
					)}
					{state?.detection.error && (
						<Alert
							intent="error"
							variant="light"
							description={state.detection.error}
						/>
					)}
				</Flex>
			</Card>

			<Card
				title="Decision model"
				variant="outline"
				intent="white"
				actions={
					<Badge
						dot
						iconProps={{ color: 'inherit' }}
						intent={running ? 'success' : 'gray'}
						variant="light"
						label={running ? 'Running' : 'Paused'}
					/>
				}
			>
				<Flex direction="column" gap="sm">
					<Button
						variant={running ? 'outline' : 'filled'}
						intent={running ? 'gray' : 'active'}
						disabled={
							!connected ||
							savingDecision ||
							(!state?.model.ready && !state?.decision.enabled)
						}
						onClick={() =>
							void applyDecision(
								!state?.decision.enabled,
								state?.decision.questions ?? questions,
								refresh,
							)
						}
					>
						{running ? 'Pause decisions' : 'Start decisions'}
					</Button>
					<SettingsSlider
						id="refresh"
						label="Capture interval"
						min={0.5}
						max={30}
						step={0.5}
						unit=" s"
						value={refresh}
						onChange={setRefresh}
					/>
					<SubLabel text="YOLO-E keeps running. At each interval, the latest detections and their frame are captured for background decisions. Busy intervals replace older pending captures. The interval applies after you stop adjusting." />
					<Separator />
					<Flex direction="row" align="center" justify="between" gap="sm">
						<h4>
							<NormalText text="Questions" weight="medium" />
						</h4>
						<SubLabel text={`${questions.length} of 4`} />
					</Flex>
					<Button
						disabled={
							!connected || savingDecision || !validQuestions || !questionsDirty
						}
						onClick={() => void applyDecision()}
					>
						Apply questions
					</Button>
					{questions.map((question, index) => (
						<section
							className="vdm-question"
							key={question.id}
							aria-labelledby={`${question.id}-title`}
						>
							<Flex direction="row" align="center" justify="between" gap="sm">
								<h5 id={`${question.id}-title`}>
									<NormalText text={`Question ${index + 1}`} weight="medium" />
								</h5>
								<Button
									variant="ghost"
									intent="gray"
									size="sm"
									icon={DeleteIcon}
									aria-label={`Remove question ${index + 1}`}
									disabled={questions.length === 1}
									onClick={() =>
										setQuestions((current) =>
											current.filter((_, i) => i !== index),
										)
									}
								>
									Remove
								</Button>
							</Flex>
							<DecisionEditor
								idPrefix={question.id}
								value={question}
								disabled={savingDecision}
								onChange={(value) => updateQuestion(index, value)}
								onTypeChange={(kind: Kind) =>
									updateQuestion(index, structuredClone(defaults[kind]))
								}
							/>
						</section>
					))}
					<Button
						variant="outline"
						intent="gray"
						icon={AddIcon}
						disabled={questions.length >= 4}
						onClick={() =>
							setQuestions((current) => [
								...current,
								{
									...structuredClone(defaults.choice),
									id: crypto.randomUUID(),
								},
							])
						}
					>
						Add question
					</Button>
				</Flex>
			</Card>
		</>
	);
}
