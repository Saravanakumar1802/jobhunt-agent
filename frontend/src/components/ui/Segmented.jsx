import { useId } from "react";

/**
 * Segmented control built on native radio inputs: keyboard arrows, form semantics
 * and screen-reader grouping come for free.
 */
export default function Segmented({ label, options, value, onChange, size = "md" }) {
  const name = useId();
  const pad = size === "sm" ? "px-2.5 py-1.5 text-xs" : "px-3 py-2 text-sm";
  return (
    <fieldset className="min-w-0">
      {label && <legend className="label">{label}</legend>}
      <div className="flex flex-wrap gap-0.5 rounded-xl bg-mist p-1">
        {options.map((o) => (
          <label key={o.value} className="relative flex-1 cursor-pointer">
            <input type="radio" name={name} value={o.value} checked={value === o.value} onChange={() => onChange(o.value)}
              className="peer sr-only" />
            <span className={`block whitespace-nowrap rounded-lg text-center font-semibold text-ink-500 transition duration-200 hover:text-ink-950 peer-checked:bg-surface peer-checked:text-ink-950 peer-checked:shadow-[0_1px_2px_rgb(11_14_20/0.08),0_0_0_1px_var(--color-line)] peer-focus-visible:outline-2 peer-focus-visible:outline-signal-500 ${pad}`}>
              {o.label}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
