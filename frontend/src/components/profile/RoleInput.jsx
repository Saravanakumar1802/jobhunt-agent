import { useMemo } from "react";
import Listbox from "../ui/Listbox";
import useTypeahead from "../../hooks/useTypeahead";
import { rankMatches } from "../../utils/typeahead";

const MAX_OPTIONS = 8;

/**
 * Role field with a dropdown of IT roles. It is still a plain text field: type any role you like.
 * Focus on an empty field lists the common roles; nothing is highlighted until you arrow or hover,
 * so Enter keeps submitting the search.
 */
export default function RoleInput({ id, value, onChange, roles = [], className = "", ...rest }) {
  const items = useMemo(() => roles.map((r) => ({ label: r.role, terms: r.aliases, category: r.category })), [roles]);
  const typed = value.trim();

  const options = useMemo(() => {
    const hits = typed
      ? rankMatches(typed, items, { limit: MAX_OPTIONS }).map((h) => h.item)
      : items.slice(0, MAX_OPTIONS);
    return hits
      .filter((it) => it.label.toLowerCase() !== typed.toLowerCase())
      .map((it) => ({ key: it.label, label: it.label, hint: it.category }));
  }, [typed, items]);

  const ta = useTypeahead({ options, onPick: (o) => onChange(o.label) });

  return (
    <div className="relative">
      <input
        id={id}
        {...ta.inputProps}
        {...rest}
        className={className}
        value={value}
        autoComplete="off"
        onChange={(e) => {
          onChange(e.target.value);
          ta.reset();
          ta.setOpen(true);
        }}
        onFocus={() => !typed && ta.setOpen(true)}
        onBlur={() => ta.setOpen(false)}
        onKeyDown={ta.onKeyDown}
      />
      {ta.open && (
        <Listbox id={ta.listId} label="Role suggestions" options={options} active={ta.active} query={typed}
          onPick={ta.pick} onHover={ta.setActive} />
      )}
    </div>
  );
}
