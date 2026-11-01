import { ExternalLink, Trash2 } from "lucide-react";
import { useTracker, useUntrack, useUpdateTracked } from "../hooks/queries";
import { shortDate } from "../utils/format";

const COLUMNS = [
  { key: "saved", label: "Saved", accent: "bg-signal-500" },
  { key: "applied", label: "Applied", accent: "bg-warn-500" },
  { key: "interview", label: "Interview", accent: "bg-ok-500" },
  { key: "rejected", label: "Rejected", accent: "bg-bad-500" },
];

function TrackedCard({ t }) {
  const update = useUpdateTracked();
  const remove = useUntrack();
  const job = t.job ?? {};
  return (
    <li className="rounded-2xl border border-line bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-bold leading-snug">{job.title}</h3>
          <p className="mt-0.5 text-sm text-ink-500">{job.company}{job.publisher && `, via ${job.publisher}`}</p>
        </div>
        {t.score != null && <span className="font-semiwide text-lg font-bold text-warn-700">{t.score}%</span>}
      </div>
      <label className="sr-only" htmlFor={`st-${t.job_id}`}>Status</label>
      <select id={`st-${t.job_id}`} className="field mt-3 py-1.5 text-sm" value={t.status}
        onChange={(e) => update.mutate({ jobId: t.job_id, status: e.target.value })}>
        {COLUMNS.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
      </select>
      <label className="sr-only" htmlFor={`nt-${t.job_id}`}>Notes</label>
      <textarea id={`nt-${t.job_id}`} rows={2} className="field mt-2 resize-y text-sm" placeholder="Notes"
        defaultValue={t.notes} onBlur={(e) => e.target.value !== t.notes && update.mutate({ jobId: t.job_id, notes: e.target.value })} />
      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
        {job.apply_url && <a className="inline-flex items-center gap-1 text-signal-600 hover:underline" href={job.apply_url} target="_blank" rel="noopener noreferrer">Posting <ExternalLink size={12} aria-hidden /></a>}
        {t.hr_profile_url && <a className="inline-flex items-center gap-1 text-signal-600 hover:underline" href={t.hr_profile_url} target="_blank" rel="noopener noreferrer">HR profile <ExternalLink size={12} aria-hidden /></a>}
        <span className="text-xs text-ink-400">Updated {shortDate(t.updated_at)}</span>
        <button type="button" className="ml-auto rounded-lg p-1.5 text-ink-400 hover:text-bad-500" aria-label={`Remove ${job.title}`}
          onClick={() => remove.mutate(t.job_id)}>
          <Trash2 size={15} />
        </button>
      </div>
    </li>
  );
}

export default function TrackerPage() {
  const { data = [], isLoading } = useTracker();
  return (
    <div>
      <h1 className="font-wide text-[clamp(2rem,4vw,2.8rem)] font-bold">Your applications</h1>
      <p className="mt-2 text-ink-500">Jobs you've saved from search. Change the status as you hear back.</p>
      {isLoading ? (
        <div className="mt-8 grid gap-4 md:grid-cols-4">{COLUMNS.map((c) => <div key={c.key} className="skeleton h-60" />)}</div>
      ) : data.length === 0 ? (
        <div className="surface mt-8 p-10 text-center">
          <h2 className="text-xl font-bold">Nothing saved yet</h2>
          <p className="mt-2 text-ink-500">Run a search and press Save on any job to track it here.</p>
        </div>
      ) : (
        <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {COLUMNS.map((c) => {
            const items = data.filter((t) => t.status === c.key);
            return (
              <section key={c.key} aria-labelledby={`col-${c.key}`} className="surface p-4">
                <h2 id={`col-${c.key}`} className="mb-3 flex items-center gap-2 font-bold">
                  <span className={`size-2.5 rounded-full ${c.accent}`} aria-hidden />
                  {c.label}
                  <span className="ml-auto text-sm font-semibold text-ink-400">{items.length}</span>
                </h2>
                <ul className="space-y-3">{items.map((t) => <TrackedCard key={t.job_id} t={t} />)}</ul>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
