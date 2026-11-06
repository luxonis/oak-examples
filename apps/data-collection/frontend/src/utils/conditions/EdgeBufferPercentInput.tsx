import { Flex, Input, Label, SubLabel } from '@luxonis/ui-components';
import { useId } from 'react';

interface EdgeBufferPercentInputProps {
	value: string;
	onChange: (v: string) => void;
	onBlur?: () => void;
	valid: boolean;
	disabled?: boolean;
}

export function EdgeBufferPercentInput({
	value,
	onChange,
	onBlur,
	valid,
	disabled,
}: EdgeBufferPercentInputProps) {
	const inputId = useId();
	const helpId = useId();

	return (
		<Flex direction="column" gap="xs">
			<label htmlFor={inputId}>
				<Label text="Edge buffer per side (0 to 49%)" />
			</label>
			<Input
				id={inputId}
				type="number"
				min={0}
				max={49}
				step={1}
				inputMode="numeric"
				pattern="\\d*"
				value={value}
				onChange={(e) => onChange(e.target.value)}
				onBlur={onBlur}
				disabled={disabled}
				aria-invalid={!valid && !disabled}
				aria-describedby={helpId}
				aria-label="Lost-in-middle edge buffer percent (0-49)"
			/>
			<SubLabel
				id={helpId}
				text="The outer margin on every edge is ignored. Only losses inside the remaining center fire snaps."
			/>
		</Flex>
	);
}
