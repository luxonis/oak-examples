import { Badge } from "@luxonis/common-fe-components";
import {
    MdCheckCircleOutline as SuccessIcon,
    MdWarningAmber as FailureIcon,
} from "react-icons/md";
import { EventType } from "./useEvents";

const badgeConfig: Record<
    EventType,
    { label: string; variant: "success" | "warning" | "error" }
> = {
    SUCCESS: { label: "Success", variant: "success" },
    INCOMPLETE: { label: "Incomplete", variant: "warning" },
    FAILED_LOW_COVERAGE: { label: "Low coverage", variant: "error" },
};

function EventTypeBadge({ eventType }: { eventType: EventType }) {
    const config = badgeConfig[eventType];

    return (
        <Badge
            label={config.label}
            icon={eventType === "SUCCESS" ? SuccessIcon : FailureIcon}
            variant={config.variant}
        />
    );
}

export default EventTypeBadge;
