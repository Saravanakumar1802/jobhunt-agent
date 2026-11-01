import { useEffect, useState } from "react";
import { scoreTone } from "../../utils/format";

/** Animated SVG ring: the stroke sweeps to the score once the card mounts. */
export default function ScoreRing({ score, size = 68 }) {
  const [shown, setShown] = useState(0);
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const tone = scoreTone(score);

  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(score));
    return () => cancelAnimationFrame(id);
  }, [score]);

  return (
    <div className="flex shrink-0 flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }} role="img" aria-label={`Match score ${score} out of 100, ${tone.label}`}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--color-line)" strokeWidth="5" fill="none" />
          <circle cx={size / 2} cy={size / 2} r={r} stroke={tone.color} strokeWidth="5" strokeLinecap="round" fill="none"
            strokeDasharray={c} strokeDashoffset={c * (1 - shown / 100)}
            style={{ transition: "stroke-dashoffset 1.2s var(--ease-out-expo)" }} />
        </svg>
        <span className="font-semiwide absolute inset-0 grid place-items-center text-xl font-bold tabular-nums">{score}</span>
      </div>
      <span className="hidden text-[0.7rem] font-semibold sm:block" style={{ color: tone.color }}>{tone.label}</span>
    </div>
  );
}
