import { Streams, useDaiConnection } from "@luxonis/depthai-viewer-common";
import { useEffect, useRef } from "react";
import "./App.css";
import SettingsForm from "./settings/SettingsForm";

const STREAM_PANEL_ORDER = ["danger", "color", "obstacle_annotations", "grid", "grid_annotations", "pcl"];
const DEFAULT_TOPICS = new Set(STREAM_PANEL_ORDER);
const getStreamPanelOrder = (topicName: string) => {
    const order = STREAM_PANEL_ORDER.indexOf(topicName);
    return order === -1 ? Number.MAX_SAFE_INTEGER : order;
};

function LiveStreams() {
    const { connected, topics, toggleTopic } = useDaiConnection();
    const opened = useRef(new Set<string>());

    useEffect(() => {
        if (!connected) {
            opened.current.clear();
            return;
        }
        for (const topic of topics) {
            if (!DEFAULT_TOPICS.has(topic.name) || opened.current.has(topic.name)) continue;
            opened.current.add(topic.name);
            if (!topic.enabled) toggleTopic(topic.name);
        }
    }, [connected, topics, toggleTopic]);

    return (
        <Streams
            topicGroups={{ color: "preview", danger: "preview", obstacle_annotations: "preview", grid: "grid", grid_annotations: "grid", pcl: "pcl" }}
            numberOfColumns={2}
            topicSortingFunction={(a, b) => getStreamPanelOrder(a.name) - getStreamPanelOrder(b.name)}
        />
    );
}

function App() {
    return (
        <main className="safeguard-layout">
            <section className="safeguard-main">
                <div className="safeguard-viewer">
                    <header className="safeguard-viewer-topbar">
                        <img src="logo.svg" alt="Luxonis" />
                        <span>Live camera, ground plane, and proximity alerts</span>
                    </header>
                    <div className="stream-container">
                        <LiveStreams />
                    </div>
                    <p className="stream-legend">Point cloud: green = ground, orange = warning zone, red = danger zone. Camera boxes mark detected obstacles.</p>
                </div>
            </section>
            <div className="safeguard-divider" aria-hidden="true" />
            <aside className="safeguard-controls">
                <header className="safeguard-intro">
                    <h1>SafeGuard</h1>
                    <p>Live proximity monitoring with person segmentation, automatic depth selection and IMU gravity alignment. The optional generic object path detects obstacles above the ground plane.</p>
                </header>
                <SettingsForm />
            </aside>
        </main>
    );
}

export default App;
