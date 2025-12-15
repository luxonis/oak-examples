// App.tsx
import {css} from "../styled-system/css/css.mjs";
import {Streams, useNavigation} from "@luxonis/depthai-viewer-common";
import {FaceMetaBar} from "./FaceMetaBar";
import {useFacesPoll} from "./useFacePoll_load";
import {StatsBanner} from "./StatsBanner";
import {TopBar} from "./TopBar";
import React, {useMemo} from "react";

const borderByStatus = (s?: string) =>
    s === "NEW" ? "#0d6efd" :   // blue
        s === "REID" ? "#28a745" :   // green
            s === "TBD" ? "#dc3545" :   // red
                "#ced4da";    // gray fallback

const LeftVideo: React.FC = React.memo(() => {
    const leftGroups = useMemo(() => ({Video: "images", Annotations: 'images'}), []);
    const leftAllowed = useMemo(() => ["Video"], []);
    const {stats} = useFacesPoll();

    return (
        <div className={css({
            flex: 1, display: "flex", flexDirection: "column",
            minWidth: 0, minHeight: 0, borderRadius: "md", overflow: "hidden",
            borderWidth: "1px", borderColor: "gray.300", backgroundColor: "white",
        })}>
            <TopBar/>
            <StatsBanner stats={stats}/>
            <div className={css({position: "relative", flex: 1, minHeight: 0})}>
                <Streams
                    allowedTopics={leftAllowed}
                    defaultTopics={leftAllowed}
                    topicGroups={leftGroups}
                    hideToolbar
                />
            </div>
        </div>
    );
});

const ImgBox: React.FC<{ url?: string }> = ({url}) => {
    const {makePath} = useNavigation();
    const placeholder = useMemo(
        () => makePath("placeholders/empty.jpg", {noSearch: true}),
        [makePath],
    );

    return (
        <div
            className={css({
                position: "relative", flex: 1, minHeight: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
                backgroundColor: "white",
            })}
        >
            <img
                src={url ?? placeholder}
                alt=""
                draggable={false}
                style={{maxWidth: "100%", maxHeight: "100%", objectFit: "contain"}}
            />
        </div>
    );
};

const CropsWithBars: React.FC = () => {
    const {faces} = useFacesPoll();
    return (
        <div
            className={css({
                width: "300px", minWidth: "300px", flexShrink: 0,
                display: "flex", flexDirection: "column", gap: "md",
            })}
        >
            {[0, 1, 2].map(i => {
                const face = faces[i];
                return (
                    <div key={i}
                         className={tileStyle}
                         style={{borderColor: borderByStatus(face?.status)}}
                    >
                        <ImgBox url={face?.img_url}/>
                        <FaceMetaBar face={face}/>
                    </div>
                );
            })}
        </div>
    );
};

export default function App() {
    return (
        <main className={css({width: "screen", height: "screen", display: "flex", gap: "md", padding: "md"})}>
            <LeftVideo/>
            <CropsWithBars/>
        </main>
    );
}

const tileStyle = css({
    borderRadius: "md",
    overflow: "hidden",
    borderWidth: "8px", // thicker to show color clearly
    borderColor: "gray.300",
    backgroundColor: "white",
    minHeight: "180px",
    flex: 1,
    display: "flex",
    flexDirection: "column",
});