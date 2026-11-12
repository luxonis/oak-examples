import {
    Alert,
    Button,
    Flex,
    WarningIcon,
} from "@luxonis/common-fe-components";
import { Streams } from "@luxonis/depthai-viewer-common";
import {
    needsCalibrationAttention,
    type CalibrationState,
} from "./calibration/calibrationState";
import { useSupportPlaneCalibrationStatus } from "./calibration/useSupportPlaneCalibration";
import Page from "./components/Page";
import DetectionSettingsButton from "./detection/DetectionSettingsButton";
import { useAppNavigate } from "./routing/useAppNavigate";

const STREAM_PANEL_ORDER = ["Color stream", "Detections"];

const getStreamPanelOrder = (topicName: string) => {
    const order = STREAM_PANEL_ORDER.indexOf(topicName);
    return order === -1 ? Number.MAX_SAFE_INTEGER : order;
};

function App() {
    const statusQuery = useSupportPlaneCalibrationStatus();
    const navigate = useAppNavigate();
    const state: CalibrationState | undefined = statusQuery.data?.state;

    const showCalibrationWarning = needsCalibrationAttention(state);

    return (
        <Page>
            <Flex direction="column" width="full" alignItems="center" gap="md">
                {showCalibrationWarning ? (
                    <Flex width="full" maxW="breakpoint-xl">
                        <Alert
                            width="full"
                            variant="light"
                            colorVariant="warning"
                            icon={WarningIcon}
                            title="Support surface is not calibrated"
                            description="Boxes are not measured until the support plane is confirmed."
                            actions={
                                <Button
                                    type="button"
                                    variant="filled"
                                    label="Calibrate"
                                    onClick={() => navigate("/calibration")}
                                />
                            }
                        />
                    </Flex>
                ) : null}
                <Flex width="full" justifyContent="flex-end">
                    <DetectionSettingsButton />
                </Flex>
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
        </Page>
    );
}

export default App;
