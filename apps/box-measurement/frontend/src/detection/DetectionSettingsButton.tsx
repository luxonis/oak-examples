import { StyledText } from '@luxonis/ui-components';
import { useState } from 'react';

import ToolbarPanel from '../components/ToolbarPanel';
import DetectionConfidenceField from './DetectionConfidenceField';
import { useDetectionConfidenceThresholdDraft } from './useDetectionConfidenceThreshold';

function DetectionSettingsButton() {
	const [open, setOpen] = useState(false);
	const { value, setValue, apply, error } =
		useDetectionConfidenceThresholdDraft();

	return (
		<ToolbarPanel
			label="Detection settings"
			open={open && value !== undefined}
			onOpenChange={setOpen}
			disabled={value === undefined}
		>
			{value !== undefined ? (
				<DetectionConfidenceField
					value={value}
					onChange={setValue}
					onCommit={apply}
				/>
			) : null}
			{error ? (
				<StyledText size="label" color="error" text={error.message} />
			) : null}
		</ToolbarPanel>
	);
}

export default DetectionSettingsButton;
