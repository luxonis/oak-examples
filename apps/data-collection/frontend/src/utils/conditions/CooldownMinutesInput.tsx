import { Input } from '@luxonis/ui-components';
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

	return (
		<div className="flex flex-col gap-2">
			<label htmlFor={inputId} className="font-medium">
				{label}
			</label>
			<div className="flex items-center gap-3">
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
					aria-label={ariaLabel || 'Cooldown (minutes, max 1 decimal)'}
				/>
				<span className="text-muted-foreground">minutes</span>
			</div>
			{!valid ? (
				<span className="text-xs text-destructive">
					Enter a non-negative number with at most one decimal place.
				</span>
			) : null}
		</div>
	);
}
