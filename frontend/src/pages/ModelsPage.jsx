/**
 * AI model health and switching. Status comes from each provider's live model list
 * (zero tokens); "Test" sends one tiny real request. Only free-tier models can be saved —
 * the backend rejects anything else.
 */
import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, FlaskConical, Plus, RefreshCw, RotateCcw, X } from "lucide-react";
import { statusApi } from "../api/endpoints";
import { useAuth } from "../context/AuthContext";
import { useModels, useModelsMutation } from "../hooks/queries";
import { useToast } from "../components/ui/Toast";

const STATUS = {
  ok: { label: "Working", cls: "bg-ok-50 text-ok-700" },
  unknown: { label: "Not checked yet", cls: "bg-mist text-ink-600" },
  rate_limited: { label: "Resting after limit", cls: "bg-warn-50 text-warn-700" },
  unavailable: { label: "Retired or unavailable", cls: "bg-bad-50 text-bad-700" },
  auth_error: { label: "Key rejected", cls: "bg-bad-50 text-bad-700" },
  no_key: { label: "No API key", cls: "bg-mist text-ink-500" },
  error: { label: "Error", cls: "bg-bad-50 text-bad-700" },
  rejected: { label: "Not a free model", cls: "bg-bad-50 text-bad-700" },
};

const TIER_INFO = {
  small: { title: "Fast model", body: "Reads job descriptions and lists their requirements. Called in batches of four jobs." },
  mid: { title: "Smart model", body: "Judges seniority and domain fit, and writes your HR drafts." },
};

const PROVIDER_LABEL = { groq: "Groq", gemini: "Google Gemini", openrouter: "OpenRouter" };

