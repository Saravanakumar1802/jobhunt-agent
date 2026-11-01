export const FILTER_OPTIONS = {
  workType: [
    { value: "any", label: "Any" },
    { value: "remote", label: "Remote" },
    { value: "hybrid", label: "Hybrid" },
    { value: "onsite", label: "On-site" },
  ],
  jobType: [
    { value: "any", label: "Any type" },
    { value: "fulltime", label: "Full-time" },
    { value: "parttime", label: "Part-time" },
    { value: "contract", label: "Contract" },
    { value: "internship", label: "Internship" },
  ],
  experience: [
    { value: "any", label: "Any" },
    { value: "fresher", label: "Fresher" },
    { value: "1-3", label: "1–3 yrs" },
    { value: "3-5", label: "3–5 yrs" },
    { value: "5+", label: "5+ yrs" },
  ],
  datePosted: [
    { value: "24h", label: "24 hours" },
    { value: "3d", label: "3 days" },
    { value: "7d", label: "7 days" },
    { value: "30d", label: "30 days" },
    { value: "any", label: "Any time" },
  ],
  source: [
    { value: "all", label: "All sources (LinkedIn first, then Naukri)" },
    { value: "linkedin", label: "LinkedIn only" },
    { value: "naukri", label: "Naukri only" },
    { value: "adzuna", label: "Adzuna" },
    { value: "remote_boards", label: "Remote boards (Remotive, Arbeitnow)" },
  ],
  country: [
    ["in", "India"], ["us", "United States"], ["gb", "United Kingdom"], ["ca", "Canada"], ["au", "Australia"],
    ["sg", "Singapore"], ["de", "Germany"], ["nl", "Netherlands"], ["ae", "United Arab Emirates"], ["fr", "France"],
  ],
};

export const DEFAULT_FILTERS = {
  country: "in", city: "", anywhere: false, work_type: "any", job_type: "any",
  experience: "any", date_posted: "7d", source: "all", min_score: 0,
};

const labelOf = (list, v) => list.find((o) => o.value === v)?.label;

/** Plain-language summary of the filters, shown in the composer and the brief bubble. */
export function describeFilters(f) {
  const country = FILTER_OPTIONS.country.find(([v]) => v === f.country)?.[1];
  const parts = [f.anywhere ? "Anywhere" : [f.city, country].filter(Boolean).join(", ")];
  parts.push(f.work_type === "any" ? "any work type" : labelOf(FILTER_OPTIONS.workType, f.work_type).toLowerCase());
  if (f.experience !== "any") parts.push(labelOf(FILTER_OPTIONS.experience, f.experience));
  if (f.job_type !== "any") parts.push(labelOf(FILTER_OPTIONS.jobType, f.job_type).toLowerCase());
  parts.push(f.date_posted === "any" ? "posted any time" : `posted in the last ${labelOf(FILTER_OPTIONS.datePosted, f.date_posted)}`);
  if (f.source !== "all") parts.push(labelOf(FILTER_OPTIONS.source, f.source));
  return parts.join(", ");
}

const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

export function timeAgo(iso) {
  if (!iso) return null;
  const days = Math.round((new Date(iso) - Date.now()) / 86_400_000);
  if (Math.abs(days) < 1) return "today";
  return rtf.format(days, "day");
}

export function shortDate(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

/** Score → semantic color + words, used by the ring and labels. */
export function scoreTone(score) {
  if (score >= 75) return { color: "var(--color-ok-500)", label: "Strong fit" };
  if (score >= 55) return { color: "var(--color-signal-500)", label: "Good fit" };
  if (score >= 35) return { color: "var(--color-warn-500)", label: "Partial fit" };
  return { color: "var(--color-bad-500)", label: "Long shot" };
}

export function publisherKind(publisher = "") {
  const p = publisher.toLowerCase();
  if (p.includes("linkedin")) return "linkedin";
  if (p.includes("naukri")) return "naukri";
  return "other";
}

export const WORK_TYPE_LABEL = { remote: "Remote", hybrid: "Hybrid", onsite: "On-site", unknown: "Work type not stated" };

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export const initials = (name = "?") =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "?";
