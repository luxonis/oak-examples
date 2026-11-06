import {
	AddIcon,
	Alert,
	ArrowUpIcon,
	Button,
	DeleteIcon,
	Flex,
	Input,
	Label,
	NormalText,
	Progress,
	Select,
	SubLabel,
	Textarea,
} from '@luxonis/ui-components';

export type Kind = 'noul' | 'choice' | 'score';
export type Option = { label: string; description: string };
export type Decision = { type: Kind; instructions: string; options: Option[] };
export type DecisionResult = {
	type: Kind;
	yes_probability?: number;
	choice?: string;
	score?: number;
	probabilities: (Option & { probability: number })[];
};
export const typeNames: Record<Kind, string> = {
	noul: 'Yes/No probability',
	choice: 'Choice',
	score: 'Ordered score',
};

const typeOptions = (Object.keys(typeNames) as Kind[]).map((type) => ({
	value: type,
	component: `${typeNames[type]} (${type})`,
}));

export const defaults: Record<Kind, Decision> = {
	noul: {
		type: 'noul',
		instructions: 'Is the person wearing a hat?',
		options: [
			{
				label: 'Yes',
				description: "A hat is visibly worn on the person's head.",
			},
			{
				label: 'No',
				description: "No hat is visible on the person's head.",
			},
		],
	},
	choice: {
		type: 'choice',
		instructions: 'What is the person’s posture?',
		options: [
			{
				label: 'Standing',
				description: 'The person is upright on their feet.',
			},
			{
				label: 'Sitting',
				description: 'The person is seated.',
			},
			{
				label: 'Other or unclear',
				description:
					'Another posture, or the crop does not show enough detail.',
			},
		],
	},
	score: {
		type: 'score',
		instructions: 'How clearly is the person’s face visible?',
		options: [
			{ label: 'Not visible', description: 'The face is not visible.' },
			{
				label: 'Partly visible',
				description: 'Only a small portion of the face is visible.',
			},
			{
				label: 'Mostly visible',
				description: 'Most of the face is visible.',
			},
			{ label: 'Fully visible', description: 'The face is clearly visible.' },
		],
	},
};
/** Check the limits and unique answer labels required by the backend. */
export function validDecision(value: Decision) {
	return (
		!!value.instructions.trim() &&
		value.instructions.length <= 2000 &&
		value.options.length >= 2 &&
		value.options.length <= 10 &&
		(value.type !== 'noul' || value.options.length === 2) &&
		value.options.every(
			(o) =>
				o.label.trim() &&
				o.label.length <= 60 &&
				o.description.trim() &&
				o.description.length <= 500,
		) &&
		new Set(value.options.map((o) => o.label.trim().toLowerCase())).size ===
			value.options.length
	);
}

