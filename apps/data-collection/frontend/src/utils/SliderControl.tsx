import { Flex, Label, Slider } from '@luxonis/ui-components';
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
	...aria
}: SliderControlProps) {
	const commit = useCallback(
		(nextValue: number[]) => onCommit?.(nextValue[0] ?? value),
		[onCommit, value],
	);

	return (
		<Flex direction="column" gap="xs">
			{label ? <Label text={label} /> : null}
			<Slider
				value={value}
				onChange={onChange}
				onValueCommit={commit}
				min={min}
				max={max}
				step={step}
				disabled={disabled}
				{...aria}
			/>
		</Flex>
	);
}
