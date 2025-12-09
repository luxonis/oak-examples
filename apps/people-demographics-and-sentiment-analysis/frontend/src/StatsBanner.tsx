import { css } from "../styled-system/css/css.mjs";
import type { FaceStats, EmotionName } from "./useFacePoll_load";

const EMOJI: Record<EmotionName, string> = {
  Happiness: "😁",
  Neutral:   "😐",
  Surprise:  "😮",
  Anger:     "😠",
  Sadness:   "🙁",
  Fear:      "😨",
  Disgust:   "🤢",
  Contempt:  "😒",
};

const bar = css({
  display: "flex",
  flexWrap: "wrap",                     
  gap: "clamp(6px, 1.2vw, 28px)",       
  padding: "8px clamp(8px, 1.5vw, 16px)",
  background: "linear-gradient(180deg, rgba(255,255,255,0.95), rgba(255,255,255,0.75))",
  borderBottom: "1px solid #ddd",
});

const col = css({
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  flex: "0 1 clamp(52px, 6.5vw, 72px)", 
  textAlign: "center",
});

const ageCol = css({
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  flex: "0 1 clamp(70px, 10vw, 120px)", 
});

const pct   = css({ fontSize: "clamp(12px, 1.6vw, 22px)", fontWeight: 700, lineHeight: 1 });
const label = css({ fontSize: "clamp(11px, 1.4vw, 18px)", fontWeight: 700, lineHeight: 1.1, opacity: 0.9 });
const emoji = css({ fontSize: "clamp(18px, 2vw, 28px)", lineHeight: 1 });
const icon  = css({ width: "clamp(20px, 2.2vw, 28px)", height: "clamp(20px, 2.2vw, 28px)" });

const vsep = css({
  width: "1px",
  alignSelf: "stretch",
  background: "#d0d0d0",
  display: { base: "none", md: "block" },
});

export function StatsBanner({ stats }: { stats?: FaceStats }) {
  if (!stats) return null;
  const e = stats.emotions ?? {};
  const order = Object.keys(EMOJI) as EmotionName[];

  return (
    <div className={bar}>
      <div className={ageCol}>
        <div className={label}>Average Age</div>
        <div className={pct}>{stats.age.toFixed(1)}</div>
      </div>

      <div className={vsep} />

      <div className={col}>
        <div className={pct} style={{ color: "#299FE9" }}>{stats.males.toFixed(1)}%</div>
        <img className={icon} src="icons/male.png" alt="Male" />
      </div>

      <div className={col}>
        <div className={pct} style={{ color: "#F32C7D" }}>{stats.females.toFixed(1)}%</div>
        <img className={icon} src="icons/female.png" alt="Female" />
      </div>

      <div className={vsep} />

      {order.map((name) => (
        <div key={name} className={col}>
          <div className={pct}>{(e[name] ?? 0).toFixed(1)}%</div>
          <div className={emoji}>{EMOJI[name]}</div>
        </div>
      ))}
    </div>
  );
}
