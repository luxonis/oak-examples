import { Streams } from '@luxonis/depthai-viewer-common';
import { Button, Label, StyledText } from '@luxonis/ui-components';
import AppLayout from './components/AppLayout';
import PanelSection from './components/PanelSection';
import DetectionSettingsSection from './detection/DetectionSettingsSection';
import {
	COLOR_STREAM_TOPIC,
	DETECTIONS_TOPIC,
	MEASUREMENT_TOPICS,
	sortTopicsBy,
} from './streamTopics';
import DistanceOffsetSection from './supportPlaneCalibration/DistanceOffsetSection';
import { useSupportPlaneCalibration } from './supportPlaneCalibration/useSupportPlaneCalibration';
import { mmToCm } from './units';

function MeasurementView() {
	const { statusQuery, retryMutation } = useSupportPlaneCalibration();
	const cameraDistanceMm = statusQuery.data?.camera_distance_mm ?? null;
	const cameraDistanceCm =
		cameraDistanceMm === null ? null : mmToCm(cameraDistanceMm);
	const distanceOffsetMm = statusQuery.data?.distance_offset_mm ?? 0;

	return (
		<AppLayout
			stream={
				<Streams
					defaultTopics={MEASUREMENT_TOPICS}
					topicGroups={{
						[COLOR_STREAM_TOPIC]: 'preview',
						[DETECTIONS_TOPIC]: 'preview',
					}}
					numberOfColumns={1}
					topicSortingFunction={sortTopicsBy(MEASUREMENT_TOPICS)}
				/>
			}
			controls={
				<>
					<PanelSection title="Support plane">
						{cameraDistanceCm !== null ? (
							<div className="flex items-center justify-between gap-2">
								<Label text="Camera distance" color="normal" />
								<Label text={`${cameraDistanceCm.toFixed(1)} cm`} />
							</div>
						) : null}
						<div className="flex">
							<Button
								type="button"
								variant="outline"
								label="Recalibrate"
								disabled={retryMutation.isPending}
								onClick={() => {
									// The polled status then switches back to support plane calibration.
									retryMutation.mutate({});
								}}
							/>
						</div>
						{retryMutation.error ? (
							<StyledText
								size="label"
								color="error"
								text={retryMutation.error.message}
							/>
						) : null}
					</PanelSection>
					{cameraDistanceCm !== null ? (
						<DistanceOffsetSection
							cameraDistanceCm={cameraDistanceCm}
							offsetCm={mmToCm(distanceOffsetMm)}
						/>
					) : null}
					<DetectionSettingsSection />
				</>
			}
		/>
	);
}

export default MeasurementView;
