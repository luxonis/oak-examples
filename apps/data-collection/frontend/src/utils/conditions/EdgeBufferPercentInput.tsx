import { Input } from '@luxonis/ui-components';
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

	return (
		<div className="flex flex-col gap-2">
			<label htmlFor={inputId} className="font-medium">
				Edge buffer (each side) - 0-49%
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
				aria-label="Lost-in-middle edge buffer percent (0-49)"
			/>
			<span className="text-xs text-muted-foreground">
				We ignore the outer margin on every edge; only losses inside the
				remaining center fire snaps.
			</span>
		</div>
	);
}
