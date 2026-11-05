import { Badge } from "@luxonis/common-fe-components";
import { MdWarningAmber as DangerIcon } from "react-icons/md";
import { EventType } from "./useEvents";

function EventTypeBadge({ eventType }: { eventType: EventType }) {
    const getLabel = (eventType: EventType) => {
        const lowercase = eventType.toLowerCase();
        return lowercase[0].toUpperCase() + lowercase.slice(1);
    };

    const getVariant = (eventType: EventType) => {
        if (eventType === "DANGER") {
            return "error";
        }
        return "warning";
    };

    return (
        <Badge
            label={getLabel(eventType)}
            icon={DangerIcon}
            variant={getVariant(eventType)}
        />
    );
}

export default EventTypeBadge;
