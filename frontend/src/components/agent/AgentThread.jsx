/**
 * The copilot's live reasoning trace, in the style of a chat model's "thinking" block.
 * Each SSE progress event updates its step: the active line shimmers and types out,
 * finished steps get a check and a duration, and every update is kept under "details".
 * While running the trace is open; when finished it folds into a one-line summary.
 */
import { useEffect, useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import { Mark } from "../ui/Logo";
import { STAGES } from "../../hooks/useSearchStream";

export const STEP_INFO = {
  search: { title: "Searching live job boards", idle: "LinkedIn first, then Naukri, then backup sources" },
  prefilter: { title: "Shortlisting by your skills", idle: "Keyword scoring in Python, so no AI tokens are spent" },
  analyzer: { title: "Reading the job descriptions", idle: "Lists what each job really requires" },
  matcher: { title: "Scoring your fit", idle: "Your skills against each job, then a seniority check" },
  ranker: { title: "Ranking the results", idle: "LinkedIn first, best fit on top" },
};

const seconds = (ms) => `${(Math.max(0, ms) / 1000).toFixed(1)}s`;
const reducedMotion = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Types a status line out character by character. Remount (key) to restart. */
function TypeOut({ text, className = "" }) {
  const [n, setN] = useState(() => (reducedMotion() ? text.length : 0));
  useEffect(() => {
    if (n >= text.length) return;
    const id = setTimeout(() => setN((x) => Math.min(text.length, x + 2)), 14);
    return () => clearTimeout(id);
  }, [n, text]);
  return (
    <span className={className}>
      <span aria-hidden>{text.slice(0, n)}</span>
      <span className="sr-only">{text}</span>
    </span>
  );
}

function useNow(running) {
  const [now, setNow] = useState(() => performance.now());
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNow(performance.now()), 100);
    return () => clearInterval(id);
  }, [running]);
  return now;
}

/** Fetched jobs as a grid of tiles; the shortlisted ones light up. */
function Funnel({ total, kept }) {
  const tiles = Math.min(total, 48);
  const lit = Math.max(1, Math.round((kept / Math.max(total, 1)) * tiles));
  return (
    <div className="mt-2.5 flex flex-wrap gap-[3px]" aria-hidden>
      {Array.from({ length: tiles }, (_, i) => (
        <span key={i} className={`h-2.5 w-4 rounded-[3px] transition-colors duration-500 ${i < lit ? "bg-signal-500" : "bg-line"}`}
          style={{ transitionDelay: `${i * 12}ms` }} />
      ))}
    </div>
  );
}

function StepIcon({ status }) {
  if (status === "done")
    return (
      <span className="grid size-6 place-items-center rounded-full bg-ink-950 text-white">
        <Check size={13} strokeWidth={3} />
      </span>
    );
  if (status === "active")
    return (
      <span className="relative grid size-6 place-items-center">
        <span className="size-2 rounded-full bg-signal-500" />
        <svg className="orbit absolute inset-0" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" fill="none" stroke="var(--color-signal-100)" strokeWidth="2.2" />
          <circle cx="12" cy="12" r="10" fill="none" stroke="var(--color-signal-500)" strokeWidth="2.2" strokeDasharray="16 63" strokeLinecap="round" />
        </svg>
      </span>
    );
  return <span className="grid size-6 place-items-center"><span className="size-2.5 rounded-full border-2 border-line-strong" /></span>;
}

