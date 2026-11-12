import {
    Alert,
    CircleLoader,
    Flex,
    NormalText,
    WarningIcon,
} from "@luxonis/common-fe-components";
import { css } from "../../styled-system/css/css.mjs";

import { useObjectUrl } from "./useObjectUrl";
import { useRecordingFile } from "./useRecordingFile";

const mediaShellClassName = css({
    width: "100%",
    minHeight: "18rem",
    borderRadius: "lg",
    border: "border.base",
    backgroundColor: "rgba(15, 23, 42, 0.92)",
});

export function RecordingVideo({ filename }: { filename: string }) {
    const { recordingFileQuery } = useRecordingFile(filename);
    const videoUrl = useObjectUrl(recordingFileQuery.data, "video/mp4");

    if (recordingFileQuery.isPending) {
        return (
            <Flex
                className={mediaShellClassName}
                direction="column"
                alignItems="center"
                justifyContent="center"
                gap="sm"
                p="md"
            >
                <CircleLoader />
                <NormalText text="Loading footage..." />
            </Flex>
        );
    }

    if (recordingFileQuery.error || !videoUrl) {
        return (
            <div className={mediaShellClassName}>
                <Alert
                    variant="light"
                    colorVariant="error"
                    icon={WarningIcon}
                    title="Unable to load footage"
                    description={
                        recordingFileQuery.error?.message ??
                        "This footage is unavailable."
                    }
                />
            </div>
        );
    }

    return (
        <video
            src={videoUrl}
            controls
            autoPlay
            preload="metadata"
            className={css({
                width: "100%",
                maxHeight: "75vh",
                borderRadius: "lg",
                backgroundColor: "black",
            })}
        />
    );
}
