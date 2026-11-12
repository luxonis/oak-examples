import {
    Flex,
    Icon,
    LightSubLabel,
    ModalContent,
    ModalContextAware,
    ModalHeader,
    NormalText,
    useRequireMultiModalContext,
} from "@luxonis/common-fe-components";
import { MdVideocam as VideoIcon } from "react-icons/md";
import { css } from "../../styled-system/css/css.mjs";
import { formatDimensions, formatVolume } from "./eventFormat";
import EventTypeBadge from "./EventTypeBadge";
import { EventVideo } from "./EventVideo";
import type { EventRecord } from "./useEvents";

const timestampFormatter = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
});

export type EventsModalContext = {
    eventVideo: EventRecord;
};

type EventVideoModalBodyProps = {
    event: EventRecord;
};

function EventVideoModalBody({ event }: EventVideoModalBodyProps) {
    const videoFile = event.files.find((file) => file.name === "video") ?? null;
    const dimensions = formatDimensions(event);
    const volume = formatVolume(event);

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
            <ModalHeader
                title={`Event #${event.id}`}
                actions={<EventTypeBadge eventType={event.event_type} />}
            />

            <Flex direction="column" gap="md">
                <Flex gap="md" flexWrap="wrap" alignItems="baseline">
                    <LightSubLabel
                        text={timestampFormatter.format(event.created_at)}
                    />
                    {dimensions ? (
                        <NormalText text={`L × W × H: ${dimensions}`} />
                    ) : null}
                    {volume ? (
                        <LightSubLabel text={`Volume: ${volume}`} />
                    ) : null}
                </Flex>
                {videoFile ? (
                    <EventVideo path={videoFile.path} />
                ) : (
                    <Flex
                        direction="column"
                        alignItems="center"
                        justifyContent="center"
                        gap="sm"
                        minH="72"
                        p="md"
                        borderRadius="lg"
                        border="border.base"
                        background="linear-gradient(135deg, rgba(33, 92, 255, 0.14), rgba(33, 92, 255, 0.03))"
                        textAlign="center"
                    >
                        <Icon icon={VideoIcon} size="xl" color="gray" />
                        <NormalText text="Video recording for this event is not available." />
                    </Flex>
                )}
            </Flex>
        </ModalContent>
    );
}

export function EventVideoModal() {
    const context = useRequireMultiModalContext<EventsModalContext>();

    return (
        <ModalContextAware context={context} which="eventVideo">
            {(event) => <EventVideoModalBody event={event} />}
        </ModalContextAware>
    );
}
