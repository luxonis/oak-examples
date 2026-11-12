import {
    Button,
    Card,
    Flex,
    Header,
    NormalText,
    StyledText,
    SubLabel,
} from "@luxonis/common-fe-components";
import { Streams } from "@luxonis/depthai-viewer-common";
import StatusDot from "../components/StatusDot";
import {
    CALIBRATION_TOPICS,
    SUPPORT_PLANE_PREVIEW_TOPIC,
    sortTopicsBy,
} from "../streamTopics";
import {
    CALIBRATION_STATE_COLOR,
    CALIBRATION_STATUS_TEXT,
} from "./calibrationState";
import {
    useSupportPlaneCalibration,
    useSupportPlanePreview,
} from "./useSupportPlaneCalibration";

const mmToCm = (mm: number | null | undefined) =>
    mm === null || mm === undefined ? null : mm / 10;

function CalibrationView() {
    const { statusQuery, confirmMutation, retryMutation, selectMutation } =
        useSupportPlaneCalibration();
    // Turns the preview cloud on for as long as this view is shown.
    const previewError = useSupportPlanePreview();
    const state = statusQuery.data?.state;
    const candidateCount = statusQuery.data?.candidate_count ?? 0;
    const selectedIndex = statusQuery.data?.selected_index ?? 0;
    const cameraDistanceCm = mmToCm(statusQuery.data?.camera_distance_mm);
    const cameraTiltDeg = statusQuery.data?.camera_tilt_deg ?? null;
    const awaitingConfirmation = state === "AWAITING_CONFIRMATION";
    const showCandidate = awaitingConfirmation && candidateCount > 0;
    const showCameraPose = cameraDistanceCm !== null && cameraTiltDeg !== null;
    const stateColor = state ? CALIBRATION_STATE_COLOR[state] : undefined;
    const statusText = CALIBRATION_STATUS_TEXT[state ?? "SEARCHING"];
    const error =
        statusQuery.error ??
        confirmMutation.error ??
        retryMutation.error ??
        selectMutation.error ??
        previewError;

    return (
        <Flex direction="column" width="full" alignItems="center" gap="md">
            <Flex width="full" maxW="breakpoint-xl">
                <Card
                    title={
                        <Flex direction="column">
                            <Header
                                text="Support plane calibration"
                                break="none"
                            />
                            <StyledText
                                size="label"
                                color="label"
                                weight="medium"
                                text="Remove boxes and other objects from the support plane before calibration."
                            />
                        </Flex>
                    }
                    fullWidth
                >
                    <Flex direction="column" gap="sm">
                        <Flex
                            gap="md"
                            alignItems="center"
                            justifyContent="space-between"
                            flexWrap="wrap"
                        >
                            <Flex direction="column" gap="xs">
                                <Flex gap="xs" alignItems="center">
                                    {stateColor ? (
                                        <StatusDot color={stateColor} />
                                    ) : null}
                                    <NormalText text={statusText} />
                                </Flex>
                                {showCandidate || showCameraPose ? (
                                    <Flex
                                        gap="xs"
                                        alignItems="center"
                                        flexWrap="wrap"
                                    >
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
                                    </Flex>
                                ) : null}
                            </Flex>
                            <Flex gap="sm" flexWrap="wrap">
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
                                            disabled={
                                                candidateCount < 2 ||
                                                selectMutation.isPending
                                            }
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
                            </Flex>
                        </Flex>
                        {error ? <SubLabel text={error.message} /> : null}
                    </Flex>
                </Card>
            </Flex>
            <Flex
                height={{
                    base: "2xl",
                    md: "calc(100vh - 24rem)",
                }}
                minH="md"
                minW="1/2"
                width="full"
            >
                <Streams
                    defaultTopics={CALIBRATION_TOPICS}
                    allowedTopics={CALIBRATION_TOPICS}
                    topicGroups={{
                        [SUPPORT_PLANE_PREVIEW_TOPIC]:
                            SUPPORT_PLANE_PREVIEW_TOPIC,
                    }}
                    numberOfColumns={1}
                    topicSortingFunction={sortTopicsBy(CALIBRATION_TOPICS)}
                />
            </Flex>
        </Flex>
    );
}

export default CalibrationView;
