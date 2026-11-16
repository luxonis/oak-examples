import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Flex, Label, Slider } from '@luxonis/ui-components';
import { useState } from 'react';
import { postToObjectVolumeService } from './services.ts';

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

			postToObjectVolumeService(
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
		<Flex direction="column" gap="xs">
			<Label text={`Confidence threshold ${value.toFixed(2)}`} />
			<Slider
				min={0.01}
				max={0.99}
				step={0.01}
				value={value}
				onChange={setValue}
				onValueCommit={handleCommit}
				aria-label="Confidence threshold"
			/>
		</Flex>
	);
}
