import { useStatus } from "../hooks/queries";

const SOURCE_LABEL = { jsearch: "JSearch (LinkedIn, Naukri)", adzuna: "Adzuna", remotive: "Remotive", arbeitnow: "Arbeitnow" };

function Meter({ used, total }) {
  const pct = total ? Math.min(100, (used / total) * 100) : 0;
  const color = pct > 85 ? "bg-bad-500" : pct > 60 ? "bg-warn-500" : "bg-signal-500";
  return (
    <div className="h-2 overflow-hidden rounded-full bg-mist" role="meter" aria-valuemin={0} aria-valuemax={total} aria-valuenow={used}>
      <div className={`h-full rounded-full ${color} transition-[width] duration-700`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function StatusPage() {
  const { data, isLoading, error } = useStatus();
  if (isLoading) return <div className="skeleton h-96" />;
  if (error) return <p role="alert" className="surface p-5 text-bad-700">{error.message}</p>;

  const { job_sources: sources, llm, searches } = data;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-wide text-[clamp(2rem,4vw,2.8rem)] font-bold">Free-tier usage</h1>
        <p className="mt-2 text-ink-500">
          {data.database === "memory"
            ? "Data is kept in memory until you add a MongoDB Atlas link, so it resets when the backend restarts."
            : "Data is stored in MongoDB Atlas."}
        </p>
      </div>

      <section className="surface scroll-in p-5 sm:p-6" aria-labelledby="src-h">
        <h2 id="src-h" className="text-xl font-bold">Job searches left this month</h2>
        <ul className="mt-5 space-y-5">
          {sources.map((s) => (
            <li key={s.provider}>
              <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-semibold">{SOURCE_LABEL[s.provider] ?? s.provider}</span>
                <span className="text-sm text-ink-500">
                  {s.configured ? <><strong className="font-semiwide text-lg text-ink-950">{s.remaining}</strong> of {s.monthly_quota} left</> : "No key added"}
                </span>
              </div>
              <Meter used={s.monthly_quota - s.remaining} total={s.monthly_quota} />
              {s.configured && s.remaining <= Math.max(5, s.monthly_quota * 0.1) && (
                <p className="mt-1.5 text-xs text-warn-700">Almost used up. Repeat searches still work from the 6-hour cache.</p>
              )}
            </li>
          ))}
        </ul>
      </section>

      <div className="grid gap-4 sm:gap-6 md:grid-cols-3">
        {[
          ["AI calls, last 24 hours", llm.calls_24h],
          ["Tokens, last 24 hours", llm.tokens_24h.toLocaleString()],
          ["Searches served from cache", `${Math.round(searches.cache_hit_rate * 100)}%`],
        ].map(([label, value]) => (
          <div key={label} className="surface scroll-in p-5 sm:p-6">
            <p className="text-sm text-ink-500">{label}</p>
            <p className="mt-2 font-semiwide text-4xl font-bold">{value}</p>
          </div>
        ))}
      </div>

      <section className="surface scroll-in p-5 sm:p-6" aria-labelledby="models-h">
        <h2 id="models-h" className="text-xl font-bold">Which model answered</h2>
        {Object.keys(llm.by_model).length === 0 ? (
          <p className="mt-3 text-ink-500">No AI calls yet in the last 24 hours.</p>
        ) : (
          <div className="-mx-1 mt-4 overflow-x-auto px-1">
            <table className="w-full text-left text-sm">
              <thead className="text-ink-400"><tr><th className="py-2 font-semibold">Model</th><th className="py-2 text-right font-semibold">Calls</th></tr></thead>
              <tbody>
                {Object.entries(llm.by_model).map(([m, n]) => (
                  <tr key={m} className="border-t border-line"><td className="break-all py-2.5 pr-4">{m}</td><td className="py-2.5 text-right tabular-nums">{n}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-4 text-sm text-ink-400">{llm.fallback_calls_24h} calls needed a backup model because the first choice was busy.</p>
      </section>

      <section className="surface scroll-in p-5 sm:p-6" aria-labelledby="recent-h">
        <h2 id="recent-h" className="text-xl font-bold">Recent searches</h2>
        {searches.recent.length === 0 ? (
          <p className="mt-3 text-ink-500">No searches yet.</p>
        ) : (
          <div className="-mx-1 mt-4 overflow-x-auto px-1">
            <table className="w-full min-w-[22rem] text-left text-sm">
              <thead className="text-ink-400">
                <tr><th className="py-2 font-semibold">When</th><th className="py-2 font-semibold">Source</th><th className="py-2 text-right font-semibold">Jobs</th><th className="py-2 text-right font-semibold">Time</th></tr>
              </thead>
              <tbody>
                {searches.recent.map((s, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="py-2.5">{new Date(s.ts).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</td>
                    <td className="py-2.5">{s.cached ? "cache" : s.demo ? "demo" : s.source}</td>
                    <td className="py-2.5 text-right tabular-nums">{s.ranked}/{s.fetched}</td>
                    <td className="py-2.5 text-right tabular-nums">{(s.elapsed_ms / 1000).toFixed(1)}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
