import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Slider } from '@luxonis/ui-components';
import { useState } from 'react';
import { postToCustomService } from './services.ts';

interface ConfidenceSliderProps {
	initialValue?: number;
}

export function ConfidenceSlider({
	initialValue = 0.5,
}: ConfidenceSliderProps) {
	const connection = useDaiConnection();
	const [value, setValue] = useState(initialValue);

	const handleCommit = () => {
		if (typeof value === 'number' && !Number.isNaN(value)) {
			console.log('Sending threshold to backend:', value);

			postToCustomService(
				connection.daiConnection,
				'Threshold Update Service',
				value,
				(response) => {
					console.log('Backend acknowledged threshold update:', response);
				},
			);
		} else {
			console.warn('Invalid value, skipping update:', value);
		}
	};

	return (
		<div className="flex flex-col gap-2">
			<div className="font-medium">
				Confidence Threshold: {value.toFixed(2)}
			</div>
			<Slider
				min={0.01}
				max={0.99}
				step={0.01}
				value={value}
				onChange={setValue}
				onValueCommit={handleCommit}
			/>
		</div>
	);
}