/** Edit one typed question and its answer criteria. */
export function DecisionEditor({
	value,
	disabled,
	onChange,
	onTypeChange,
	idPrefix = '',
}: {
	value: Decision;
	disabled: boolean;
	onChange: (value: Decision) => void;
	onTypeChange: (kind: Kind) => void;
	idPrefix?: string;
}) {
	function changeOption(index: number, key: keyof Option, content: string) {
		onChange({
			...value,
			options: value.options.map((o, i) =>
				i === index ? { ...o, [key]: content } : o,
			),
		});
	}
	return (
		<Flex direction="column" gap="sm">
			<Flex direction="column" gap="xs">
				<label htmlFor={`${idPrefix}question-type`}>
					<Label text="Question type" />
				</label>
				<Select
					id={`${idPrefix}question-type`}
					items={typeOptions}
					value={value.type}
					disabled={disabled}
					onChange={(type) => onTypeChange(type as Kind)}
					aria-describedby={`${idPrefix}question-type-help`}
				/>
				<SubLabel
					id={`${idPrefix}question-type-help`}
					text={
						value.type === 'noul'
							? 'Returns the probability of Yes. Edit what Yes and No mean below.'
							: value.type === 'choice'
								? 'Chooses one of your answers and returns a probability for every option.'
								: 'Returns an expected score on your ordered scale from 0 to N, plus a probability for every level.'
					}
				/>
			</Flex>
			<Flex direction="column" gap="xs">
				<label htmlFor={`${idPrefix}question`}>
					<Label text="Question or instructions" />
				</label>
				<Textarea
					id={`${idPrefix}question`}
					value={value.instructions}
					maxLength={2000}
					rows={4}
					disabled={disabled}
					aria-describedby={`${idPrefix}question-help`}
					onChange={(event) =>
						onChange({ ...value, instructions: event.target.value })
					}
				/>
				<SubLabel
					id={`${idPrefix}question-help`}
					text="This is the exact question sent to the model."
				/>
			</Flex>
			<h6>
				<Label
					text={
						value.type === 'score' ? 'Ordered score levels' : 'Answer options'
					}
					weight="medium"
				/>
			</h6>
			{value.options.map((o, index) => (
				<fieldset
					className="vdm-option"
					aria-labelledby={`${idPrefix}option-${index}`}
					key={`${value.type}-${index}`}
				>
					<Flex direction="row" align="center" justify="between" gap="sm">
						<NormalText
							id={`${idPrefix}option-${index}`}
							weight="medium"
							text={
								value.type === 'noul'
									? index === 0
										? 'Yes (true)'
										: 'No (false)'
									: value.type === 'score'
										? `Level ${index}`
										: `Option ${index + 1}`
							}
						/>
						<Flex direction="row" align="center" gap="xs">
							{value.type === 'score' && index > 0 && (
								<Button
									variant="ghost"
									intent="gray"
									size="sm"
									icon={ArrowUpIcon}
									disabled={disabled}
									aria-label={`Move level ${index} up`}
									onClick={() => {
										const options = [...value.options];
										[options[index - 1], options[index]] = [
											options[index],
											options[index - 1],
										];
										onChange({ ...value, options });
									}}
								>
									Move up
								</Button>
							)}
							{value.type !== 'noul' && (
								<Button
									variant="ghost"
									intent="gray"
									size="sm"
									icon={DeleteIcon}
									disabled={disabled || value.options.length <= 2}
									aria-label={`Remove option ${index + 1}`}
									onClick={() =>
										onChange({
											...value,
											options: value.options.filter((_, i) => i !== index),
										})
									}
								>
									Remove
								</Button>
							)}
						</Flex>
					</Flex>
					<Flex direction="column" gap="xs">
						<label htmlFor={`${idPrefix}answer-label-${index}`}>
							<Label text={`Label ${index + 1}`} />
						</label>
						<Input
							id={`${idPrefix}answer-label-${index}`}
							value={o.label}
							maxLength={60}
							disabled={disabled}
							onChange={(event) =>
								changeOption(index, 'label', event.target.value)
							}
						/>
					</Flex>
					<Flex direction="column" gap="xs">
						<label htmlFor={`${idPrefix}answer-description-${index}`}>
							<Label text={`Description ${index + 1}`} />
						</label>
						<Textarea
							id={`${idPrefix}answer-description-${index}`}
							value={o.description}
							maxLength={500}
							rows={2}
							disabled={disabled}
							onChange={(event) =>
								changeOption(index, 'description', event.target.value)
							}
						/>
					</Flex>
				</fieldset>
			))}
			{value.type !== 'noul' && (
				<Button
					variant="outline"
					intent="gray"
					icon={AddIcon}
					disabled={disabled || value.options.length >= 10}
					onClick={() =>
						onChange({
							...value,
							options: [
								...value.options,
								{ label: `New ${value.options.length + 1}`, description: '' },
							],
						})
					}
				>
					Add {value.type === 'score' ? 'level' : 'option'}
				</Button>
			)}
			{!validDecision(value) && (
				<Alert
					role="status"
					intent="warning"
					variant="light"
					description="Enter a question and 2 to 10 unique labels with descriptions. Yes/No uses exactly two answers."
				/>
			)}
		</Flex>
	);
}

/** Show the selected answer and every returned probability. */
export function DecisionOutput({ result }: { result: DecisionResult }) {
	return (
		<>
			<div className="vdm-score">
				<NormalText
					weight="bold"
					text={
						result.type === 'noul'
							? `${((result.yes_probability ?? 0) * 100).toFixed(1)}%`
							: result.type === 'choice'
								? result.choice
								: result.score?.toFixed(2)
					}
				/>
				<SubLabel
					text={
						result.type === 'noul'
							? `Probability of ${result.probabilities[0].label}`
							: result.type === 'choice'
								? 'Selected answer'
								: `Expected score from 0 to ${result.probabilities.length - 1}`
					}
				/>
			</div>
			<div className="vdm-probabilities">
				{result.probabilities.map((o, i) => (
					<Flex direction="column" gap="xs" key={o.label}>
						<Flex direction="row" justify="between" gap="sm">
							<Label
								weight="medium"
								text={result.type === 'score' ? `${i}. ${o.label}` : o.label}
							/>
							<SubLabel text={`${(o.probability * 100).toFixed(1)}%`} />
						</Flex>
						<Progress
							value={o.probability * 100}
							aria-label={`${o.label} probability`}
						/>
						<SubLabel text={o.description} />
					</Flex>
				))}
			</div>
		</>
	);
}
