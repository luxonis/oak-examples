import { Streams } from '@luxonis/depthai-viewer-common';
import { Button, StyledText } from '@luxonis/ui-components';
import AppLayout from './components/AppLayout';
import DetectionSettingsButton from './detection/DetectionSettingsButton';
import {
	COLOR_STREAM_TOPIC,
	DETECTIONS_TOPIC,
	MEASUREMENT_TOPICS,
	sortTopicsBy,
} from './streamTopics';
import DistanceOffsetButton from './supportPlaneCalibration/DistanceOffsetButton';
import { useSupportPlaneCalibration } from './supportPlaneCalibration/useSupportPlaneCalibration';
import { mmToCm } from './units';

function MeasurementView() {
	const { statusQuery, retryMutation } = useSupportPlaneCalibration();
	const cameraDistanceMm = statusQuery.data?.camera_distance_mm ?? null;
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
				<div className="flex flex-col gap-2">
					{/* Positioned so the toolbar panels span the row */}
					<div className="relative flex flex-wrap gap-2">
						{cameraDistanceMm !== null ? (
							<DistanceOffsetButton
								cameraDistanceCm={mmToCm(cameraDistanceMm)}
								offsetCm={mmToCm(distanceOffsetMm)}
							/>
						) : null}
						<DetectionSettingsButton />
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
				</div>
			}
		/>
	);
}

export default MeasurementView;
