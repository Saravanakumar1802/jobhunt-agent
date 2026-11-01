/**
 * Search, laid out like a chat: compose a brief, then watch the thread unfold.
 * Your brief becomes a message, the copilot's trace streams under it, and the
 * ranked jobs arrive as its reply.
 */
import { lazy, Suspense, useCallback, useMemo, useState } from "react";
import { ArrowLeft, RefreshCw, Square } from "lucide-react";
import Composer, { EMPTY_PROFILE, toForm } from "../components/search/Composer";
import AgentThread from "../components/agent/AgentThread";
import JobCard from "../components/jobs/JobCard";
import OutreachDialog from "../components/outreach/OutreachDialog";
import Segmented from "../components/ui/Segmented";
import { useToast } from "../components/ui/Toast";
import { useAuth } from "../context/AuthContext";
import { useSaveProfile, useTrackJob, useTracker } from "../hooks/queries";
import { useSearchStream } from "../hooks/useSearchStream";
import { DEFAULT_FILTERS, describeFilters } from "../utils/format";

const GlassCards = lazy(() => import("../components/three/GlassCards"));
const FILTERS_KEY = "jhc.filters";

function loadFilters() {
  try {
    return { ...DEFAULT_FILTERS, ...JSON.parse(localStorage.getItem(FILTERS_KEY) || "{}") };
  } catch {
    return DEFAULT_FILTERS;
  }
}

function saveFilters(f) {
  try {
    localStorage.setItem(FILTERS_KEY, JSON.stringify(f));
  } catch {
    /* per-viewer convenience only */
  }
}

const SORTS = [
  { value: "priority", label: "LinkedIn first" },
  { value: "score", label: "Best match" },
];

export function sortResults(items, mode) {
  if (!items) return [];
  if (mode === "score") return [...items].sort((a, b) => b.match.score - a.match.score);
  return items; // backend already ranks LinkedIn → Naukri → others, then by score
}

function greeting(name) {
  const h = new Date().getHours();
  const part = h < 5 ? "Working late" : h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
  return `${part}${name ? `, ${name.split(" ")[0]}` : ""}.`;
}

function BriefBubble({ profile, filters }) {
  const shown = profile.skills.slice(0, 8);
  return (
    <div className="rise-in ml-auto max-w-[88%] rounded-[22px] rounded-br-md bg-ink-950 px-5 py-4 text-white sm:max-w-[80%]">
      <p className="font-semiwide font-bold">
        {profile.target_role}
        {profile.years_experience !== "" && <span className="font-normal text-white/60">, {profile.years_experience} yrs</span>}
      </p>
      <p className="mt-1 text-sm text-white/75">
        {shown.join(", ")}{profile.skills.length > shown.length && ` and ${profile.skills.length - shown.length} more`}
      </p>
      <p className="mt-2 text-xs text-white/50">{describeFilters(filters)}</p>
    </div>
  );
}

function ResultsLead({ meta, count, sort }) {
  if (!meta) return null;
  const source = meta.cached ? "the 6-hour cache, so no API call was used" : meta.demo ? "sample data" : meta.source;
  const model = meta.last_model?.split("/").slice(1).join("/");
  return (
    <div className="space-y-1">
      <p className="text-[1.05rem] leading-relaxed">
        {count === 0 ? "No jobs cleared your minimum score this time." :
          <>Here {count === 1 ? "is your best match" : <>are your <strong>{count} best matches</strong></>}
            {sort === "priority" ? ", with LinkedIn postings first." : ", best fit first."}</>}
      </p>
      <p className="text-sm text-ink-500">
        {meta.fetched} jobs came from {source}.{model && <> Scored with {model}.</>}
        {meta.hidden_below_min > 0 && <> {meta.hidden_below_min} hidden below your minimum.</>}
      </p>
    </div>
  );
}

