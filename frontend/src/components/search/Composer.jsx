/**
 * The search brief, in one composer: role, years and skills up front; filters and the
 * "about you" text fold out underneath. The parent saves the profile right before searching.
 */
import { useEffect, useRef, useState } from "react";
import { ArrowUp, ChevronDown, NotebookPen, SlidersHorizontal, Square, Trash2 } from "lucide-react";
import SkillInput from "../profile/SkillInput";
import FilterPanel from "../filters/FilterPanel";
import { useDeleteProfile, useProfiles, useSkillSuggestions } from "../../hooks/queries";
import { DEFAULT_FILTERS, describeFilters } from "../../utils/format";

export const EMPTY_PROFILE = { name: "My profile", target_role: "", description: "", skills: [], years_experience: "" };

export const toForm = (p) => ({ ...EMPTY_PROFILE, ...p, years_experience: p.years_experience ?? "" });

function Toggle({ open, onClick, icon: Icon, children, controls }) {
  return (
    <button type="button" onClick={onClick} aria-expanded={open} aria-controls={controls}
      className={`btn px-3.5 py-2 text-sm ${open ? "bg-ink-950 text-white" : "btn-quiet"}`}>
      <Icon size={15} aria-hidden /> {children}
      <ChevronDown size={14} aria-hidden className={`transition-transform duration-300 ${open ? "rotate-180" : ""}`} />
    </button>
  );
}

export default function Composer({ form, onChange, selectedId, onSelect, filters, onFilters, onSubmit, onStop, running, busy }) {
  const { data: profiles = [] } = useProfiles();
  const { data: suggestions = [] } = useSkillSuggestions();
  const del = useDeleteProfile();
  const initialised = useRef(false);
  const [panel, setPanel] = useState(null); // "filters" | "about" | null

  // Load the most recent profile the first time profiles arrive, unless the user already has one open
  // (the composer remounts when they come back from the results thread).
  const hasForm = Boolean(selectedId || form.target_role);
  useEffect(() => {
    if (!initialised.current && profiles.length && !hasForm) {
      initialised.current = true;
      onSelect(profiles[0].id, toForm(profiles[0]));
    }
  }, [profiles, onSelect, hasForm]);

  const set = (key) => (e) => onChange({ ...form, [key]: e?.target ? e.target.value : e });
  const changedFilters = Object.keys(DEFAULT_FILTERS).filter((k) => filters[k] !== DEFAULT_FILTERS[k]).length;
  const flip = (p) => setPanel((cur) => (cur === p ? null : p));

  return (
    <form className="composer" onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
      <div className="space-y-4 p-4 sm:p-6">
        {profiles.length > 0 && (
          <div className="flex items-center gap-2">
            <label htmlFor="p-pick" className="sr-only">Saved profile</label>
            <select id="p-pick" className="field w-auto max-w-full py-1.5 pr-8 text-sm font-semibold" value={selectedId ?? "new"}
              onChange={(e) => {
                const p = profiles.find((x) => x.id === e.target.value);
                onSelect(p?.id ?? null, p ? toForm(p) : EMPTY_PROFILE);
              }}>
              {profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              <option value="new">New profile</option>
            </select>
            {selectedId && (
              <button type="button" className="btn btn-plain p-2" aria-label="Delete this profile"
                onClick={() => del.mutate(selectedId, { onSuccess: () => onSelect(null, EMPTY_PROFILE) })}>
                <Trash2 size={15} />
              </button>
            )}
          </div>
        )}

        <div className="grid grid-cols-[1fr_5.5rem] gap-3 sm:grid-cols-[1fr_7rem]">
          <div>
            <label className="label" htmlFor="p-role">Role you want</label>
            <input id="p-role" className="field font-semiwide py-3 text-lg font-semibold sm:text-xl" required
              placeholder="MERN Stack Developer" value={form.target_role} onChange={set("target_role")} autoComplete="off" />
          </div>
          <div>
            <label className="label" htmlFor="p-years">Years</label>
            <input id="p-years" className="field py-3 text-lg font-semibold sm:text-xl" type="number" min="0" max="50" step="0.5"
              inputMode="decimal" placeholder="2" value={form.years_experience} onChange={set("years_experience")} />
          </div>
        </div>

        <SkillInput value={form.skills} onChange={set("skills")} suggestions={suggestions} />
      </div>

      <div className="reveal" data-open={panel === "filters"} id="panel-filters">
        <div><div className="border-t border-line p-4 sm:p-6"><FilterPanel filters={filters} onChange={onFilters} /></div></div>
      </div>
      <div className="reveal" data-open={panel === "about"} id="panel-about">
        <div>
          <div className="grid gap-4 border-t border-line p-4 sm:grid-cols-[1fr_14rem] sm:p-6">
            <div>
              <label className="label" htmlFor="p-desc">About you <span className="font-normal text-ink-400">(used in HR drafts)</span></label>
              <textarea id="p-desc" rows={3} className="field resize-y" maxLength={2000}
                placeholder="Full-stack developer who builds MERN apps and LLM features with FastAPI…"
                value={form.description} onChange={set("description")} />
            </div>
            <div>
              <label className="label" htmlFor="p-name">Save this profile as</label>
              <input id="p-name" className="field" value={form.name} onChange={set("name")} maxLength={60} />
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-line p-3 sm:px-5">
        <Toggle open={panel === "filters"} onClick={() => flip("filters")} icon={SlidersHorizontal} controls="panel-filters">
          Filters{changedFilters > 0 && <span className="rounded-md bg-lime-300 px-1.5 text-xs font-bold text-ink-950">{changedFilters}</span>}
        </Toggle>
        <Toggle open={panel === "about"} onClick={() => flip("about")} icon={NotebookPen} controls="panel-about">About you</Toggle>
        <p className="hidden min-w-0 flex-1 truncate px-2 text-sm text-ink-500 md:block" title={describeFilters(filters)}>
          {describeFilters(filters)}
        </p>
        {running ? (
          <button type="button" className="btn btn-quiet ml-auto px-5 py-2.5" onClick={onStop}>
            <Square size={14} aria-hidden className="fill-current" /> Stop
          </button>
        ) : (
          <button type="submit" className="btn btn-signal ml-auto px-5 py-2.5" disabled={busy}>
            Find jobs <ArrowUp size={16} aria-hidden />
          </button>
        )}
      </div>
    </form>
  );
}
