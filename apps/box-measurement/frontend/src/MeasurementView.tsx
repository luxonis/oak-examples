import { Button, Flex, StyledText } from "@luxonis/common-fe-components";
import { Streams } from "@luxonis/depthai-viewer-common";
import DistanceOffsetButton from "./calibration/DistanceOffsetButton";
import { useSupportPlaneCalibration } from "./calibration/useSupportPlaneCalibration";
import DetectionSettingsButton from "./detection/DetectionSettingsButton";

const STREAM_PANEL_ORDER = ["Color stream", "Detections"];

const getStreamPanelOrder = (topicName: string) => {
    const order = STREAM_PANEL_ORDER.indexOf(topicName);
    return order === -1 ? Number.MAX_SAFE_INTEGER : order;
};

function MeasurementView() {
    const { statusQuery, retryMutation, distanceOffsetMutation } =
        useSupportPlaneCalibration();
    const cameraDistanceMm = statusQuery.data?.camera_distance_mm ?? null;
    const distanceOffsetMm = statusQuery.data?.distance_offset_mm ?? 0;

    return (
        <Flex direction="column" width="full" alignItems="center" gap="md">
            <Flex width="full" justifyContent="flex-end" gap="sm" flexWrap="wrap">
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
                        // The polled status then switches back to calibration.
                        retryMutation.mutate({});
                    }}
                />
            </Flex>
            {retryMutation.error ? (
                <Flex width="full" justifyContent="flex-end">
                    <StyledText
                        size="label"
                        color="error"
                        text={retryMutation.error.message}
                    />
                </Flex>
            ) : null}
            <Flex
                height={{
                    base: "2xl",
                    md: "calc(100vh - 6rem)",
                }}
                minH="lg"
                minW="1/2"
                width="full"
            >
                <Streams
                    defaultTopics={STREAM_PANEL_ORDER}
                    topicGroups={{
                        "Color stream": "preview",
                        Detections: "preview",
                    }}
                    numberOfColumns={1}
                    topicSortingFunction={(a, b) =>
                        getStreamPanelOrder(a.name) -
                        getStreamPanelOrder(b.name)
                    }
                />
            </Flex>
        </Flex>
    );
}

export default MeasurementView;
