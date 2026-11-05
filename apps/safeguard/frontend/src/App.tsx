import {
    Alert, Button, Card, CircleLoader, EmptyView, EventsIcon, Flex,
    Grid, ProvideMultiModalContext,
    useNewMultiModalContext,
} from "@luxonis/common-fe-components";
import { Streams, useDaiConnection } from "@luxonis/depthai-viewer-common";
import { useEffect, useRef, useState } from "react";
import "./App.css";
import { EventCard } from "./events/EventCard";
import { EventVideoModal, type EventsModalContext } from "./events/EventVideoModal";
import { useEvents } from "./events/useEvents";
import SettingsForm from "./settings/SettingsForm";

const STREAM_PANEL_ORDER = ["danger", "color", "grid", "grid_annotations", "pcl"];
const getStreamPanelOrder = (topicName: string) => {
    const order = STREAM_PANEL_ORDER.indexOf(topicName);
    return order === -1 ? Number.MAX_SAFE_INTEGER : order;
};

function LiveStreams() {
    const { connected, topics, toggleTopic } = useDaiConnection();
    const opened = useRef(false);

    useEffect(() => {
        const color = topics.find(topic => topic.name === "color");
        if (!connected || !color) {
            opened.current = false;
            return;
        }
        if (color.enabled) {
            opened.current = true;
        } else if (!opened.current) {
            opened.current = true;
            toggleTopic("color");
        }
    }, [connected, topics, toggleTopic]);

    return (
        <Streams
            topicGroups={{ color: "preview", danger: "preview", grid: "grid", grid_annotations: "grid", pcl: "pcl" }}
            numberOfColumns={1}
            topicSortingFunction={(a, b) => getStreamPanelOrder(a.name) - getStreamPanelOrder(b.name)}
        />
    );
}

function RecentEvents() {
    const modalContext = useNewMultiModalContext<EventsModalContext>();
    const [visibleCount, setVisibleCount] = useState(8);
    const { eventsQuery } = useEvents({ limit: visibleCount });
    const events = eventsQuery.data?.events ?? [];
    const totalCount = eventsQuery.data?.total_count ?? 0;
    return (
        <ProvideMultiModalContext context={modalContext}>
            <section className="recent-events">
                <div className="recent-events-heading">
                    <h2>Recent events</h2>
                    <p>Warning and danger captures are kept only while this app is running. Select an event to inspect its video.</p>
                </div>
                {eventsQuery.isPending && <Card fullWidth cardStyles="safeguard-event-card"><Flex justifyContent="center" p="md"><CircleLoader /></Flex></Card>}
                {eventsQuery.error && <Alert variant="light" colorVariant="error" title="Unable to load events" description={eventsQuery.error.message} />}
                {!eventsQuery.isPending && !eventsQuery.error && events.length === 0 &&
                    <Card fullWidth cardStyles="safeguard-event-card"><EmptyView icon={EventsIcon} title="No events yet" subtitle="Warning and danger events will appear here." py="lg" /></Card>}
                {events.length > 0 &&
                    <Grid gap="md" columns={{ base: 1, md: 2 }}>
                        {events.map(event =>
                            <EventCard key={event.id} event={event} onClick={() => modalContext.open("eventVideo", event)} />)}
                    </Grid>}
                {totalCount > visibleCount &&
                    <Button type="button" variant="outline" label={`Show more (${totalCount - visibleCount} remaining)`}
                        onClick={() => setVisibleCount(count => count + 8)} />}
            </section>
            <EventVideoModal />
        </ProvideMultiModalContext>
    );
}

function App() {
    return (
        <main className="safeguard-layout">
            <section className="safeguard-main">
                <div className="safeguard-viewer">
                    <header className="safeguard-viewer-topbar">
                        <img src="logo.svg" alt="Luxonis" />
                        <span>Live camera + alerts</span>
                    </header>
                    <div className="stream-container">
                        <LiveStreams />
                    </div>
                </div>
                <RecentEvents />
            </section>
            <div className="safeguard-divider" aria-hidden="true" />
            <aside className="safeguard-controls">
                <header className="safeguard-intro">
                    <h1>SafeGuard</h1>
                    <p>Live proximity monitoring with person segmentation, stereo depth and IMU gravity alignment. The optional generic object path detects obstacles above the ground plane.</p>
                </header>
                <SettingsForm />
            </aside>
        </main>
    );
}

export default App;
