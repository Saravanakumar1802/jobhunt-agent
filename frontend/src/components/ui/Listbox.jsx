import { useEffect, useRef } from "react";
import { Plus } from "lucide-react";
import { splitMatch } from "../../utils/typeahead";

/**
 * The dropdown under a combobox input. Options: [{key, label, hint?, custom?}]. A `custom` option is the
 * "use exactly what I typed" row. Mouse down is cancelled so the input keeps focus while you click.
 */
export default function Listbox({ id, label, options, active, query, onPick, onHover }) {
  const activeRef = useRef(null);
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest" });
  }, [active]);

  return (
    <ul id={id} role="listbox" aria-label={label}
      className="surface absolute inset-x-0 top-full z-40 mt-2 max-h-72 overflow-y-auto overscroll-contain rounded-2xl p-1.5 shadow-[0_24px_48px_-20px_rgb(11_14_20/0.4)]">
      {options.map((o, i) => {
        const [before, match, after] = o.custom ? [o.label, "", ""] : splitMatch(o.label, query);
        return (
          <li key={o.key} id={`${id}-${i}`} role="option" aria-selected={i === active} ref={i === active ? activeRef : null}
            onMouseDown={(e) => e.preventDefault()} onClick={() => onPick(i)} onMouseEnter={() => onHover(i)}
            className={`flex cursor-pointer items-center justify-between gap-3 rounded-xl px-3 py-2 text-sm ${
              i === active ? "bg-mist" : ""
            } ${o.custom ? "border-t border-line text-ink-600" : ""}`}>
            {o.custom ? (
              <span className="flex min-w-0 items-center gap-2">
                <Plus size={14} aria-hidden className="shrink-0 text-ink-400" />
                <span className="truncate">Add “<strong className="font-semibold text-ink-950">{o.label}</strong>” as typed</span>
              </span>
            ) : (
              <span className="min-w-0 truncate font-medium">
                {before}<strong className="font-bold text-signal-600">{match}</strong>{after}
              </span>
            )}
            {o.hint && <span className="shrink-0 text-xs text-ink-400">{o.hint}</span>}
          </li>
        );
      })}
    </ul>
  );
}
