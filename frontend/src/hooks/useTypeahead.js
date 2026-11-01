import { useId, useState } from "react";

/**
 * Keyboard and ARIA behaviour shared by the skill and role dropdowns (the WAI-ARIA "combobox with listbox popup").
 * The caller owns the text and the options; this owns open/active state and the arrow, Enter and Escape keys.
 *
 * autoFirst: highlight the first option as soon as there are options, so Enter picks it (skills).
 * Without it nothing is highlighted until the user arrows or hovers, so Enter still submits the form (roles).
 */
export default function useTypeahead({ options, onPick, autoFirst = false }) {
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState(-1);
  const listId = useId();
  const n = options.length;

  // Derived rather than reset in an effect: an out-of-range or unset index falls back to the default.
  const active = n === 0 ? -1 : chosen >= n || chosen < 0 ? (autoFirst ? 0 : -1) : chosen;
  const visible = open && n > 0;

  const pick = (i) => {
    if (!options[i]) return;
    onPick(options[i]);
    setOpen(false);
    setChosen(-1);
  };

  const onKeyDown = (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!n) return;
      e.preventDefault();
      const dir = e.key === "ArrowDown" ? 1 : -1;
      setOpen(true);
      setChosen((((active < 0 ? (dir > 0 ? -1 : 0) : active) + dir) % n + n) % n);
    } else if (e.key === "Enter" && visible && active >= 0) {
      e.preventDefault();
      pick(active);
    } else if (e.key === "Escape" && visible) {
      e.preventDefault();
      e.stopPropagation(); // don't also close a dialog the field sits in
      setOpen(false);
    }
  };

  return {
    open: visible,
    setOpen,
    active,
    setActive: setChosen,
    listId,
    pick,
    onKeyDown,
    /** Call when the typed text changes. */
    reset: () => setChosen(-1),
    inputProps: {
      role: "combobox",
      "aria-expanded": visible,
      "aria-controls": listId,
      "aria-autocomplete": "list",
      "aria-activedescendant": visible && active >= 0 ? `${listId}-${active}` : undefined,
    },
  };
}
