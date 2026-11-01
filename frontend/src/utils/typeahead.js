/**
 * Ranking for the skill and role dropdowns. Pure functions so they are easy to test.
 *
 * Order: exact match, then names that start with what was typed, then aliases that start with it
 * ("js" finds javascript), then a word inside the name ("fico" finds "sap fico"), then anything containing it.
 * Ties keep the catalog order, which lists the most popular skills and roles first.
 */
const norm = (s) => s.toLowerCase().replace(/\s+/g, " ").trim();
const spaced = (s) => ` ${s.replace(/[./\-+#()]+/g, " ").replace(/\s+/g, " ")}`;

// [exact, prefix, word start, contains]; null scores mean "no match".
// An alias typed in full ("js") beats names that merely start with it ("jsp"); inside an alias is never a match.
const LABEL = [0, 1, 3, 5];
const ALIAS = [0.5, 2, 4, null];

function score(text, q, [exact, prefix, word, contains], loose) {
  if (text === q) return exact;
  if (text.startsWith(q)) return prefix;
  if (spaced(text).includes(` ${q}`)) return word;
  if (loose && text.includes(q)) return contains; // one typed letter only matches starts of words, not the middle
  return null; // also what a `null` slot above means
}

/** items: [{label, terms?}]. Returns [{item, via, score}] best first; `via` is the alias that matched. */
export function rankMatches(query, items, { limit = 8, skip } = {}) {
  const q = norm(query);
  if (!q) return [];
  const loose = q.length > 1;
  const hits = [];
  items.forEach((item, index) => {
    if (skip?.(item)) return;
    let best = score(item.label.toLowerCase(), q, LABEL, loose);
    let via = null;
    for (const term of item.terms ?? []) {
      const s = score(term.toLowerCase(), q, ALIAS, loose);
      if (s != null && (best === null || s < best)) {
        best = s;
        via = term;
      }
    }
    if (best != null) hits.push({ item, via, score: best, index });
  });
  hits.sort((a, b) => a.score - b.score || a.index - b.index);
  return hits.slice(0, limit).map(({ item, via, score: s }) => ({ item, via, score: s }));
}

/** Splits a label around the typed text so the match can be bold: [before, match, after]. */
export function splitMatch(label, query) {
  const q = norm(query ?? "");
  const at = q ? label.toLowerCase().indexOf(q) : -1;
  return at < 0 ? [label, "", ""] : [label.slice(0, at), label.slice(at, at + q.length), label.slice(at + q.length)];
}
