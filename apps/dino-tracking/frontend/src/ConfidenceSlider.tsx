import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Slider } from '@luxonis/ui-components';
import { useCallback } from 'react';
import { postToDinoTrackingService } from './services.ts';

interface ConfidenceSliderProps {
	value: number;
	setValue: (value: number) => void;
}

export function ConfidenceSlider({ value, setValue }: ConfidenceSliderProps) {
	const connection = useDaiConnection();

	const handleCommit = useCallback(
		(nextValue: number[]) => {
			const threshold = nextValue[0] ?? value;

			if (Number.isFinite(threshold)) {
				console.log('[Threshold] Sending to backend:', threshold);

				postToDinoTrackingService(
					connection.daiConnection,
					'Threshold Update Service',
					{ threshold },
					(response) => {
						console.log('[Threshold] Backend acknowledged:', response);
					},
				);
			} else {
				console.warn('[Threshold] Invalid value:', threshold);
			}
		},
		[connection.daiConnection, value],
	);

	return (
		<div className="flex flex-col gap-2">
			<span className="font-medium">
				Confidence Threshold: {value.toFixed(2)}
			</span>
			<Slider
				value={value}
				onChange={setValue}
				onValueCommit={handleCommit}
				min={0}
				max={1}
				step={0.01}
				aria-label="Confidence threshold"
			/>
		</div>
	);
}
