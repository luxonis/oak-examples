// src/components/LuxonisStream.tsx
import React from "react";
import { Streams } from "@luxonis/depthai-viewer-common";
import { css } from "../../styled-system/css/css.mjs";

// the viewer component isn’t always nicely typed for custom props
// const PatchedStreams = Streams as unknown as React.ComponentType<any>;

interface LuxonisStreamProps {
  title: string;
  caption?: string;
  defaultTopics: string[];
  allowedTopics: string[];
  // for your case: low_res_image uses detections, others don’t
  topicGroups?: Record<string, string>;
  hideToolbar?: boolean;
  connected?: boolean;
}

const LuxonisStream: React.FC<LuxonisStreamProps> = ({
  title,
  caption,
  defaultTopics,
  allowedTopics,
  topicGroups = {},
}) => {
  return (
    <section className={css({
      flex: 1,
      bg: 'white',
      borderRadius: 'xl',
      p: '3',
      display: 'flex',
      flexDirection: 'column',
      gap: '2',
      boxShadow: 'lg',
      minHeight: '72',
    })}>
      <h2 className={css({ fontWeight: 'semibold', fontSize: 'md', mb: '1' })}>
        {title}
      </h2>
      {/* Caption (optional) */}
      {caption && (
        <p className={css({ fontSize: 'sm', color: 'gray.600', mb: '2' })}>
          {caption}
        </p>
      )}
      <div className={css({ flex: 1, minHeight: '80', pointerEvents: 'none' })}>
        <Streams
          topicGroups={topicGroups}
          defaultTopics={defaultTopics}
          allowedTopics={allowedTopics}
          hideToolbar
        />
      </div>
    </section>
  );
};

export default LuxonisStream;