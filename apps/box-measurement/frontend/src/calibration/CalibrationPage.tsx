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
import Page from "../components/Page";
import StatusDot from "../components/StatusDot";
import {
    CALIBRATION_STATE_COLOR,
    CALIBRATION_STATUS_TEXT,
    formatOffsetCm,
    isCalibrated,
} from "./calibrationState";
import DistanceOffsetButton from "./DistanceOffsetButton";
import {
    useSupportPlaneCalibration,
    useSupportPlanePreview,
} from "./useSupportPlaneCalibration";

// Preserve an existing color subscription during calibration to reduce
// H264 interruptions. Only the surface preview is restarted.
const STREAM_PANEL_ORDER = ["Support surface preview"];

const getStreamPanelOrder = (topicName: string) => {
    const order = STREAM_PANEL_ORDER.indexOf(topicName);
    return order === -1 ? Number.MAX_SAFE_INTEGER : order;
};

const mmToCm = (mm: number | null | undefined) =>
    mm === null || mm === undefined ? null : mm / 10;

function CalibrationPage() {
    const {
        statusQuery,
        confirmMutation,
        retryMutation,
        selectMutation,
        distanceOffsetMutation,
    } = useSupportPlaneCalibration();
    // Turns the preview cloud on for as long as this page is mounted.
    const previewError = useSupportPlanePreview();
    const state = statusQuery.data?.state;
    const candidateCount = statusQuery.data?.candidate_count ?? 0;
    const selectedIndex = statusQuery.data?.selected_index ?? 0;
    const cameraDistanceCm = mmToCm(statusQuery.data?.camera_distance_mm);
    const correctedCameraDistanceCm = mmToCm(
        statusQuery.data?.corrected_camera_distance_mm,
    );
    const distanceOffsetCm = mmToCm(statusQuery.data?.distance_offset_mm) ?? 0;
    const cameraTiltDeg = statusQuery.data?.camera_tilt_deg ?? null;
    const awaitingConfirmation = state === "AWAITING_CONFIRMATION";
    const showCandidate = awaitingConfirmation && candidateCount > 0;
    const showCameraPose =
        correctedCameraDistanceCm !== null && cameraTiltDeg !== null;
    const stateColor = state ? CALIBRATION_STATE_COLOR[state] : undefined;
    const statusText = CALIBRATION_STATUS_TEXT[state ?? "SEARCHING"];
    const error =
        statusQuery.error ??
        confirmMutation.error ??
        retryMutation.error ??
        selectMutation.error ??
        previewError;

    return (
        <Page>
            <Flex direction="column" width="full" alignItems="center" gap="md">
                <Flex width="full" maxW="breakpoint-xl">
                    <Card
                        title={
                            <Flex direction="column">
                                <Header
                                    text="Support surface calibration"
                                    break="none"
                                />
                                {!isCalibrated(state) ? (
                                    <StyledText
                                        size="label"
                                        color="label"
                                        weight="medium"
                                        text="Remove boxes and other objects from the surface before calibration."
                                    />
                                ) : null}
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
                                                    text={`Surface ${selectedIndex + 1} of ${candidateCount}`}
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
                                                        text={`${correctedCameraDistanceCm.toFixed(1)} cm`}
                                                    />
                                                    {distanceOffsetCm !== 0 ? (
                                                        <SubLabel
                                                            text={`(offset ${formatOffsetCm(distanceOffsetCm)})`}
                                                        />
                                                    ) : null}
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
                                                label="Confirm surface"
                                                disabled={
                                                    confirmMutation.isPending
                                                }
                                                onClick={() => {
                                                    confirmMutation.mutate({});
                                                }}
                                            />
                                            <Button
                                                type="button"
                                                variant="outline"
                                                label="Next surface"
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
                                    {isCalibrated(state) &&
                                    cameraDistanceCm !== null ? (
                                        <DistanceOffsetButton
                                            cameraDistanceCm={cameraDistanceCm}
                                            offsetCm={distanceOffsetCm}
                                            onApply={(offsetCm, onSuccess) => {
                                                distanceOffsetMutation.mutate(
                                                    {
                                                        // The offset input has 0.1 cm steps
                                                        offset_mm: Math.round(
                                                            offsetCm * 10,
                                                        ),
                                                    },
                                                    { onSuccess },
                                                );
                                            }}
                                            isPending={
                                                distanceOffsetMutation.isPending
                                            }
                                            error={distanceOffsetMutation.error}
                                        />
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
                        defaultTopics={STREAM_PANEL_ORDER}
                        allowedTopics={STREAM_PANEL_ORDER}
                        topicGroups={{
                            "Support surface preview": "Support surface preview",
                        }}
                        numberOfColumns={1}
                        topicSortingFunction={(a, b) =>
                            getStreamPanelOrder(a.name) -
                            getStreamPanelOrder(b.name)
                        }
                    />
                </Flex>
            </Flex>
        </Page>
    );
}

export default CalibrationPage;
