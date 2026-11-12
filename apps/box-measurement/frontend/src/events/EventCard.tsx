import {
    Button,
    Card,
    Flex,
    Icon,
    LightSubLabel,
    StyledText,
} from "@luxonis/common-fe-components";
import {
    MdDeleteOutline as DeleteIcon,
    MdImage as ImageIcon,
} from "react-icons/md";
import { css } from "../../styled-system/css/css.mjs";
import { EventImage } from "./EventImage";
import { formatDimensions, formatVolume } from "./eventFormat";
import EventTypeBadge from "./EventTypeBadge";
import { EventRecord } from "./useEvents";

const timestampFormatter = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
});

type EventCardProps = {
    event: EventRecord;
    onClick?: () => void;
    onDelete?: () => void;
    isDeleting?: boolean;
    isDeleteDisabled?: boolean;
};

export function EventCard({
    event,
    onClick,
    onDelete,
    isDeleting = false,
    isDeleteDisabled = false,
}: EventCardProps) {
    const imageFile = event.files.find((file) => file.name === "image") ?? null;
    const hasImage = imageFile !== null;
    const dimensions = formatDimensions(event);
    const volume = formatVolume(event);

    return (
        <Card
            fullWidth
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
                    <StyledText
                        text={`Event #${event.id}`}
                        size="label"
                        color="normal"
                        weight="bold"
                        break="none"
                        className={css({
                            minWidth: 0,
                        })}
                    />
                    <EventTypeBadge eventType={event.event_type} />
                </Flex>
            }
            footer={
                <Flex
                    alignItems="center"
                    justifyContent="space-between"
                    gap="sm"
                    width="full"
                >
                    <LightSubLabel
                        text={timestampFormatter.format(event.created_at)}
                    />
                    {onDelete ? (
                        <Button
                            type="button"
                            variant="ghost"
                            icon={DeleteIcon}
                            label={isDeleting ? "Deleting..." : "Delete"}
                            disabled={isDeleting || isDeleteDisabled}
                            onClick={(clickEvent) => {
                                clickEvent.stopPropagation();
                                onDelete();
                            }}
                        />
                    ) : null}
                </Flex>
            }
        >
            <Flex direction="column" gap="sm">
                <Flex gap="md" flexWrap="wrap" alignItems="baseline">
                    <StyledText
                        size="label"
                        color="normal"
                        weight="medium"
                        text={
                            dimensions
                                ? `L × W × H: ${dimensions}`
                                : "No measurement captured"
                        }
                    />
                    {volume ? (
                        <LightSubLabel text={`Volume: ${volume}`} />
                    ) : null}
                    <LightSubLabel text={`Track ${event.track_id}`} />
                </Flex>

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
                        background="linear-gradient(135deg, rgba(33, 92, 255, 0.14), rgba(33, 92, 255, 0.03))"
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
            </Flex>
        </Card>
    );
}