export default function SearchPage() {
  const toast = useToast();
  const { user } = useAuth();
  const [filters, setFilters] = useState(loadFilters);
  const [profile, setProfile] = useState(EMPTY_PROFILE);
  const [profileId, setProfileId] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [sort, setSort] = useState("priority");
  const [view, setView] = useState("compose");
  const [drafting, setDrafting] = useState(null);
  const search = useSearchStream();
  const saveProfile = useSaveProfile();
  const track = useTrackJob();
  const { data: tracked = [] } = useTracker();
  const trackedIds = useMemo(() => new Set(tracked.map((t) => t.job_id)), [tracked]);

  const onSelectProfile = useCallback((id, form) => {
    setProfileId(id);
    setProfile(form);
    setDirty(false);
  }, []);

  const start = async (forceRefresh = false) => {
    if (!profile.target_role.trim() || profile.skills.length === 0) {
      toast("Add a target role and at least one skill first", "error");
      return;
    }
    saveFilters(filters);
    let id = profileId;
    if (!id || dirty) {
      try {
        const body = { ...profile, years_experience: profile.years_experience === "" ? null : Number(profile.years_experience) };
        const saved = await saveProfile.mutateAsync({ id, ...body });
        id = saved.id;
        onSelectProfile(saved.id, toForm(saved));
      } catch (e) {
        toast(e.message, "error");
        return;
      }
    }
    setView("thread");
    window.scrollTo({ top: 0 });
    search.run({ profile_id: id, filters, force_refresh: forceRefresh });
  };

  const onTrack = useCallback(
    (item, extra = {}) =>
      track.mutate(
        { body: { job_id: item.job.id, status: "saved", ...extra }, profileHash: search.meta?.profile_hash },
        { onSuccess: () => toast(extra.hr_profile_url ? "HR link saved to your tracker" : "Saved to your tracker"),
          onError: (e) => toast(e.message, "error") },
      ),
    [track, search.meta, toast],
  );

  const results = sortResults(search.results, sort);
  const running = search.status === "running";

  return (
    <div className="mx-auto max-w-[52rem]">
      {view === "compose" ? (
        <div className="space-y-6">
          <div className="text-center">
            <Suspense fallback={<div className="h-56 sm:h-64" />}>
              <GlassCards mode="fan" className="mx-auto h-56 w-full max-w-xl sm:h-64" />
            </Suspense>
            <p className="text-ink-500">{greeting(user?.name)}</p>
            <h1 className="font-wide mt-2 text-[clamp(1.9rem,5vw,3rem)] font-bold leading-[1.02]">What role are you hunting for?</h1>
            <p className="mx-auto mt-3 max-w-lg text-ink-500">
              Five agents search live LinkedIn and Naukri postings, score each one against your skills and rank them for you.
            </p>
          </div>
          <Composer form={profile} selectedId={profileId} onSelect={onSelectProfile}
            onChange={(f) => { setProfile(f); setDirty(true); }} filters={filters} onFilters={setFilters}
            onSubmit={() => start(false)} onStop={search.abort} running={running} busy={saveProfile.isPending} />
          {search.status !== "idle" && (
            <p className="text-center">
              <button type="button" className="btn btn-plain text-sm" onClick={() => setView("thread")}>Back to your last results</button>
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-7">
          <div className="flex items-center gap-2">
            <button type="button" className="btn btn-plain -ml-3 px-3 py-2 text-sm" onClick={() => setView("compose")}>
              <ArrowLeft size={16} aria-hidden /> Edit search
            </button>
            {running ? (
              <button type="button" className="btn btn-quiet ml-auto px-4 py-2 text-sm" onClick={search.abort}>
                <Square size={13} aria-hidden className="fill-current" /> Stop
              </button>
            ) : (
              <button type="button" className="btn btn-quiet ml-auto px-4 py-2 text-sm" onClick={() => start(true)}
                title="Fetch fresh jobs (uses 1 API call)">
                <RefreshCw size={14} aria-hidden /> Fetch fresh jobs
              </button>
            )}
          </div>

          <BriefBubble profile={profile} filters={filters} />

          <AgentThread key={search.runInfo.id} stages={search.stages} log={search.log} status={search.status}
            startedAt={search.runInfo.startedAt} elapsedMs={search.meta?.elapsed_ms} />

          <div className="space-y-5 sm:pl-[50px]">
            {search.error && (
              <p role="alert" className="rounded-2xl border border-bad-500/25 bg-bad-50 p-4 text-sm text-bad-700">{search.error}</p>
            )}

            {running && !search.results && (
              <div className="space-y-4" aria-hidden>
                {[0, 1].map((i) => <div key={i} className="skeleton h-48" style={{ animationDelay: `${i * 0.2}s` }} />)}
              </div>
            )}

            {search.results && (
              <>
                {search.meta?.demo && (
                  <p className="rounded-2xl bg-warn-50 p-4 text-sm text-warn-700">
                    Showing sample jobs. Live sources need keys or have used this month's free quota. See Usage for details.
                  </p>
                )}
                {search.meta?.warnings?.map((w) => (
                  <p key={w} className="rounded-2xl bg-signal-50 p-4 text-sm text-signal-700">{w}</p>
                ))}
                <div className="flex flex-wrap items-end justify-between gap-4">
                  <ResultsLead meta={search.meta} count={results.length} sort={sort} />
                  {results.length > 1 && <div className="w-60"><Segmented options={SORTS} value={sort} onChange={setSort} size="sm" /></div>}
                </div>
                {results.length === 0 ? (
                  <p className="surface p-6 text-ink-600">
                    Lower "Hide matches below" in Filters, or widen the date and location, then search again.
                  </p>
                ) : (
                  <div className="space-y-4">
                    {results.map((item, i) => (
                      <div key={item.job.id} className="rise-in" style={{ animationDelay: `${Math.min(i, 8) * 70}ms` }}>
                        <JobCard item={item} rank={i + 1} onDraft={setDrafting} onTrack={onTrack} tracked={trackedIds.has(item.job.id)} />
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      <OutreachDialog key={drafting?.job.id ?? "none"} item={drafting} profileId={profileId} onClose={() => setDrafting(null)}
        onSaveHr={(item, url) => onTrack(item, { hr_profile_url: url })} />
    </div>
  );
}
