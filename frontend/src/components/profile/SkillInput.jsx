import { useId, useState } from "react";
import { X } from "lucide-react";

/** Chip input: Enter or comma adds a skill, Backspace on empty removes the last one. */
export default function SkillInput({ value, onChange, suggestions = [] }) {
  const [draft, setDraft] = useState("");
  const listId = useId();
  const inputId = useId();

  const add = (raw) => {
    const parts = raw.split(",").map((s) => s.trim()).filter(Boolean);
    const next = [...value];
    parts.forEach((p) => {
      if (!next.some((s) => s.toLowerCase() === p.toLowerCase())) next.push(p);
    });
    onChange(next);
    setDraft("");
  };

  return (
    <div>
      <label className="label" htmlFor={inputId}>Your skills</label>
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
          list={listId}
          value={draft}
          placeholder={value.length ? "Add more…" : "react, node.js, python…"}
          className="min-w-28 flex-1 bg-transparent py-0.5 outline-none placeholder:text-ink-400"
          onChange={(e) => (e.target.value.endsWith(",") ? add(e.target.value) : setDraft(e.target.value))}
          onKeyDown={(e) => {
            if (e.key === "Enter" && draft.trim()) {
              e.preventDefault();
              add(draft);
            } else if (e.key === "Backspace" && !draft && value.length) {
              onChange(value.slice(0, -1));
            }
          }}
          onBlur={() => draft.trim() && add(draft)}
        />
        <datalist id={listId}>
          {suggestions.map((s) => <option key={s} value={s} />)}
        </datalist>
      </div>
      <p className="mt-1.5 text-xs text-ink-400">Press Enter after each skill. Aliases like "ReactJS" are merged automatically.</p>
    </div>
  );
}