function Step({ id, st, entries, duration, last, stages }) {
  const info = STEP_INFO[id];
  const message = entries.at(-1)?.message;
  const active = st.status === "active";
  const done = st.status === "done";

  return (
    <li className="relative flex gap-3.5 pb-5 last:pb-0" aria-current={active ? "step" : undefined}>
      {!last && (
        <span aria-hidden className={`absolute left-[11px] top-7 bottom-0.5 w-0.5 rounded-full transition-colors duration-700 ${done ? "bg-ink-950" : "bg-line"}`} />
      )}
      <StepIcon status={st.status} />
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className={`text-[0.95rem] font-semibold ${st.status === "waiting" ? "text-ink-400" : "text-ink-950"}`}>
            {info.title}
            <span className="sr-only">, {done ? "done" : active ? "in progress" : "waiting"}</span>
          </h3>
          {duration != null && <span className="shrink-0 text-xs tabular-nums text-ink-400">{seconds(duration)}</span>}
        </div>

        <p className="mt-0.5 text-sm leading-relaxed">
          {active && message ? (
            <TypeOut key={message} text={message} className="shimmer-text" />
          ) : (
            <span className={done ? "text-ink-600" : "text-ink-400"}>{message ?? info.idle}</span>
          )}
        </p>

        {active && st.total > 0 && (
          <div className="mt-2.5 flex items-center gap-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-signal-50">
              <div className="h-full rounded-full bg-signal-500 transition-[width] duration-500"
                style={{ width: `${Math.round(((st.progress ?? 0) / st.total) * 100)}%` }} />
            </div>
            <span className="text-xs tabular-nums text-ink-500">{st.progress ?? 0} of {st.total}</span>
          </div>
        )}
        {id === "prefilter" && done && stages.search.count > 0 && <Funnel total={stages.search.count} kept={st.count ?? 0} />}

        {entries.length > 1 && (
          <details className="group mt-2">
            <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded-md text-xs font-medium text-ink-500 hover:text-ink-950 [&::-webkit-details-marker]:hidden">
              {entries.length} updates
              <ChevronDown size={13} className="transition-transform group-open:rotate-180" aria-hidden />
            </summary>
            <ol className="mt-2 space-y-1 border-l-2 border-line pl-3 text-xs text-ink-500">
              {entries.map((e, i) => (
                <li key={i} className="flex gap-2.5"><span className="w-9 shrink-0 tabular-nums text-ink-400">{seconds(e.t)}</span>{e.message}</li>
              ))}
            </ol>
          </details>
        )}
      </div>
    </li>
  );
}

export function summarize(stages, elapsedMs) {
  const fetched = stages.search.count, kept = stages.prefilter.count, scored = stages.matcher.progress;
  if (fetched == null) return `Finished in ${seconds(elapsedMs)}.`;
  const parts = [`Searched ${fetched} live ${fetched === 1 ? "job" : "jobs"}`];
  if (kept != null) parts.push(`shortlisted ${kept}`);
  if (scored != null) parts.push(`scored ${scored === kept ? "them" : scored}`);
  const last = parts.pop();
  return `${parts.join(", ")}${parts.length ? " and " : ""}${last} in ${seconds(elapsedMs)}.`;
}

export default function AgentThread({ stages, log, status, startedAt = 0, elapsedMs }) {
  const running = status === "running";
  const now = useNow(running);
  const [manualOpen, setManualOpen] = useState(null);
  const open = manualOpen ?? running;
  const elapsed = running ? now - startedAt : (elapsedMs ?? log.at(-1)?.t ?? 0);

  const byStage = Object.fromEntries(STAGES.map((s) => [s, log.filter((e) => e.stage === s)]));
  const durationOf = (s, i) => {
    const entries = byStage[s];
    if (!entries.length) return null;
    const start = entries[0].t;
    if (stages[s].status === "active") return running ? now - startedAt - start : null;
    const nextStart = STAGES.slice(i + 1).map((n) => byStage[n][0]?.t).find((t) => t != null);
    return (nextStart ?? elapsed) - start;
  };

  return (
    <section aria-label="What the copilot is doing" className="flex gap-3 sm:gap-4">
      <Mark size={34} busy={running} className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <button type="button" onClick={() => setManualOpen(!open)} aria-expanded={open}
          className="group flex w-full items-center gap-2 rounded-lg py-1.5 text-left">
          <span className="font-semibold">
            {running ? <span className="shimmer-text">Working on your search</span> : status === "done" ? "Search finished" : "Search stopped"}
          </span>
          <span className="text-sm tabular-nums text-ink-400">{seconds(elapsed)}</span>
          <ChevronDown size={16} aria-hidden className={`ml-auto text-ink-400 transition-transform duration-300 group-hover:text-ink-950 ${open ? "rotate-180" : ""}`} />
          <span className="sr-only">{open ? "Hide steps" : "Show steps"}</span>
        </button>

        {!running && status === "done" && <p className="text-[0.95rem] text-ink-600">{summarize(stages, elapsed)}</p>}

        <div className="reveal" data-open={open}>
          <div>
            <ol className="surface mt-3 p-4 sm:p-5" aria-live="polite">
              {STAGES.map((s, i) => (
                <Step key={s} id={s} st={stages[s]} entries={byStage[s]} duration={durationOf(s, i)} last={i === STAGES.length - 1} stages={stages} />
              ))}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
