import { useId, useMemo, useState } from "react";
import { Plus, X } from "lucide-react";
import Listbox from "../ui/Listbox";
import useTypeahead from "../../hooks/useTypeahead";
import { rankMatches } from "../../utils/typeahead";

const MAX_OPTIONS = 8;

/**
 * Chip input with a typeahead: type a letter and matching skills drop down (aliases count, "js" finds javascript).
 * Pick one to avoid typos, or type anything else and press Enter / comma to add it as written.
 * Backspace on an empty field removes the last chip. `suggested` shows one-click skills for the chosen role.
 */
export default function SkillInput({ value, onChange, catalog = [], suggested = [], suggestedFor = "" }) {
  const [draft, setDraft] = useState("");
  const inputId = useId();

  const items = useMemo(() => catalog.map((s) => ({ label: s.name, terms: s.aliases })), [catalog]);
  const names = useMemo(() => {
    const map = new Map();
    catalog.forEach((s) => [s.name, ...s.aliases].forEach((a) => map.set(a.toLowerCase(), s.name)));
    return map; // typed text or alias → canonical name
  }, [catalog]);
  const have = useMemo(() => new Set(value.map((s) => s.toLowerCase())), [value]);

  const add = (raw) => {
    const next = [...value];
    raw.split(",").map((s) => s.trim()).filter(Boolean).forEach((p) => {
      const skill = names.get(p.toLowerCase()) ?? p;
      if (!next.some((s) => s.toLowerCase() === skill.toLowerCase())) next.push(skill);
    });
    onChange(next);
    setDraft("");
  };

  const typed = draft.trim();
  const options = useMemo(() => {
    if (!typed) return [];
    const list = rankMatches(typed, items, { limit: MAX_OPTIONS, skip: (it) => have.has(it.label.toLowerCase()) })
      .map(({ item, via }) => ({ key: item.label, label: item.label, hint: via ? `matches “${via}”` : "" }));
    const known = names.has(typed.toLowerCase()) || have.has(typed.toLowerCase());
    return known ? list : [...list, { key: "__custom", label: typed, custom: true }];
  }, [typed, items, names, have]);

  const ta = useTypeahead({ options, onPick: (o) => add(o.label), autoFirst: true });
  const pending = suggested.filter((s) => !have.has(s.toLowerCase()));

  return (
    <div>
      <label className="label" htmlFor={inputId}>Your skills</label>
      <div className="relative">
        <div className="field flex flex-wrap items-center gap-1.5 focus-within:border-signal-500 focus-within:bg-surface focus-within:shadow-[0_0_0_4px_rgb(39_71_245/0.12)]">
          {value.map((s) => (
            <span key={s} className="chip rise-in bg-surface text-ink-800 shadow-[0_0_0_1px_var(--color-line)]">
              {s}
              <button type="button" aria-label={`Remove ${s}`} className="-mr-1 rounded p-0.5 text-ink-400 hover:bg-mist hover:text-ink-950"
                onClick={() => onChange(value.filter((x) => x !== s))}>
                <X size={12} />
              </button>
            </span>
          ))}
          <input
            id={inputId}
            {...ta.inputProps}
            value={draft}
            autoComplete="off"
            spellCheck={false}
            placeholder={value.length ? "Add more…" : "Start typing: react, sap fico, python…"}
            className="min-w-28 flex-1 bg-transparent py-0.5 outline-none placeholder:text-ink-400"
            onChange={(e) => {
              const v = e.target.value;
              if (v.endsWith(",")) return add(v);
              setDraft(v);
              ta.reset();
              ta.setOpen(true);
            }}
            onFocus={() => draft.trim() && ta.setOpen(true)}
            onBlur={() => {
              ta.setOpen(false);
              if (draft.trim()) add(draft);
            }}
            onKeyDown={(e) => {
              ta.onKeyDown(e);
              if (e.defaultPrevented) return;
              if (e.key === "Enter" && draft.trim()) {
                e.preventDefault();
                add(draft);
              } else if (e.key === "Backspace" && !draft && value.length) {
                onChange(value.slice(0, -1));
              }
            }}
          />
        </div>
        {ta.open && (
          <Listbox id={ta.listId} label="Skill suggestions" options={options} active={ta.active} query={typed}
            onPick={ta.pick} onHover={ta.setActive} />
        )}
      </div>
      <p className="sr-only" role="status">{ta.open ? `${options.length} suggestions` : ""}</p>
      <p className="mt-1.5 text-xs text-ink-400">
        Pick a suggestion to avoid typos, or type your own and press Enter. Aliases like "ReactJS" are merged automatically.
      </p>

      {pending.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5" aria-label={`Skills usually asked for ${suggestedFor}`}>
          <span className="mr-1 text-xs font-semibold text-ink-500">Usually asked for {suggestedFor}</span>
          {pending.map((s) => (
            <button key={s} type="button" onClick={() => add(s)}
              className="chip chip-soft cursor-pointer transition-colors hover:bg-signal-500 hover:text-white">
              <Plus size={12} aria-hidden /> {s}
            </button>
          ))}
          <button type="button" className="btn btn-plain px-2.5 py-1 text-xs" onClick={() => add(pending.join(","))}>
            Add all
          </button>
        </div>
      )}
    </div>
  );
}
