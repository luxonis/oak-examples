import {
    Alert,
    Button,
    Card,
    CircleLoader,
    EmptyView,
    Flex,
    ForwardIcon,
    Icon,
    NormalText,
    ProvideMultiModalContext,
    ReloadIcon,
    StyledText,
    useNewMultiModalContext,
    VideoIcon,
    WarningIcon,
} from "@luxonis/common-fe-components";

import { css } from "../../styled-system/css/css.mjs";
import Page from "../components/Page";
import {
    RecordingVideoModal,
    type RecordingsModalContext,
} from "./RecordingVideoModal";
import { formatRecordingTimeRange } from "./recordingFormat";
import { type Recording, useRecordings } from "./useRecordings";

const rowClassName = css({
    cursor: "pointer",
    _hover: { backgroundColor: "rgba(33, 92, 255, 0.08)" },
});

const dayFormatter = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
});
const hourFormatter = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
});
type HourGroup = { key: string; label: string; items: Recording[] };
type DayGroup = { key: string; label: string; hours: HourGroup[] };

function truncateToHour(date: Date): Date {
    const d = new Date(date);
    d.setMinutes(0, 0, 0);
    return d;
}

function truncateToDay(date: Date): Date {
    const d = new Date(date);
    d.setHours(0, 0, 0, 0);
    return d;
}

// Recordings arrive newest-first, so appending preserves that order at every level.
function groupByDayAndHour(recordings: Recording[]): DayGroup[] {
    const days: DayGroup[] = [];
    const dayByKey = new Map<string, DayGroup>();
    for (const recording of recordings) {
        const dayKey = truncateToDay(recording.started_at).toISOString();
        let day = dayByKey.get(dayKey);
        if (!day) {
            day = {
                key: dayKey,
                label: dayFormatter.format(recording.started_at),
                hours: [],
            };
            dayByKey.set(dayKey, day);
            days.push(day);
        }

        const hourDate = truncateToHour(recording.started_at);
        const hourKey = hourDate.toISOString();
        let hour = day.hours.find((h) => h.key === hourKey);
        if (!hour) {
            hour = { key: hourKey, label: hourFormatter.format(hourDate), items: [] };
            day.hours.push(hour);
        }
        hour.items.push(recording);
    }
    return days;
}

function RecordingsPage() {
    const modalContext = useNewMultiModalContext<RecordingsModalContext>();
    const { recordingsQuery } = useRecordings();

    const recordings = recordingsQuery.data?.recordings ?? [];
    const days = groupByDayAndHour(recordings);

    const isReady = !recordingsQuery.isPending && !recordingsQuery.error;

    return (
        <ProvideMultiModalContext context={modalContext}>
            <Page>
                <Flex direction="column" width="full" alignItems="center">
                    <Flex
                        direction="column"
                        width="full"
                        maxW="breakpoint-sm"
                        gap="md"
                    >
                        <Flex width="full" justifyContent="flex-end">
                            <Button
                                type="button"
                                variant="ghost"
                                icon={ReloadIcon}
                                label={
                                    recordingsQuery.isFetching
                                        ? "Refreshing..."
                                        : "Refresh"
                                }
                                disabled={recordingsQuery.isFetching}
                                onClick={() => {
                                    recordingsQuery.refetch();
                                }}
                            />
                        </Flex>

                        {recordingsQuery.isPending ? (
                            <Card fullWidth>
                                <Flex
                                    direction="column"
                                    alignItems="center"
                                    justifyContent="center"
                                    gap="sm"
                                    py="xl"
                                >
                                    <CircleLoader />
                                    <NormalText text="Loading footage..." />
                                </Flex>
                            </Card>
                        ) : null}

                        {!recordingsQuery.isPending && recordingsQuery.error ? (
                            <Alert
                                variant="light"
                                colorVariant="error"
                                icon={WarningIcon}
                                title="Unable to load footage"
                                description={recordingsQuery.error.message}
                            />
                        ) : null}

                        {isReady && recordings.length === 0 ? (
                            <Card fullWidth>
                                <EmptyView
                                    icon={VideoIcon}
                                    title="No footage yet"
                                    subtitle="Recorded RGB footage will appear here."
                                    py="xl"
                                />
                            </Card>
                        ) : null}

                        {days.map((day) => (
                            <Flex
                                key={day.key}
                                direction="column"
                                gap="sm"
                                width="full"
                            >
                                <StyledText
                                    text={day.label}
                                    size="label"
                                    color="normal"
                                    weight="bold"
                                    break="none"
                                />
                                {day.hours.map((hour) => (
                                    <Card
                                        key={hour.key}
                                        fullWidth
                                        title={
                                            <StyledText
                                                size="label"
                                                color="normal"
                                                weight="bold"
                                                text={hour.label}
                                            />
                                        }
                                    >
                                        <Flex direction="column" gap="xs">
                                            {hour.items.map((recording) => (
                                                <Flex
                                                    key={recording.filename}
                                                    className={rowClassName}
                                                    alignItems="center"
                                                    justifyContent="space-between"
                                                    gap="sm"
                                                    p="xs"
                                                    borderRadius="md"
                                                    role="button"
                                                    tabIndex={0}
                                                    onClick={() => {
                                                        modalContext.open(
                                                            "recordingVideo",
                                                            recording,
                                                        );
                                                    }}
                                                    onKeyDown={(event) => {
                                                        if (
                                                            event.key !== "Enter" &&
                                                            event.key !== " "
                                                        ) {
                                                            return;
                                                        }
                                                        event.preventDefault();
                                                        modalContext.open(
                                                            "recordingVideo",
                                                            recording,
                                                        );
                                                    }}
                                                >
                                                    <NormalText
                                                        text={formatRecordingTimeRange(
                                                            recording,
                                                        )}
                                                    />
                                                    <Icon
                                                        icon={ForwardIcon}
                                                        size="sm"
                                                        color="gray"
                                                    />
                                                </Flex>
                                            ))}
                                        </Flex>
                                    </Card>
                                ))}
                            </Flex>
                        ))}
                    </Flex>
                </Flex>
            </Page>

            <RecordingVideoModal />
        </ProvideMultiModalContext>
    );
}

export default RecordingsPage;
