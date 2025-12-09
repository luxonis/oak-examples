// FaceMetaBar.tsx
import { css } from "../styled-system/css/css.mjs";
import type { FaceMeta } from "./useFacePoll_load";

const EMOJI: Record<Exclude<FaceMeta["emotion"], undefined>, string> = {
  Happiness: "😁", Anger: "😠", Neutral: "😐", Sadness: "🙁",
  Surprise: "😮", Fear: "😨", Disgust: "🤢", Contempt: "😒",
};

const barStyle = css({
  backgroundColor: "white",
  borderTop: "1px solid",
  borderColor: "gray.300",
  fontSize: "sm",          // <- shared font
  lineHeight: "tight",
  padding: "2",
});

export function FaceMetaBar({ face }: { face?: FaceMeta }) {
  if (!face) return <div className={barStyle}/>;

  const statusText =
    face.status === "NEW"  ? "new person" :
    face.status === "REID" ? "re-identified" :
    face.status === "TBD"  ? "deciding…" : "";

  const line1 = face.id != null ? `ID: ${face.id}${statusText ? `, ${statusText}` : ""}` : "";

  const left = face.gender && face.age != null ? `${face.gender} (${face.age})`
             : face.gender ? face.gender
             : face.age != null ? `(${face.age})` : "";
  const right = face.emotion ? `${EMOJI[face.emotion]} ${face.emotion}` : "";
  const line2 = left && right ? `${left}, ${right}` : (left || right || "");

  return (
    <div className={barStyle}>
      {line1 && <div>{line1}</div>}
      {line2 && <div>{line2}</div>}
    </div>
  );
}
