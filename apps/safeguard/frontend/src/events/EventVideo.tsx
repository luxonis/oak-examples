import {
    Alert,
    CircleLoader,
    Flex,
    NormalText,
    WarningIcon,
} from "@luxonis/common-fe-components";
import { useEffect, useMemo } from "react";
import { css } from "../../styled-system/css/css.mjs";

import { useEventFile } from "./useEventFile";

type EventVideoProps = Omit<
    React.VideoHTMLAttributes<HTMLVideoElement>,
    "src"
> & {
    path: string;
};

const mediaShellClassName = css({
    width: "100%",
    minHeight: "18rem",
    borderRadius: "lg",
    border: "border.base",
    backgroundColor: "rgba(15, 23, 42, 0.92)",
});

export function EventVideo({ path, ...videoProps }: EventVideoProps) {
    const { eventFileQuery } = useEventFile(path);

    const videoUrl = useMemo(() => {
        if (!eventFileQuery.data) {
            return null;
        }

        const bytes = new Uint8Array(eventFileQuery.data.byteLength);
        bytes.set(
            new Uint8Array(
                eventFileQuery.data.buffer,
                eventFileQuery.data.byteOffset,
                eventFileQuery.data.byteLength,
            ),
        );

        return URL.createObjectURL(new Blob([bytes], { type: "video/mp4" }));
    }, [eventFileQuery.data]);

    useEffect(() => {
        if (!videoUrl) {
            return;
        }

        return () => {
            URL.revokeObjectURL(videoUrl);
        };
    }, [videoUrl]);

    if (eventFileQuery.isPending) {
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
                <NormalText text="Loading event video..." />
            </Flex>
        );
    }

    if (eventFileQuery.error) {
        return (
            <div className={mediaShellClassName}>
                <Alert
                    variant="light"
                    colorVariant="error"
                    icon={WarningIcon}
                    title="Unable to load event video"
                    description={eventFileQuery.error.message}
                />
            </div>
        );
    }

    if (!videoUrl) {
        return (
            <div className={mediaShellClassName}>
                <Alert
                    variant="light"
                    colorVariant="warning"
                    icon={WarningIcon}
                    title="Event video unavailable"
                    description="This event does not have a playable saved video."
                />
            </div>
        );
    }

    return (
        <video
            src={videoUrl}
            controls
            preload="metadata"
            className={css({
                width: "100%",
                maxHeight: "75vh",
                borderRadius: "lg",
                backgroundColor: "black",
            })}
            {...videoProps}
        />
    );
}