function TierEditor({ tier, rows, chain, setChain, suggestions, isAdmin, onTest, testing }) {
  const [custom, setCustom] = useState("");
  const statusOf = (m) => rows.find((r) => r.model === m) ?? { status: "unknown", detail: "Save to check" };
  const move = (i, d) => {
    const next = [...chain];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    setChain(next);
  };
  const add = (m) => m && !chain.includes(m) && setChain([...chain, m]);
  const allSuggestions = Object.entries(suggestions).flatMap(([p, list]) => list.map((m) => ({ p, m })));

  return (
    <section className="surface scroll-in min-w-0 p-5 sm:p-6" aria-labelledby={`tier-${tier}`}>
      <h2 id={`tier-${tier}`} className="text-xl font-bold">{TIER_INFO[tier].title}</h2>
      <p className="mt-1 text-sm text-ink-500">{TIER_INFO[tier].body} Tried top to bottom; the next one takes over automatically.</p>

      <ol className="mt-5 space-y-2.5">
        {chain.map((m, i) => {
          const s = statusOf(m);
          const st = STATUS[s.status] ?? STATUS.unknown;
          return (
            <li key={m} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-mist p-3.5">
              <span className="grid size-7 place-items-center rounded-full bg-mist text-sm font-bold text-ink-600" aria-label={`Priority ${i + 1}`}>{i + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">{m}</p>
                {s.detail && <p className="truncate text-xs text-ink-400" title={s.detail}>{s.detail}</p>}
              </div>
              <span className={`chip ${st.cls}`}>{st.label}</span>
              {isAdmin && (
                <div className="flex items-center gap-1">
                  <button type="button" className="btn btn-quiet p-2" aria-label={`Test ${m}`} onClick={() => onTest(m)} disabled={testing === m}>
                    <FlaskConical size={14} className={testing === m ? "animate-pulse" : ""} />
                  </button>
                  <button type="button" className="btn btn-quiet p-2" aria-label={`Move ${m} up`} disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp size={14} /></button>
                  <button type="button" className="btn btn-quiet p-2" aria-label={`Move ${m} down`} disabled={i === chain.length - 1} onClick={() => move(i, 1)}><ArrowDown size={14} /></button>
                  <button type="button" className="btn btn-quiet p-2" aria-label={`Remove ${m}`} disabled={chain.length === 1}
                    onClick={() => setChain(chain.filter((x) => x !== m))}><X size={14} /></button>
                </div>
              )}
            </li>
          );
        })}
      </ol>

      {isAdmin && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor={`sug-${tier}`}>Add a free model from the live list</label>
            <select id={`sug-${tier}`} className="field" value="" onChange={(e) => add(e.target.value)}>
              <option value="">{allSuggestions.length ? "Choose a model…" : "Press “Check models now” to load the list"}</option>
              {Object.entries(suggestions).map(([p, list]) => list.length > 0 && (
                <optgroup key={p} label={PROVIDER_LABEL[p] ?? p}>
                  {list.filter((m) => !chain.includes(m)).map((m) => <option key={m} value={m}>{m}</option>)}
                </optgroup>
              ))}
            </select>
          </div>
          <form onSubmit={(e) => { e.preventDefault(); add(custom.trim()); setCustom(""); }}>
            <label className="label" htmlFor={`custom-${tier}`}>Or type a model id</label>
            <div className="flex gap-2">
              <input id={`custom-${tier}`} className="field" placeholder="groq/openai/gpt-oss-20b" value={custom}
                onChange={(e) => setCustom(e.target.value)} spellCheck="false" />
              <button className="btn btn-quiet px-3" aria-label="Add model"><Plus size={16} /></button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}

export default function ModelsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const { data, isLoading } = useModels();
  const [edited, setChains] = useState(null); // null = show the saved chains
  const [testing, setTesting] = useState(null);
  const check = useModelsMutation(statusApi.checkModels);
  const save = useModelsMutation(statusApi.saveModels);
  const reset = useModelsMutation(statusApi.resetModels);
  const isAdmin = Boolean(user?.is_admin);
  const { mutate: runCheck } = check;

  // Refresh health from the providers' model lists when the page opens (costs no tokens).
  useEffect(() => runCheck(), [runCheck]);

  if (isLoading || !data) return <div className="skeleton h-96" />;
  const chains = edited ?? { small: data.tiers.small.map((r) => r.model), mid: data.tiers.mid.map((r) => r.model) };
  const suggestions = check.data?.suggestions ?? {};

  const dirty = ["small", "mid"].some((t) => chains[t].join() !== data.tiers[t].map((r) => r.model).join());
  const onTest = async (model) => {
    setTesting(model);
    try {
      const r = await statusApi.testModel(model);
      toast(`${model}: ${(STATUS[r.status] ?? STATUS.error).label}`, r.status === "ok" ? "ok" : "error");
      check.mutate();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setTesting(null);
    }
  };
  const onSave = () =>
    save.mutate(chains, {
      onSuccess: () => { setChains(null); toast("Model order saved. New searches use it right away."); check.mutate(); },
      onError: (e) => toast(e.message, "error"),
    });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-wide text-[clamp(2rem,4vw,2.8rem)] font-bold">AI models</h1>
          <p className="mt-2 max-w-2xl text-ink-500">
            Free models get retired or renamed now and then. If one shows as retired, add a replacement from the live list and save.
            Only free-tier models are allowed.
          </p>
        </div>
        <button type="button" className="btn btn-quiet" onClick={() => check.mutate(undefined, { onError: (e) => toast(e.message, "error") })} disabled={check.isPending}>
          <RefreshCw size={15} className={check.isPending ? "animate-spin" : ""} aria-hidden /> Check models now
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {Object.entries(data.providers).map(([p, ok]) => (
          <span key={p} className={`chip ${ok ? "chip-match" : "bg-mist text-ink-500"}`}>
            {PROVIDER_LABEL[p]}: {ok ? "key added" : "no key"}
          </span>
        ))}
      </div>

      {!Object.values(data.providers).some(Boolean) && (
        <div className="rounded-2xl border border-transparent bg-warn-50 p-5 text-sm leading-relaxed text-warn-700">
          No AI keys found. The app still works with keyword scoring and template drafts. To turn on AI, create free keys
          (no card needed) by following <strong>docs/SETUP_KEYS.md</strong>, add them to <strong>backend/.env</strong>, and restart the backend.
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        {["small", "mid"].map((tier) => (
          <TierEditor key={tier} tier={tier} rows={data.tiers[tier]} chain={chains[tier]} isAdmin={isAdmin}
            setChain={(c) => setChains({ ...chains, [tier]: c })} suggestions={suggestions} onTest={onTest} testing={testing} />
        ))}
      </div>

      {isAdmin ? (
        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn btn-ink" onClick={onSave} disabled={!dirty || save.isPending}>Save model order</button>
          <button type="button" className="btn btn-quiet" onClick={() => reset.mutate(undefined, {
            onSuccess: () => { setChains(null); toast("Defaults restored"); check.mutate(); },
          })}>
            <RotateCcw size={15} aria-hidden /> Restore defaults
          </button>
        </div>
      ) : (
        <p className="text-sm text-ink-400">Only the first account created (the admin) can change models.</p>
      )}
    </div>
  );
}
