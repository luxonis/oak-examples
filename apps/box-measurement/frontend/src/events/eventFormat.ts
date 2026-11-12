import { EventRecord } from "./useEvents";

const formatCm = (mm: number) => (mm / 10).toFixed(1);

export function formatDimensions(event: EventRecord): string | null {
    if (
        event.length_mm === null ||
        event.width_mm === null ||
        event.height_mm === null
    ) {
        return null;
    }

    return `${formatCm(event.length_mm)} × ${formatCm(event.width_mm)} × ${formatCm(event.height_mm)} cm`;
}

export function formatVolume(event: EventRecord): string | null {
    if (event.volume_mm3 === null) {
        return null;
    }

    return `${Math.round(event.volume_mm3 / 1000)} cm³`;
}
