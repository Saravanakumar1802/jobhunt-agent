import { memo } from "react";
import { Bookmark, BookmarkCheck, Building2, CalendarClock, ExternalLink, MapPin, PenLine, Sparkles } from "lucide-react";
import ScoreRing from "../ui/ScoreRing";
import { WORK_TYPE_LABEL, initials, publisherKind, shortDate, timeAgo } from "../../utils/format";

const MAX_MISSING = 6;
const prettyType = (t) => t.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

const PUBLISHER_STYLE = {
  linkedin: "bg-[#0a66c2] text-white",
  naukri: "bg-[#e6f0ff] text-[#1f5fbf]",
  other: "chip-neutral",
};

function JobCard({ item, onDraft, onTrack, tracked, rank }) {
  const { job, match } = item;
  const kind = publisherKind(job.publisher);
  const posted = timeAgo(job.posted_at);
  const closes = shortDate(job.closes_at);

  return (
    <article className="surface scroll-in group relative p-4 transition-[border-color,box-shadow] duration-300 hover:border-line-strong hover:shadow-[0_18px_40px_-24px_rgb(11_14_20/0.35)] sm:p-6"
      data-testid="job-card">
      <div className="flex gap-4">
        <div className="relative grid size-12 shrink-0 place-items-center overflow-hidden rounded-[14px] border border-line bg-mist font-semiwide font-bold text-ink-600">
          {job.company_logo ? (
            <img src={job.company_logo} alt="" className="size-full object-contain p-1.5" loading="lazy"
              onError={(e) => (e.currentTarget.style.display = "none")} />
          ) : (
            initials(job.company)
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            {rank != null && <span className="mr-1 text-xs font-bold tabular-nums text-ink-400">#{rank}</span>}
            <span className={`chip ${PUBLISHER_STYLE[kind]}`}>{job.publisher || job.source}</span>
            {job.work_type !== "unknown" && <span className="chip chip-soft">{WORK_TYPE_LABEL[job.work_type]}</span>}
            {job.job_type && <span className="chip chip-neutral">{prettyType(job.job_type)}</span>}
          </div>
          <h3 className="font-semiwide mt-2 text-lg font-bold leading-snug sm:text-xl">{job.title}</h3>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-500">
            <span className="inline-flex items-center gap-1.5"><Building2 size={14} aria-hidden />{job.company || "Company not listed"}</span>
            {job.location && <span className="inline-flex items-center gap-1.5"><MapPin size={14} aria-hidden />{job.location}</span>}
            {(posted || closes) && (
              <span className="inline-flex items-center gap-1.5">
                <CalendarClock size={14} aria-hidden />
                {posted && `Posted ${posted}`}
                {closes && <span className="font-medium text-warn-700">{posted ? ", " : ""}closes {closes}</span>}
              </span>
            )}
          </p>
        </div>

        <ScoreRing score={match.score} />
      </div>

      <div className="mt-5 space-y-2.5 sm:pl-16">
        {match.matched_skills.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 w-16 text-xs font-semibold text-ink-500">You have</span>
            {match.matched_skills.map((s) => <span key={s} className="chip chip-match">{s}</span>)}
          </div>
        )}
        {match.missing_skills.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 w-16 text-xs font-semibold text-ink-500">Missing</span>
            {match.missing_skills.slice(0, MAX_MISSING).map((s) => <span key={s} className="chip chip-miss">{s}</span>)}
            {match.missing_skills.length > MAX_MISSING && (
              <span className="text-xs text-ink-500" title={match.missing_skills.slice(MAX_MISSING).join(", ")}>
                +{match.missing_skills.length - MAX_MISSING} more
              </span>
            )}
          </div>
        )}
        {match.reasoning && (
          <p className="flex gap-2 rounded-xl bg-mist px-3.5 py-2.5 text-sm leading-relaxed text-ink-600">
            <Sparkles size={15} className="mt-0.5 shrink-0 text-signal-500" aria-hidden />
            {match.reasoning}
          </p>
        )}
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2 sm:pl-16">
        {job.apply_url && (
          <a href={job.apply_url} target="_blank" rel="noopener noreferrer" className="btn btn-ink px-4 py-2 text-sm">
            Apply <ExternalLink size={14} aria-hidden />
          </a>
        )}
        <button type="button" className="btn btn-signal px-4 py-2 text-sm" onClick={() => onDraft(item)}>
          <PenLine size={14} aria-hidden /> Draft HR message
        </button>
        <button type="button" className="btn btn-quiet px-4 py-2 text-sm" onClick={() => onTrack(item)} disabled={tracked}>
          {tracked ? <BookmarkCheck size={14} aria-hidden /> : <Bookmark size={14} aria-hidden />}
          {tracked ? "Saved" : "Save"}
        </button>
        {job.company_url && (
          <a href={job.company_url} target="_blank" rel="noopener noreferrer" className="btn btn-plain px-3 py-2 text-sm">
            Company site
          </a>
        )}
        {job.attribution && <span className="ml-auto text-xs text-ink-400">{job.attribution}</span>}
      </div>
    </article>
  );
}

export default memo(JobCard);
