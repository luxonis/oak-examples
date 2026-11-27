import { Flex, Input, Label, SubLabel } from '@luxonis/ui-components';
import { useId } from 'react';

interface CooldownMinutesInputProps {
	label?: string;
	value: string;
	onChange: (v: string) => void;
	onBlur?: () => void;
	valid: boolean;
	disabled?: boolean;
	ariaLabel?: string;
}

export function CooldownMinutesInput({
	label = 'Cooldown (minutes)',
	value,
	onChange,
	onBlur,
	valid,
	disabled,
	ariaLabel,
}: CooldownMinutesInputProps) {
	const inputId = useId();
	const errorId = useId();

	return (
		<Flex direction="column" gap="xs">
			<label htmlFor={inputId}>
				<Label text={label} />
			</label>
			<Flex direction="row" align="center" gap="xs">
				<Input
					id={inputId}
					className="min-w-0 flex-1"
					type="number"
					min={0}
					step={0.1}
					inputMode="decimal"
					value={value}
					onChange={(e) => onChange(e.target.value)}
					onBlur={onBlur}
					disabled={disabled}
					aria-invalid={!valid && !disabled}
					aria-describedby={valid ? undefined : errorId}
					aria-label={ariaLabel || 'Cooldown (minutes, max 1 decimal)'}
				/>
				<SubLabel text="minutes" />
			</Flex>
			{!valid ? (
				<SubLabel
					id={errorId}
					color="error"
					text="Enter a non-negative number with at most one decimal place."
				/>
			) : null}
		</Flex>
	);
}
