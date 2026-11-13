import { Streams } from '@luxonis/depthai-viewer-common';
import { Button, Card, NormalText, SubLabel } from '@luxonis/ui-components';
import StatusDot from '../components/StatusDot';
import {
	SUPPORT_PLANE_CALIBRATION_TOPICS,
	SUPPORT_PLANE_PREVIEW_TOPIC,
	sortTopicsBy,
} from '../streamTopics';
import {
	SUPPORT_PLANE_CALIBRATION_STATE_COLOR,
	SUPPORT_PLANE_CALIBRATION_STATUS_TEXT,
} from './supportPlaneCalibrationState';
import {
	useSupportPlaneCalibration,
	useSupportPlanePreview,
} from './useSupportPlaneCalibration';

const mmToCm = (mm: number | null | undefined) =>
	mm === null || mm === undefined ? null : mm / 10;

function SupportPlaneCalibrationView() {
	const { statusQuery, confirmMutation, retryMutation, selectMutation } =
		useSupportPlaneCalibration();
	// Turns the preview cloud on for as long as this view is shown.
	const previewError = useSupportPlanePreview();
	const state = statusQuery.data?.state;
	const candidateCount = statusQuery.data?.candidate_count ?? 0;
	const selectedIndex = statusQuery.data?.selected_index ?? 0;
	const cameraDistanceCm = mmToCm(statusQuery.data?.camera_distance_mm);
	const cameraTiltDeg = statusQuery.data?.camera_tilt_deg ?? null;
	const awaitingConfirmation = state === 'AWAITING_CONFIRMATION';
	const showCandidate = awaitingConfirmation && candidateCount > 0;
	const showCameraPose = cameraDistanceCm !== null && cameraTiltDeg !== null;
	const stateColor = state
		? SUPPORT_PLANE_CALIBRATION_STATE_COLOR[state]
		: undefined;
	const statusText =
		SUPPORT_PLANE_CALIBRATION_STATUS_TEXT[state ?? 'SEARCHING'];
	const error =
		statusQuery.error ??
		confirmMutation.error ??
		retryMutation.error ??
		selectMutation.error ??
		previewError;

	return (
		<div className="flex w-full flex-col items-center gap-4">
			<Card
				className="w-full max-w-7xl"
				title="Support plane calibration"
				subtitle="Remove boxes and other objects from the support plane before support plane calibration."
				fullWidth
			>
				<div className="flex flex-col gap-2">
					<div className="flex flex-wrap items-center justify-between gap-4">
						<div className="flex flex-col gap-1">
							<div className="flex items-center gap-2">
								{stateColor ? <StatusDot color={stateColor} /> : null}
								<NormalText text={statusText} />
							</div>
							{showCandidate || showCameraPose ? (
								<div className="flex flex-wrap items-center gap-1">
									{showCandidate ? (
										<SubLabel
											weight="bold"
											text={`Candidate ${selectedIndex + 1} of ${candidateCount}`}
										/>
									) : null}
									{showCandidate && showCameraPose ? (
										<SubLabel text="·" />
									) : null}
									{showCameraPose ? (
										<>
											<SubLabel text="Camera distance" />
											<SubLabel
												weight="bold"
												text={`${cameraDistanceCm.toFixed(1)} cm`}
											/>
											<SubLabel text="·" />
											<SubLabel text="Camera tilt" />
											<SubLabel
												weight="bold"
												text={`${Math.round(cameraTiltDeg)}°`}
											/>
										</>
									) : null}
								</div>
							) : null}
						</div>
						<div className="flex flex-wrap gap-2">
							{awaitingConfirmation ? (
								<>
									<Button
										type="button"
										variant="filled"
										label="Confirm support plane"
										disabled={confirmMutation.isPending}
										onClick={() => {
											confirmMutation.mutate({});
										}}
									/>
									<Button
										type="button"
										variant="outline"
										label="Next candidate"
										disabled={candidateCount < 2 || selectMutation.isPending}
										onClick={() => {
											selectMutation.mutate({
												direction: 1,
											});
										}}
									/>
								</>
							) : null}
							<Button
								type="button"
								variant="outline"
								label="Restart calibration"
								disabled={retryMutation.isPending}
								onClick={() => {
									retryMutation.mutate({});
								}}
							/>
						</div>
					</div>
					{error ? <SubLabel color="error" text={error.message} /> : null}
				</div>
			</Card>
			<div className="h-[42rem] min-h-[28rem] w-full min-w-1/2 md:h-[calc(100vh-24rem)]">
				<Streams
					defaultTopics={SUPPORT_PLANE_CALIBRATION_TOPICS}
					allowedTopics={SUPPORT_PLANE_CALIBRATION_TOPICS}
					topicGroups={{
						[SUPPORT_PLANE_PREVIEW_TOPIC]: SUPPORT_PLANE_PREVIEW_TOPIC,
					}}
					numberOfColumns={1}
					topicSortingFunction={sortTopicsBy(SUPPORT_PLANE_CALIBRATION_TOPICS)}
				/>
			</div>
		</div>
	);
}

export default SupportPlaneCalibrationView;
