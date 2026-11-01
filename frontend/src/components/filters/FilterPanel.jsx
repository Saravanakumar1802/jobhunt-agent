import Segmented from "../ui/Segmented";
import { FILTER_OPTIONS } from "../../utils/format";

/** Filters are sent to the job APIs, so tighter filters = fewer jobs = less quota and fewer tokens. */
export default function FilterPanel({ filters, onChange }) {
  const set = (key) => (value) => onChange({ ...filters, [key]: value });

  return (
    <div className="grid gap-5 lg:grid-cols-2 lg:gap-x-8">
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="f-country">Country</label>
            <select id="f-country" className="field" value={filters.country} disabled={filters.anywhere}
              onChange={(e) => set("country")(e.target.value)}>
              {FILTER_OPTIONS.country.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="f-city">City</label>
            <input id="f-city" className="field" placeholder="e.g. Chennai" value={filters.city} disabled={filters.anywhere}
              autoComplete="address-level2" onChange={(e) => set("city")(e.target.value)} />
          </div>
        </div>
        <label className="flex items-center gap-2.5 text-sm text-ink-600">
          <input type="checkbox" className="size-4 accent-signal-500" checked={filters.anywhere}
            onChange={(e) => set("anywhere")(e.target.checked)} />
          Search anywhere in the world
        </label>
      </div>

      <Segmented label="Work type" options={FILTER_OPTIONS.workType} value={filters.work_type} onChange={set("work_type")} size="sm" />
      <Segmented label="Experience" options={FILTER_OPTIONS.experience} value={filters.experience} onChange={set("experience")} size="sm" />

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="f-type">Job type</label>
          <select id="f-type" className="field" value={filters.job_type} onChange={(e) => set("job_type")(e.target.value)}>
            {FILTER_OPTIONS.jobType.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="f-date">Posted within</label>
          <select id="f-date" className="field" value={filters.date_posted} onChange={(e) => set("date_posted")(e.target.value)}>
            {FILTER_OPTIONS.datePosted.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      <div>
        <label className="label" htmlFor="f-source">Source</label>
        <select id="f-source" className="field" value={filters.source} onChange={(e) => set("source")(e.target.value)}>
          {FILTER_OPTIONS.source.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      <div>
        <div className="flex items-baseline justify-between">
          <label className="label" htmlFor="f-min">Hide matches below</label>
          <output htmlFor="f-min" className="text-sm font-bold tabular-nums text-signal-600">{filters.min_score}%</output>
        </div>
        <input id="f-min" type="range" min="0" max="90" step="5" value={filters.min_score}
          onChange={(e) => set("min_score")(Number(e.target.value))} className="mt-1.5 w-full accent-signal-500" />
      </div>
    </div>
  );
}
