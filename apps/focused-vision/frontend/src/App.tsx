// src/App.tsx
import LuxonisStream from "./components/LuxonisStream";
import {
  LOW_RES_DEFAULT_TOPICS,
  LOW_RES_ALLOWED_TOPICS,
  NON_FOCUS_HEAD_CROPS_DEFAULT,
  NON_FOCUS_HEAD_CROPS_ALLOWED,
  FOCUSED_VISION_HEAD_CROPS_DEFAULT,
  FOCUSED_VISION_HEAD_CROPS_ALLOWED,
  LOW_RES_TOPIC_GROUPS,
  FOCUSED_VISION_TILING_HEAD_CROPS_DEFAULT,
  FOCUSED_VISION_TILING_HEAD_CROPS_ALLOWED,
  NON_FOCUSED_TOPIC_GROUPS,
  FOCUSED_TOPIC_GROUPS,
  FOCUSED_TILING_TOPIC_GROUPS,
} from "./constants";
import { css } from "../styled-system/css/css.mjs";

export default function App() {
  return (
    <main
      className={css({
        width: "screen",
        height: "screen",
        display: "flex",
        flexDirection: "row",
        gap: "md",
        padding: "md",
        bg: "gray.50",
          overflowY: "auto",     // vertical scroll when content too tall
        overflowX: "auto",     // horizontal scroll when content too wide
      })}
    >
      {/* LEFT: Streams (2x2 grid) */}
      <div
        className={css({
          flex: 1,
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: "md",
          minHeight: 0,
            flexShrink: 0,
        })}
      >
        <LuxonisStream
          title="RGB Preview"
          topicGroups={LOW_RES_TOPIC_GROUPS}
          defaultTopics={LOW_RES_DEFAULT_TOPICS}
          allowedTopics={LOW_RES_ALLOWED_TOPICS}
        />

        <LuxonisStream
          title="Naive Approach"
          topicGroups={NON_FOCUSED_TOPIC_GROUPS}
          defaultTopics={NON_FOCUS_HEAD_CROPS_DEFAULT}
          allowedTopics={NON_FOCUS_HEAD_CROPS_ALLOWED}
        />

        <LuxonisStream
          title="Focused Vision with NN Model Chaining"
          topicGroups={FOCUSED_TOPIC_GROUPS}
          defaultTopics={FOCUSED_VISION_HEAD_CROPS_DEFAULT}
          allowedTopics={FOCUSED_VISION_HEAD_CROPS_ALLOWED}
        />

        <LuxonisStream
          title="Focused Vision with Tiling"
          topicGroups={FOCUSED_TILING_TOPIC_GROUPS}
          defaultTopics={FOCUSED_VISION_TILING_HEAD_CROPS_DEFAULT}
          allowedTopics={FOCUSED_VISION_TILING_HEAD_CROPS_ALLOWED}
        />
      </div>

      {/* DIVIDER */}
      <div
        className={css({
          width: "2px",
          backgroundColor: "gray.300",
          borderRadius: "full",
        })}
      />

      {/* RIGHT: Sidebar */}
      <aside
        className={css({
          width: "md",
          display: "flex",
          flexDirection: "column",
          gap: "md",
        })}
      >
        <h1 className={css({ fontSize: "2xl", fontWeight: "semibold" })}>
          Focused Vision
        </h1>

        <div className={css({ color: "gray.600", lineHeight: "relaxed" })}>
          <p>
            The goal of Focused Vision is to capture an object of interest in as
            much detail as possible and do all necessary steps on-device.  It excels when the object occupies only a small part of the image
              — whether because it is physically small, relatively far from the camera, or both.
          </p>
          <p>
            This application compares a naive face-detection approach with two
            Focused Vision approaches using person detection and tiling.
          </p>

          <ul
            className={css({
              listStyle: "disc",
              pl: "5",
              mt: "2",
              "& li + li": { mt: "1" },
            })}
          >
            <li>
              <strong>Naive Approach:</strong> detect faces on downscaled
              low-res RGB.
            </li>
            <li>
              <strong>NN Model Chaining:</strong> detect person → crop high-res
              → detect face on the high-res crop.
            </li>
            <li>
              <strong>Tiling:</strong> detect faces on overlapping tiles of the
              high-res image, then merge results.
            </li>
            <li>
              <strong>RGB Preview:</strong> H264 encoded RGB stream.
                Face detections from the naive approach and people detections from the NN model chaining are shown
                in the stream.
            </li>
          </ul>
        </div>
      </aside>
    </main>
  );
}