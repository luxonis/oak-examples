import {
    Card,
    Flex,
    Icon,
    LightSubLabel,
} from "@luxonis/common-fe-components";
import { MdImage as ImageIcon } from "react-icons/md";
import { css } from "../../styled-system/css/css.mjs";
import { EventImage } from "./EventImage";
import EventTypeBadge from "./EventTypeBadge";
import { EventRecord } from "./useEvents";

const timestampFormatter = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
});

type EventCardProps = {
    event: EventRecord;
    onClick?: () => void;
};

export function EventCard({ event, onClick }: EventCardProps) {
    const imageFile = event.files.find((file) => file.name === "image") ?? null;
    const hasImage = imageFile !== null;

    return (
        <Card
            fullWidth
            cardStyles="safeguard-event-card"
            withHoverEffect={!!onClick}
            role={onClick ? "button" : undefined}
            tabIndex={onClick ? 0 : undefined}
            onClick={onClick}
            title={
                <Flex
                    alignItems="center"
                    justifyContent="space-between"
                    gap="sm"
                    width="full"
                >
                    <span className="safeguard-event-title">Event #{event.id}</span>
                    <EventTypeBadge eventType={event.event_type} />
                </Flex>
            }
            footer={
                <LightSubLabel
                    text={timestampFormatter.format(event.triggered_at)}
                />
            }
        >
            <div
                className={css({
                    position: "relative",
                    width: "100%",
                    minHeight: "12rem",
                    overflow: "hidden",
                    borderRadius: "lg",
                    aspectRatio: "16/9",
                })}
            >
                <Flex
                    alignItems="center"
                    justifyContent="center"
                    width="full"
                    minH="12rem"
                    background="#f2f4f7"
                    border="border.base"
                    aspectRatio="16/9"
                >
                    <Icon
                        icon={ImageIcon}
                        size="xl"
                        color={hasImage ? "active" : "gray"}
                    />
                </Flex>

                {imageFile ? (
                    <EventImage
                        path={imageFile.path}
                        alt={`Saved frame for event #${event.id}`}
                        className={css({
                            position: "absolute",
                            inset: "0",
                            width: "100%",
                            height: "100%",
                            objectFit: "cover",
                            aspectRatio: "16/9",
                        })}
                    />
                ) : null}
            </div>
        </Card>
    );
}
