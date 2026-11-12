import type { Recording } from "./useRecordings";

const timeFormatter = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
});

export function getRecordingEnd(recording: Recording): Date | null {
    if (recording.ended_at.getTime() <= recording.started_at.getTime()) {
        return null;
    }

    return recording.ended_at;
}

export function formatRecordingTimeRange(recording: Recording): string {
    const start = timeFormatter.format(recording.started_at);
    const end = getRecordingEnd(recording);

    return end === null ? start : `${start} – ${timeFormatter.format(end)}`;
}
