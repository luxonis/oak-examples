import { Streams } from '@luxonis/depthai-viewer-common';
import { Button, StyledText } from '@luxonis/ui-components';
import DetectionSettingsButton from './detection/DetectionSettingsButton';
import {
	COLOR_STREAM_TOPIC,
	DETECTIONS_TOPIC,
	MEASUREMENT_TOPICS,
	sortTopicsBy,
} from './streamTopics';
import DistanceOffsetButton from './supportPlaneCalibration/DistanceOffsetButton';
import { useSupportPlaneCalibration } from './supportPlaneCalibration/useSupportPlaneCalibration';

function MeasurementView() {
	const { statusQuery, retryMutation, distanceOffsetMutation } =
		useSupportPlaneCalibration();
	const cameraDistanceMm = statusQuery.data?.camera_distance_mm ?? null;
	const distanceOffsetMm = statusQuery.data?.distance_offset_mm ?? 0;

	return (
		<div className="flex w-full flex-col items-center gap-4">
			<div className="flex w-full flex-wrap justify-end gap-2">
				{cameraDistanceMm !== null ? (
					<DistanceOffsetButton
						cameraDistanceCm={cameraDistanceMm / 10}
						offsetCm={distanceOffsetMm / 10}
						onApply={(offsetCm, onSuccess) => {
							distanceOffsetMutation.mutate(
								// The offset input has 0.1 cm steps
								{ offset_mm: Math.round(offsetCm * 10) },
								{ onSuccess },
							);
						}}
						isPending={distanceOffsetMutation.isPending}
						error={distanceOffsetMutation.error}
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
				<div className="flex w-full justify-end">
					<StyledText
						size="label"
						color="error"
						text={retryMutation.error.message}
					/>
				</div>
			) : null}
			<div className="flex h-[42rem] min-h-[32rem] w-full min-w-1/2 md:h-[calc(100vh-6rem)]">
				<Streams
					defaultTopics={MEASUREMENT_TOPICS}
					topicGroups={{
						[COLOR_STREAM_TOPIC]: 'preview',
						[DETECTIONS_TOPIC]: 'preview',
					}}
					numberOfColumns={1}
					topicSortingFunction={sortTopicsBy(MEASUREMENT_TOPICS)}
				/>
			</div>
		</div>
	);
}

export default MeasurementView;
