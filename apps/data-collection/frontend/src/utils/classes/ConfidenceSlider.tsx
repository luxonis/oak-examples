import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { useEffect, useState } from 'react';
import { postToDataCollectionService } from '../../services.ts';
import { SliderControl } from '../SliderControl.tsx';

interface ConfidenceSliderProps {
	initialValue?: number;
	disabled?: boolean;
}

export function ConfidenceSlider({
	initialValue = 0.5,
	disabled,
}: ConfidenceSliderProps) {
	const connection = useDaiConnection();
	const [value, setValue] = useState(initialValue);

	useEffect(() => {
		if (Number.isFinite(initialValue)) {
			console.log(
				'[ConfidenceSlider] Restoring value from backend:',
				initialValue,
			);
			setValue(initialValue);
		}
	}, [initialValue]);

	const handleCommit = (newThreshold: number) => {
		if (!Number.isFinite(newThreshold)) return;

		postToDataCollectionService(
			connection.daiConnection,
			'Threshold Update Service',
			{ threshold: newThreshold },
			(resp) => console.log('[ConfidenceSlider] BE ack:', resp),
		);
	};

	return (
		<SliderControl
			label={`Confidence Threshold: ${(value * 100).toFixed(0)}%`}
			value={value}
			onChange={setValue}
			onCommit={handleCommit}
			min={0}
			max={1}
			step={0.01}
			disabled={disabled}
			aria-label="Confidence threshold"
		/>
	);
}
