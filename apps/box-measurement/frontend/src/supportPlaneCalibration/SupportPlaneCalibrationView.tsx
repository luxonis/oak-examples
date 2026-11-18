import { Streams } from '@luxonis/depthai-viewer-common';
import { Button, Label, NormalText, SubLabel } from '@luxonis/ui-components';
import AppLayout from '../components/AppLayout';
import PanelSection from '../components/PanelSection';
import StatusDot from '../components/StatusDot';
import {
	SUPPORT_PLANE_CALIBRATION_TOPICS,
	SUPPORT_PLANE_PREVIEW_TOPIC,
	sortTopicsBy,
} from '../streamTopics';
import { mmToCm } from '../units';
import {
	SUPPORT_PLANE_CALIBRATION_STATE_COLOR,
	SUPPORT_PLANE_CALIBRATION_STATUS_PENDING_TEXT,
	SUPPORT_PLANE_CALIBRATION_STATUS_TEXT,
} from './supportPlaneCalibrationState';
import {
	useSupportPlaneCalibration,
	useSupportPlanePreview,
} from './useSupportPlaneCalibration';

function SupportPlaneCalibrationView() {
	const { statusQuery, confirmMutation, retryMutation, selectMutation } =
		useSupportPlaneCalibration();
	// Turns the preview cloud on for as long as this view is shown.
	const previewError = useSupportPlanePreview();
	const state = statusQuery.data?.state;
	const candidateCount = statusQuery.data?.candidate_count ?? 0;
	const selectedIndex = statusQuery.data?.selected_index ?? 0;
	const cameraDistanceMm = statusQuery.data?.camera_distance_mm ?? null;
	const cameraDistanceCm =
		cameraDistanceMm === null ? null : mmToCm(cameraDistanceMm);
	const cameraTiltDeg = statusQuery.data?.camera_tilt_deg ?? null;
	const awaitingConfirmation = state === 'AWAITING_CONFIRMATION';
	const showCandidate = awaitingConfirmation && candidateCount > 0;
	const showCameraPose = cameraDistanceCm !== null && cameraTiltDeg !== null;
	const stateColor = state
		? SUPPORT_PLANE_CALIBRATION_STATE_COLOR[state]
		: undefined;
	const statusText = state
		? SUPPORT_PLANE_CALIBRATION_STATUS_TEXT[state]
		: SUPPORT_PLANE_CALIBRATION_STATUS_PENDING_TEXT;
	const error =
		statusQuery.error ??
		confirmMutation.error ??
		retryMutation.error ??
		selectMutation.error ??
		previewError;

	return (
		<AppLayout
			stream={
				<Streams
					defaultTopics={SUPPORT_PLANE_CALIBRATION_TOPICS}
					allowedTopics={SUPPORT_PLANE_CALIBRATION_TOPICS}
					topicGroups={{
						[SUPPORT_PLANE_PREVIEW_TOPIC]: SUPPORT_PLANE_PREVIEW_TOPIC,
					}}
					numberOfColumns={1}
					topicSortingFunction={sortTopicsBy(SUPPORT_PLANE_CALIBRATION_TOPICS)}
				/>
			}
			controls={
				<PanelSection
					title="Support plane calibration"
					hint="Remove boxes and other objects from the support plane."
				>
					<div className="flex items-center gap-2">
						{stateColor ? <StatusDot color={stateColor} /> : null}
						<NormalText text={statusText} />
					</div>
					{showCandidate ? (
						<SubLabel
							weight="bold"
							text={`Candidate ${selectedIndex + 1} of ${candidateCount}`}
						/>
					) : null}
					{showCameraPose ? (
						<>
							<div className="flex items-center justify-between gap-2">
								<Label text="Camera distance" color="normal" />
								<Label text={`${cameraDistanceCm.toFixed(1)} cm`} />
							</div>
							<div className="flex items-center justify-between gap-2">
								<Label text="Camera tilt" color="normal" />
								<Label text={`${Math.round(cameraTiltDeg)}°`} />
							</div>
						</>
					) : null}
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
					{error ? <SubLabel color="error" text={error.message} /> : null}
				</PanelSection>
			}
		/>
	);
}

export default SupportPlaneCalibrationView;
