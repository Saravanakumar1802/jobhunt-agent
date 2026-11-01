/**
 * A scripted replay of a real search, fed through the same reducer and AgentThread the app uses.
 * Starts when scrolled into view; the timings mirror a typical run on the free models.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { RotateCcw } from "lucide-react";
import AgentThread from "./AgentThread";
import ScoreRing from "../ui/ScoreRing";
import { reduceProgress, STAGES } from "../../hooks/useSearchStream";

const SCRIPT = [
  [250, { stage: "search", message: "Searching live jobs for “MERN Stack Developer”…" }],
  [1000, { stage: "search", message: "Asking JSearch for LinkedIn and Naukri postings…" }],
  [1800, { stage: "search", message: "Found 47 jobs via JSearch", done: true, count: 47 }],
  [2100, { stage: "prefilter", message: "Scoring 47 jobs locally (no LLM)…" }],
  [2600, { stage: "prefilter", message: "Kept top 12 of 47 candidates", done: true, count: 12 }],
  [2900, { stage: "analyzer", message: "Reading 12 job descriptions (3 cached)…", total: 12, progress: 3 }],
  [3700, { stage: "analyzer", message: "Extracting required skills…", total: 12, progress: 7 }],
  [4500, { stage: "analyzer", message: "Analyzed 12 jobs (9 by LLM, 3 from cache)", done: true, total: 12, progress: 12 }],
  [4800, { stage: "matcher", message: "Scoring your fit for 12 jobs…", total: 12, progress: 0 }],
  [5500, { stage: "matcher", message: "Judging seniority and domain fit…", total: 12, progress: 8 }],
  [6200, { stage: "matcher", message: "Scored 12 jobs", done: true, total: 12, progress: 12 }],
  [6500, { stage: "ranker", message: "Ranked 9 jobs (3 below your min score)", done: true, count: 9 }],
];
const END = 6800;
const empty = () => Object.fromEntries(STAGES.map((s) => [s, { status: "waiting" }]));

export default function DemoThread() {
  const root = useRef(null);
  const timers = useRef([]);
  const [run, setRun] = useState(() => ({ id: 0, startedAt: performance.now(), status: "idle", stages: empty(), log: [] }));

  const play = useCallback(() => {
    timers.current.forEach(clearTimeout);
    const startedAt = performance.now();
    setRun((r) => ({ id: r.id + 1, startedAt, status: "running", stages: empty(), log: [] }));
    timers.current = SCRIPT.map(([t, evt]) =>
      setTimeout(() => setRun((r) => ({ ...r, stages: reduceProgress(r.stages, evt), log: [...r.log, { ...evt, t }] })), t),
    );
    timers.current.push(setTimeout(() => setRun((r) => ({ ...r, status: "done" })), END));
  }, []);

  useEffect(() => {
    const el = root.current;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) {
        play();
        io.disconnect();
      }
    }, { threshold: 0.4 });
    io.observe(el);
    return () => {
      io.disconnect();
      timers.current.forEach(clearTimeout);
    };
  }, [play]);

  return (
    <div ref={root} className="space-y-5">
      <div className="ml-auto max-w-[85%] rounded-[22px] rounded-br-md bg-ink-950 px-5 py-4 text-white">
        <p className="font-semiwide font-bold">MERN Stack Developer<span className="font-normal text-white/60">, 2 yrs</span></p>
        <p className="mt-1 text-sm text-white/75">react, node.js, express, mongodb, python, fastapi</p>
      </div>
      <AgentThread key={run.id} stages={run.stages} log={run.log} status={run.status === "idle" ? "running" : run.status}
        startedAt={run.startedAt} elapsedMs={run.status === "done" ? END : undefined} />
      {run.status === "done" && (
        <div className="rise-in surface flex items-center gap-4 p-4 sm:ml-[50px]">
          <ScoreRing score={91} size={56} />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-ink-500">Top match, via LinkedIn</p>
            <p className="font-semiwide truncate font-bold">MERN Stack Developer at Nimbus Labs</p>
            <p className="mt-1 flex flex-wrap gap-1.5">
              {["react", "node.js", "mongodb"].map((s) => <span key={s} className="chip chip-match">{s}</span>)}
              <span className="chip chip-miss">aws</span>
            </p>
          </div>
          <button type="button" className="btn btn-quiet hidden px-3.5 py-2 text-sm sm:inline-flex" onClick={play}>
            <RotateCcw size={14} aria-hidden /> Replay
          </button>
        </div>
      )}
    </div>
  );
}
