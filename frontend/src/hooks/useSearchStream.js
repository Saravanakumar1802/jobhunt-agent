/**
 * Runs a streamed search and turns SSE events into UI state.
 *
 * stages: { search|prefilter|analyzer|matcher|ranker: {status, message, progress, total, count} }
 * log:    every progress message in order (the "mission log")
 * status: idle | running | done | error
 * run:    {id, startedAt}, a fresh id per search so views can reset their local state
 */
import { useCallback, useRef, useState } from "react";
import { streamSearch } from "../api/search";

export const STAGES = ["search", "prefilter", "analyzer", "matcher", "ranker"];

const emptyStages = () => Object.fromEntries(STAGES.map((s) => [s, { status: "waiting" }]));

export function reduceProgress(stages, evt) {
  const { stage, message, done, ...rest } = evt;
  if (!STAGES.includes(stage)) return stages;
  const next = { ...stages };
  // Entering a stage completes every earlier one.
  STAGES.slice(0, STAGES.indexOf(stage)).forEach((s) => {
    if (next[s].status !== "done") next[s] = { ...next[s], status: "done" };
  });
  next[stage] = { ...next[stage], ...rest, message, status: done ? "done" : "active" };
  return next;
}

export function useSearchStream() {
  const [stages, setStages] = useState(emptyStages);
  const [log, setLog] = useState([]);
  const [results, setResults] = useState(null);
  const [meta, setMeta] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  const [runInfo, setRunInfo] = useState({ id: 0, startedAt: 0 });
  const controller = useRef(null);

  const run = useCallback(async (body) => {
    controller.current?.abort();
    const ac = new AbortController();
    controller.current = ac;
    setStages(emptyStages());
    setLog([]);
    setResults(null);
    setMeta(null);
    setError(null);
    setStatus("running");
    const started = performance.now();
    setRunInfo((r) => ({ id: r.id + 1, startedAt: started }));

    try {
      await streamSearch(body, {
        signal: ac.signal,
        onEvent: ({ event, data }) => {
          if (event === "progress") {
            setStages((s) => reduceProgress(s, data));
            setLog((l) => [...l, { ...data, t: Math.round(performance.now() - started) }]);
          } else if (event === "result") {
            setStages((s) => Object.fromEntries(STAGES.map((k) => [k, { ...s[k], status: "done" }])));
            setResults(data.jobs);
            setMeta(data.meta);
            setStatus("done");
          } else if (event === "error") {
            setError(data.message);
            setStatus("error");
          }
        },
      });
    } catch (e) {
      if (e.name === "AbortError") return;
      setError(e.message);
      setStatus("error");
    }
  }, []);

  const abort = useCallback(() => {
    controller.current?.abort();
    setStatus((s) => (s === "running" ? "idle" : s));
  }, []);

  return { stages, log, results, meta, status, error, run, abort, setResults, runInfo };
}
