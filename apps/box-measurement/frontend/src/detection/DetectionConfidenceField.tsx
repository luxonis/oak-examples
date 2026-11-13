import { Label, Slider } from '@luxonis/ui-components';

type DetectionConfidenceFieldProps = {
	value: number;
	onChange: (value: number) => void;
	onCommit: (value: number) => void;
	disabled?: boolean;
};

function DetectionConfidenceField({
	value,
	onChange,
	onCommit,
	disabled = false,
}: DetectionConfidenceFieldProps) {
	return (
		<div className="flex w-full flex-col gap-2">
			<div className="flex w-full items-center justify-between gap-2">
				<Label
					text="Detection confidence threshold"
					color="normal"
					weight="medium"
				/>
				<Label text={value.toFixed(2)} />
			</div>
			<Slider
				aria-label="Minimum detection confidence"
				min={0}
				max={1}
				step={0.01}
				value={value}
				onChange={onChange}
				onValueCommit={([committed]) => onCommit(committed)}
				disabled={disabled}
				thumbSize="sm"
			/>
		</div>
	);
}

export default DetectionConfidenceField;
