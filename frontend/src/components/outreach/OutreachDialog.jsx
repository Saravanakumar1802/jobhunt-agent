/**
 * Side sheet built on native <dialog> + showModal(): focus trap, Esc, inert page and
 * focus return come from the browser. Drafts are generated only on click (lazy = cheap)
 * and the app never sends anything — the user copies and sends it themselves.
 */
import { useEffect, useId, useRef, useState } from "react";
import { Copy, Sparkles, UserSearch, X } from "lucide-react";
import Segmented from "../ui/Segmented";
import { jobsApi } from "../../api/endpoints";
import { hrSearchUrl } from "../../utils/links";
import { copyText } from "../../utils/format";
import { useToast } from "../ui/Toast";

const KINDS = [
  { value: "message", label: "HR message" },
  { value: "cover_letter", label: "Cover letter" },
  { value: "bullets", label: "Resume bullets" },
];
const TONES = [
  { value: "short", label: "Short" },
  { value: "friendly", label: "Friendly" },
  { value: "formal", label: "Formal" },
];

export default function OutreachDialog({ item, profileId, onClose, onSaveHr }) {
  const ref = useRef(null);
  const titleId = useId();
  const toast = useToast();
  const [kind, setKind] = useState("message");
  const [tone, setTone] = useState("short");
  const [draft, setDraft] = useState(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [hrUrl, setHrUrl] = useState("");

  // The parent remounts this component per job (key={job.id}), so draft state starts fresh.
  useEffect(() => {
    const dialog = ref.current;
    if (item && !dialog.open) dialog.showModal();
  }, [item]);

  useEffect(() => {
    // Light dismiss where `closedby` is unsupported (Safari): press and release outside the sheet.
    const dialog = ref.current;
    if ("closedBy" in HTMLDialogElement.prototype) return;
    let pressedOutside = false;
    const outside = (e) => {
      const r = dialog.getBoundingClientRect();
      return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
    };
    const down = (e) => (pressedOutside = outside(e));
    const up = (e) => pressedOutside && outside(e) && dialog.close();
    dialog.addEventListener("pointerdown", down);
    dialog.addEventListener("pointerup", up);
    return () => {
      dialog.removeEventListener("pointerdown", down);
      dialog.removeEventListener("pointerup", up);
    };
  }, []);

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await jobsApi.draft(item.job.id, { profile_id: profileId, tone, kind });
      setDraft(res);
      setText(res.subject && kind !== "bullets" ? `Subject: ${res.subject}\n\n${res.body}` : res.body);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const job = item?.job;
  return (
    <dialog ref={ref} className="sheet" aria-labelledby={titleId} closedby="any" onClose={onClose}>
      {job && (
        <div className="flex h-full flex-col">
          <header className="flex items-start justify-between gap-4 border-b border-line p-6">
            <div>
              <p className="text-sm text-ink-500">{job.company}</p>
              <h2 id={titleId} className="mt-1 text-xl font-bold leading-snug">{job.title}</h2>
            </div>
            <button type="button" className="btn btn-quiet p-2" aria-label="Close" onClick={() => ref.current.close()}>
              <X size={18} />
            </button>
          </header>

          <div className="flex-1 space-y-5 overflow-y-auto p-6">
            <Segmented label="What to write" options={KINDS} value={kind} onChange={(v) => { setKind(v); setDraft(null); }} size="sm" />
            {kind !== "bullets" && <Segmented label="Tone" options={TONES} value={tone} onChange={(v) => { setTone(v); setDraft(null); }} size="sm" />}

            <button type="button" className="btn btn-signal w-full" onClick={generate} disabled={busy} autoFocus>
              <Sparkles size={16} aria-hidden />
              {busy ? "Writing your draft…" : draft ? "Write again" : "Write draft"}
            </button>

            {error && <p role="alert" className="rounded-xl bg-bad-50 p-3 text-sm text-bad-700">{error}</p>}

            {busy && <div className="skeleton h-48" aria-hidden />}
            {!busy && draft && (
              <div className="space-y-2">
                <label className="label" htmlFor="draft-text">Your draft (edit before sending)</label>
                <textarea id="draft-text" className="field min-h-64 resize-y leading-relaxed" value={text}
                  onChange={(e) => setText(e.target.value)} />
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-ink-400">
                    {draft.method === "llm" ? `Written by ${draft.model}${draft.cached ? " (saved copy)" : ""}` : "AI is busy, so this is a template draft"}
                  </span>
                  <button type="button" className="btn btn-ink px-4 py-2 text-sm"
                    onClick={async () => toast(await copyText(text) ? "Copied to clipboard" : "Copy failed — select the text and copy it", "ok")}>
                    <Copy size={14} aria-hidden /> Copy
                  </button>
                </div>
              </div>
            )}

            <section className="rounded-2xl border border-line bg-mist p-4">
              <h3 className="font-bold">Find the right person</h3>
              <p className="mt-1 text-sm text-ink-500">
                Open a LinkedIn search for recruiters at {job.company}, pick someone, then paste their profile link here to keep it with this job.
              </p>
              <a className="btn btn-quiet mt-3 px-4 py-2 text-sm" href={hrSearchUrl(job.company)} target="_blank" rel="noopener noreferrer">
                <UserSearch size={14} aria-hidden /> Search recruiters on LinkedIn
              </a>
              <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); onSaveHr(item, hrUrl); }}>
                <label htmlFor="hr-url" className="sr-only">HR profile link</label>
                <input id="hr-url" type="url" className="field" placeholder="https://www.linkedin.com/in/…" value={hrUrl}
                  onChange={(e) => setHrUrl(e.target.value)} required />
                <button className="btn btn-quiet shrink-0 px-4 text-sm">Save link</button>
              </form>
            </section>
            <p className="text-xs text-ink-400">Job Hunt Copilot never sends messages for you. Review the draft and send it from your own account.</p>
          </div>
        </div>
      )}
    </dialog>
  );
}
