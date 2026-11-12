import {
    Alert,
    Button,
    Card,
    CircleLoader,
    EmptyView,
    EventsIcon,
    Flex,
    Grid,
    NormalText,
    ProvideMultiModalContext,
    ReloadIcon,
    useNewMultiModalContext,
    WarningIcon,
} from "@luxonis/common-fe-components";
import { useEffect } from "react";
import { useSearchParams } from "react-router";

import Page from "../components/Page";
import { ArchiveStatusPanel } from "../export/ArchiveStatusPanel";
import { ExportArchiveButton } from "../export/ExportArchiveButton";
import { useEventExport } from "../export/useEventExport";
import { EventCard } from "./EventCard";
import { EventsPagination } from "./EventsPagination";
import { EventVideoModal, type EventsModalContext } from "./EventVideoModal";
import { useDeleteEvent } from "./useDeleteEvent";
import { useEvents } from "./useEvents";

const EVENTS_PAGE_SIZE = 8;

function parsePageParam(pageParam: string | null) {
    const page = Number(pageParam);

    if (!Number.isInteger(page) || page < 1) {
        return 1;
    }

    return page;
}

function EventsPage() {
    const modalContext = useNewMultiModalContext<EventsModalContext>();
    const [searchParams, setSearchParams] = useSearchParams();
    const currentPage = parsePageParam(searchParams.get("page"));
    const { eventsQuery } = useEvents({
        offset: (currentPage - 1) * EVENTS_PAGE_SIZE,
        limit: EVENTS_PAGE_SIZE,
    });
    const { deleteEventMutation } = useDeleteEvent();
    const { exportStatusQuery, createExportMutation, deleteExportMutation } =
        useEventExport();
    const exportStatus = exportStatusQuery.data;
    // The backend refuses event deletion while an export reads the events
    const isExportPreparing =
        exportStatus?.state === "preparing" || createExportMutation.isPending;
    const events = eventsQuery.data?.events ?? [];
    const totalCount = eventsQuery.data?.total_count ?? 0;
    const totalPages = Math.max(1, Math.ceil(totalCount / EVENTS_PAGE_SIZE));
    const isOutOfRangePage =
        !eventsQuery.isPending &&
        !eventsQuery.error &&
        currentPage > totalPages;
    const shouldShowPagination =
        !eventsQuery.isPending &&
        !eventsQuery.error &&
        !isOutOfRangePage &&
        totalPages > 1;
    useEffect(() => {
        if (searchParams.get("page") === String(currentPage)) {
            return;
        }

        const nextSearchParams = new URLSearchParams(searchParams);
        nextSearchParams.set("page", String(currentPage));
        setSearchParams(nextSearchParams, {
            replace: true,
        });
    }, [currentPage, searchParams, setSearchParams]);

    useEffect(() => {
        if (eventsQuery.isPending || eventsQuery.error) {
            return;
        }

        const clampedPage = Math.min(currentPage, totalPages);

        if (clampedPage === currentPage) {
            return;
        }

        const nextSearchParams = new URLSearchParams(searchParams);
        nextSearchParams.set("page", String(clampedPage));
        setSearchParams(nextSearchParams, {
            replace: true,
        });
    }, [
        currentPage,
        eventsQuery.error,
        eventsQuery.isPending,
        searchParams,
        setSearchParams,
        totalPages,
    ]);

    const updatePage = (page: number) => {
        const nextSearchParams = new URLSearchParams(searchParams);
        nextSearchParams.set("page", String(page));
        setSearchParams(nextSearchParams);
    };

    const deleteArchive = () => {
        if (
            !window.confirm(
                "Delete export archive? Event data will not be deleted.",
            )
        ) {
            return;
        }

        deleteExportMutation.mutate({});
    };

    return (
        <ProvideMultiModalContext context={modalContext}>
            <Page>
                <Flex direction="column" width="full" alignItems="center">
                    <Flex
                        direction="column"
                        width="full"
                        maxW="breakpoint-xl"
                        gap="md"
                    >
                        <Flex
                            width="full"
                            alignItems="flex-start"
                            justifyContent="flex-end"
                            gap="sm"
                            flexWrap="wrap"
                        >
                            <ExportArchiveButton
                                status={exportStatus}
                                isStatusPending={exportStatusQuery.isPending}
                                isCreatePending={createExportMutation.isPending}
                                isDeletePending={deleteExportMutation.isPending}
                                onCreate={() => createExportMutation.mutate({})}
                            />
                            <Button
                                type="button"
                                variant="ghost"
                                icon={ReloadIcon}
                                label={
                                    eventsQuery.isFetching
                                        ? "Refreshing..."
                                        : "Refresh"
                                }
                                disabled={eventsQuery.isFetching}
                                onClick={() => {
                                    eventsQuery.refetch();
                                }}
                            />
                        </Flex>

                        {exportStatusQuery.error ? (
                            <Alert
                                variant="light"
                                colorVariant="error"
                                icon={WarningIcon}
                                title="Unable to load export status"
                                description={exportStatusQuery.error.message}
                            />
                        ) : null}

                        {createExportMutation.error ? (
                            <Alert
                                variant="light"
                                colorVariant="error"
                                icon={WarningIcon}
                                title="Unable to start export"
                                description={createExportMutation.error.message}
                            />
                        ) : null}

                        {deleteExportMutation.error ? (
                            <Alert
                                variant="light"
                                colorVariant="error"
                                icon={WarningIcon}
                                title="Unable to delete export archive"
                                description={deleteExportMutation.error.message}
                            />
                        ) : null}

                        {exportStatus ? (
                            <ArchiveStatusPanel
                                status={exportStatus}
                                isDeletePending={deleteExportMutation.isPending}
                                onDelete={deleteArchive}
                            />
                        ) : null}

                        {eventsQuery.isPending ? (
                            <Card fullWidth>
                                <Flex
                                    direction="column"
                                    alignItems="center"
                                    justifyContent="center"
                                    gap="sm"
                                    py="xl"
                                >
                                    <CircleLoader />
                                    <NormalText text="Loading events..." />
                                </Flex>
                            </Card>
                        ) : null}

                        {!eventsQuery.isPending && eventsQuery.error ? (
                            <Alert
                                variant="light"
                                colorVariant="error"
                                icon={WarningIcon}
                                title="Unable to load events"
                                description={eventsQuery.error.message}
                                actions={
                                    <Button
                                        type="button"
                                        variant="outline"
                                        icon={ReloadIcon}
                                        label="Try again"
                                        onClick={() => {
                                            eventsQuery.refetch();
                                        }}
                                    />
                                }
                            />
                        ) : null}

                        {!eventsQuery.isPending &&
                        !eventsQuery.error &&
                        !isOutOfRangePage &&
                        events.length === 0 &&
                        currentPage === 1 ? (
                            <Card fullWidth>
                                <EmptyView
                                    icon={EventsIcon}
                                    title="No measurement events yet"
                                    subtitle="Successful and failed box measurements will appear here."
                                    py="xl"
                                />
                            </Card>
                        ) : null}

                        {!eventsQuery.isPending &&
                        !eventsQuery.error &&
                        !isOutOfRangePage &&
                        events.length === 0 &&
                        currentPage > 1 ? (
                            <Card fullWidth>
                                <EmptyView
                                    icon={EventsIcon}
                                    title={`No events on page ${currentPage}`}
                                    subtitle="Try an earlier page or refresh to load the latest events."
                                    py="xl"
                                />
                            </Card>
                        ) : null}

                        {!eventsQuery.isPending &&
                        !eventsQuery.error &&
                        !isOutOfRangePage &&
                        events.length > 0 ? (
                            <Grid
                                gap="md"
                                columns={{
                                    base: 1,
                                    lg: 2,
                                }}
                            >
                                {events.map((event) => (
                                    <EventCard
                                        key={event.id}
                                        event={event}
                                        onClick={() => {
                                            modalContext.open(
                                                "eventVideo",
                                                event,
                                            );
                                        }}
                                        onDelete={() => {
                                            deleteEventMutation.mutate({
                                                id: event.id,
                                            });
                                        }}
                                        isDeleting={
                                            deleteEventMutation.isPending &&
                                            deleteEventMutation.variables
                                                ?.id === event.id
                                        }
                                        isDeleteDisabled={isExportPreparing}
                                    />
                                ))}
                            </Grid>
                        ) : null}

                        {shouldShowPagination ? (
                            <EventsPagination
                                page={currentPage}
                                totalPages={totalPages}
                                isDisabled={eventsQuery.isFetching}
                                onPageChange={updatePage}
                            />
                        ) : null}
                    </Flex>
                </Flex>
            </Page>

            <EventVideoModal />
        </ProvideMultiModalContext>
    );
}

export default EventsPage;
