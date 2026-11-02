import { Slider } from '@luxonis/ui-components';

type SettingsSliderProps = {
	id: string;
	label: string;
	value: number;
	onChange: (value: number) => void;
	min: number;
	max: number;
	step: number;
	unit?: string;
};

/** Render a labeled Luxonis slider with its current numeric setting. */
export function SettingsSlider({
	id,
	label,
	value,
	onChange,
	min,
	max,
	step,
	unit = '',
}: SettingsSliderProps) {
	return (
		<div className="slider-control">
			<label id={`${id}-label`} htmlFor={id}>
				{label}: {value.toFixed(unit ? 1 : 2)}
				{unit}
			</label>
			<Slider
				id={id}
				value={value}
				onChange={onChange}
				min={min}
				max={max}
				step={step}
				aria-labelledby={`${id}-label`}
			/>
		</div>
	);
}
