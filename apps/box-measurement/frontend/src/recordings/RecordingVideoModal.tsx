import {
    Flex,
    LightSubLabel,
    ModalContent,
    ModalContextAware,
    ModalHeader,
    useRequireMultiModalContext,
} from "@luxonis/common-fe-components";
import { css } from "../../styled-system/css/css.mjs";
import { formatRecordingTimeRange } from "./recordingFormat";
import { RecordingVideo } from "./RecordingVideo";
import type { Recording } from "./useRecordings";

const dateFormatter = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
});

export type RecordingsModalContext = {
    recordingVideo: Recording;
};

function RecordingVideoModalBody({ recording }: { recording: Recording }) {
    return (
        <ModalContent
            size="full"
            preventOverlayClick={false}
            className={css({
                width: "min(100vw - 2rem, 72rem)",
                maxWidth: "72rem",
                maxHeight: "calc(100vh - 2rem)",
            })}
        >
            <ModalHeader title="Footage" />
            <Flex direction="column" gap="md">
                <LightSubLabel
                    text={`${dateFormatter.format(
                        recording.started_at,
                    )} · ${formatRecordingTimeRange(recording)}`}
                />
                <RecordingVideo filename={recording.filename} />
            </Flex>
        </ModalContent>
    );
}

export function RecordingVideoModal() {
    const context = useRequireMultiModalContext<RecordingsModalContext>();

    return (
        <ModalContextAware context={context} which="recordingVideo">
            {(recording) => <RecordingVideoModalBody recording={recording} />}
        </ModalContextAware>
    );
}
