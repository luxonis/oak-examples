import { Slider } from '@luxonis/ui-components';
import { type ReactNode, useCallback } from 'react';

export interface SliderControlProps {
	label?: ReactNode;
	value: number;
	onChange: (v: number) => void;
	onCommit?: (v: number) => void;
	min?: number;
	max?: number;
	step?: number;
	disabled?: boolean;
	id?: string;
	'aria-label'?: string;
}

export function SliderControl({
	label,
	value,
	onChange,
	onCommit,
	min = 0,
	max = 1,
	step = 0.01,
	disabled,
	id,
	...aria
}: SliderControlProps) {
	const commit = useCallback(
		(nextValue: number[]) => onCommit?.(nextValue[0] ?? value),
		[onCommit, value],
	);

	return (
		<div className="flex flex-col gap-2">
			{label ? (
				<label htmlFor={id} className="font-medium">
					{label}
				</label>
			) : null}
			<Slider
				id={id}
				value={value}
				onChange={onChange}
				onValueCommit={commit}
				min={min}
				max={max}
				step={step}
				disabled={disabled}
				{...aria}
			/>
		</div>
	);
}
