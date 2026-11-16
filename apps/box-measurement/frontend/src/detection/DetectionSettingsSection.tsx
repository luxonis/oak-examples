import { StyledText } from '@luxonis/ui-components';

import PanelSection from '../components/PanelSection';
import DetectionConfidenceField from './DetectionConfidenceField';
import { useDetectionConfidenceThresholdDraft } from './useDetectionConfidenceThreshold';

function DetectionSettingsSection() {
	const { value, setValue, apply, error } =
		useDetectionConfidenceThresholdDraft();

	return (
		<PanelSection title="Detection settings">
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
		</PanelSection>
	);
}

export default DetectionSettingsSection;
