# Job Hunt Copilot: Code Overview

This document explains what the app does, how every part works, and why it was built this way. It's arranged so you can answer interview questions about any file. Read sections 1, 5 and 7 first for the big picture.

---

## 1. Project summary

**Problem.** Job hunting means checking LinkedIn and Naukri every day, reading dozens of descriptions to see whether you fit, and writing a fresh note to each recruiter. Most of that work is repetitive.

**What the app does.**
1. You set filters (location, work type, experience, date posted, source, minimum score) and a profile (target role, skills, years, a short bio).
2. One click runs a five-agent pipeline. It fetches live jobs, filters them cheaply, reads each shortlisted posting with a small LLM, scores your fit with a larger LLM, and ranks the results: **LinkedIn first, Naukri second, best match on top**.
3. Each result shows a match score, the skills you have and the skills you're missing, posted and closing dates, apply and company links.
4. On demand, it drafts an HR message, cover letter or resume bullets, and opens a pre-filled LinkedIn recruiter search. **You** send the message; the app never does.
5. A tracker (Saved, Applied, Interview, Rejected), a usage page (quotas, tokens, cache hit rate) and an **AI models** page. That page shows when a free model has been retired and lets you switch to another from the live list.

**Constraint that shapes everything:** every service is a free tier with no card. That's why the design is about *protecting two quotas*, job-API calls (~200 a month on JSearch) and LLM requests and tokens.

**Architecture**

```
┌──────────────── React 19 + Vite (frontend/) ────────────────┐
│ Landing (3D + GSAP) │ Search │ Tracker │ AI models │ Usage   │
│ TanStack Query (server state) · fetch-stream SSE reader      │
└───────────────┬──────────────────────────────────────────────┘
                │ REST (JSON) + POST /api/search → text/event-stream
┌───────────────▼──────────── FastAPI (backend/app) ───────────┐
│ routes → services/agents → repositories → MongoDB            │
│                                                              │
│  LangGraph pipeline                                          │
│  search ─► prefilter ─► analyzer ─► matcher ─► ranker        │
│    │          (Python)    (small LLM)  (mid LLM)  (Python)   │
│    ▼                                                         │
│  JobSourceRegistry: cache → JSearch → Adzuna → Remotive      │
│                     → Arbeitnow → demo dataset               │
│  LLMClient: Groq → Gemini → OpenRouter(:free), free-only     │
│             guard, cooldowns, health tracking                │
└───────────────┬──────────────────────────────────────────────┘
                ▼
        MongoDB Atlas (or in-memory DB when MONGODB_URI is empty)
```

---

## 2. Folder structure

```
Job_copilot/
├── README.md                 quick start, eval table
├── CODE_OVERVIEW.md          this file
├── docs/SETUP_KEYS.md        how to create each free account and key
├── backend/
│   ├── app/
│   │   ├── main.py           app factory + lifespan (DB, http client, LLM client, health loop)
│   │   ├── core/             config, security, errors, rate limiting, small utils
│   │   ├── db/               Mongo connection + in-memory stand-in
│   │   ├── schemas/          Pydantic models = the API contract
│   │   ├── repositories/     ALL database access (one class per collection group)
│   │   ├── services/
│   │   │   ├── job_sources/  one file per job API + registry (fallback, quota, cache)
│   │   │   ├── llm/          LLM client, free-only guard, health checks, prompts, JSON output
│   │   │   ├── text/         skill taxonomy, JD trimmer, pre-filter (zero tokens)
│   │   │   └── scoring.py    hybrid match score
│   │   ├── agents/           LangGraph state, nodes, graph, on-demand outreach agent
│   │   └── api/              FastAPI dependencies + routers
│   ├── data/                 skills_taxonomy.json, demo_jobs.json
│   ├── evals/                labelled jobs, eval runner, RESULTS.md
│   ├── scripts/              check_models.py
│   └── tests/                unit/, integration/, test_live.py (opt-in)
└── frontend/
    ├── index.html, vite.config.js, eslint.config.js
    └── src/
        ├── main.jsx, App.jsx  providers + routes
        ├── api/              fetch wrapper, endpoint functions, SSE stream reader
        ├── context/          AuthContext
        ├── hooks/            useSearchStream (SSE → state), TanStack Query hooks
        ├── components/       ui/, layout/, filters/, profile/, jobs/, progress/, outreach/, three/
        ├── pages/            Landing, AuthPage, SearchPage, TrackerPage, ModelsPage, StatusPage
        ├── styles/index.css  design tokens + component classes (Tailwind v4)
        ├── utils/            formatting, filter options, links
        └── test/             Vitest + Testing Library + MSW
```

**Layering rule (backend):** `routes → services/agents → repositories → DB`. Routes hold no business logic, and only repositories know Mongo exists. Each layer can be tested on its own, and swapping Mongo would touch one folder.

---

## 3. Backend (FastAPI)

### 3.1 File map

| File | Use |
|---|---|
| `main.py` | `create_app()` registers middleware, error handlers and routers. `lifespan` connects the DB, builds the shared `httpx.AsyncClient`, `LLMClient` and `JobSourceRegistry`, and starts a background task that re-checks model health every 6 h. |
| `core/config.py` | `Settings` (pydantic-settings) reads `.env`. Holds every tuning value: quotas, cache TTL, top-K, batch sizes, concurrency, default model chains. |
| `core/security.py` | bcrypt password hashing, JWT create/decode (PyJWT, HS256). |
| `core/errors.py` | `AppError` hierarchy plus handlers, so every error returns `{"error": {"code", "message"}}`. |
| `core/rate_limit.py` | slowapi limiter keyed by user id (from the JWT) or IP. |
| `core/utils.py` | `stable_hash` (cache keys), `utcnow`, `month_key`, `ensure_aware`. |
| `db/mongo.py` | One `AsyncMongoClient` per process (PyMongo's native async driver; Motor is deprecated). `ensure_indexes()` creates all indexes, including TTLs. |
| `db/memory.py` | mongomock-backed async stand-in, used when `MONGODB_URI` is empty and in tests. |
| `schemas/*.py` | Request/response models. `SearchFilters` (enums for every filter), `ProfileIn` (normalises skills, computes `profile_hash`), `NormalizedJob` (one shape for all providers, `dedupe_hash`), `JobAnalysis`, `MatchResult`, `RankedJob`, outreach and tracker models. |
| `repositories/jobs.py` | Job upserts (bulk), search cache, analysis cache, match cache. |
| `repositories/usage.py` | Monthly job-API counters, LLM call log (model, tokens, latency, fallback depth), search events. |
| `repositories/settings.py` | Runtime model chains saved from the UI, persisted model health, outreach draft cache. |
| `repositories/users.py, profiles.py, tracker.py` | CRUD scoped by `user_id`, so users can't see each other's data. |
| `services/job_sources/base.py` | `JobProvider` abstract class, `QuotaExceededError`, `ProviderError`, `search_query()` cleaning, work-type inference, date parsing. |
| `services/job_sources/jsearch.py` | Primary source. Maps filters onto JSearch params (`date_posted`, `employment_types`, `job_requirements`, `work_from_home`, `country`, plus "via linkedin/naukri" hints). Reads remaining quota from response headers. |
| `services/job_sources/adzuna.py` | Country-scoped endpoint, filter mapping, "Jobs by Adzuna" attribution. |
| `services/job_sources/remote_boards.py` | Remotive + Arbeitnow, keyless fallbacks with local freshness and relevance filtering. |
| `services/job_sources/demo.py` | 20 fictional jobs so the demo never breaks. |
| `services/job_sources/registry.py` | The orchestration: cache → fallback chain → dedupe → publisher filter → store → cache. Also `publisher_priority()` (LinkedIn 0, Naukri 1, others 2). |
| `services/text/skills.py` | Skill taxonomy (aliases → canonical), regex extraction, `split_requirements` (required vs nice-to-have), `is_grounded` (is this skill really in the text?). |
| `services/text/jd_trimmer.py` | Strips HTML and drops benefits/EEO/about-us sections. Keeps requirements; caps length. |
| `services/text/prefilter.py` | Zero-token ranking: skill coverage + fuzzy title similarity + experience fit. |
| `services/scoring.py` | Hybrid score: deterministic base, calibrated, plus an LLM nudge clamped to ±15. |
| `services/llm/client.py` | Priority fallback over free models, cooldown after 429, retired-model detection, concurrency semaphore, token logging. |
| `services/llm/free_guard.py` | Rejects any model that isn't free (Gemini Pro, non-`:free` OpenRouter, unknown providers). |
| `services/llm/health.py` | Checks models against each provider's live model list (zero tokens), suggests free replacements, `ping()` for a real test. |
| `services/llm/structured.py` | JSON mode → parse → Pydantic validate → one repair retry. |
| `services/llm/prompts.py` | System prompts (static, first) and user-prompt builders (variable, last). |
| `agents/state.py` | `PipelineState` TypedDict shared by all nodes. |
| `agents/deps.py` | `PipelineDeps` (registry, repo, LLM client) passed through LangGraph's typed runtime context; `emit()` progress helper. |
| `agents/nodes/*.py` | One agent per file (see 3.6). |
| `agents/graph.py` | Builds and compiles the `StateGraph` once; `run_pipeline()` streams progress plus the final state. |
| `agents/outreach.py` | On-demand drafts, LinkedIn recruiter-search URL, template fallback. |
| `api/deps.py` | `current_user`, `admin_user`, DB and service injection. |
| `api/routes/*.py` | Thin HTTP layer (see 3.3). |

### 3.2 Packages and why

| Package | Why |
|---|---|
| fastapi + uvicorn | Async API, automatic validation from Pydantic, OpenAPI docs at `/docs`. |
| pydantic v2, pydantic-settings | Schemas for API and LLM output; typed config from `.env`. |
| pymongo (async) | Official async driver (`AsyncMongoClient`). Motor reached end of life in May 2026. |
| httpx | Async HTTP with connection pooling for job and provider APIs. |
| litellm | One `acompletion()` call shape for Groq, Gemini and OpenRouter. |
| langgraph | Explicit agent graph, shared state, streaming of custom progress events. |
| slowapi | Per-user rate limits. |
| pyjwt, bcrypt | Stateless auth, safe password storage. |
| rapidfuzz | Fast fuzzy title matching in the pre-filter. |
| mongomock | In-memory DB for tests and no-Atlas local runs. |
| pytest, pytest-asyncio, respx, ruff | Tests, async tests, HTTP mocking, linting. |

### 3.3 API endpoints (all under `/api`)

| Method | Route | Auth | Purpose | Request → Response |
|---|---|---|---|---|
| POST | `/auth/register` | – | Create account (first = admin) | `{name,email,password}` → `{access_token,user}` |
| POST | `/auth/login` | – | Sign in | `{email,password}` → `{access_token,user}` |
| GET | `/auth/me` | JWT | Current user | → `UserOut` |
| GET/POST | `/profiles` | JWT | List / create profiles | `ProfileIn` → `ProfileOut` |
| GET/PUT/DELETE | `/profiles/{id}` | JWT | One profile | |
| GET | `/profiles/skills/suggestions` | – | Autocomplete list | → `[str]` |
| POST | `/search` | JWT | **Runs the agent graph, streams SSE** | `{profile_id, filters, force_refresh}` → `progress…` then `result {jobs, meta}` |
| GET | `/jobs/{id}` | JWT | Job detail | → `NormalizedJob` |
| GET | `/jobs/{id}/hr-search-link` | JWT | LinkedIn recruiter search URL | → `{company,url}` |
| POST | `/jobs/{id}/outreach` | JWT | Draft (cached) | `{profile_id,tone,kind}` → `OutreachOut` |
| GET/POST | `/tracker` | JWT | List / save job | `{job_id,status,notes,hr_profile_url}` |
| PATCH/DELETE | `/tracker/{job_id}` | JWT | Update / remove | |
| GET | `/status` | JWT | Quotas, LLM usage, cache hit rate, recent searches | |
| GET | `/models` | JWT | Model chains + health | |
| POST | `/models/check` | JWT | Refresh health from provider lists, get suggestions | |
| POST | `/models/test` | Admin | One tiny real request to a model | `{model}` |
| PUT | `/models` | Admin | Save new chains (free-only validated) | `{small:[…], mid:[…]}` |
| POST | `/models/reset` | Admin | Restore defaults | |
| GET | `/health` | – | Liveness | |

Rate limits: search 15/hour, outreach 40/hour, register 10/hour, login 20/min per user or IP.

### 3.4 Database collections and indexes

| Collection | Holds | Indexes | Why |
|---|---|---|---|
| `users` | name, email, bcrypt hash, is_admin | unique `email` | No duplicate accounts |
| `profiles` | role, skills, years, bio | `user_id` | Fast per-user list |
| `jobs` | `NormalizedJob`; `_id = "{source}:{external_id}"` | `dedupe_hash`, `fetched_at` | Re-rank without re-fetching |
| `search_cache` | query+filters hash → job ids | unique `key`, **TTL 6 h** | Identical search = 0 API calls |
| `job_analyses` | LLM-extracted requirements per job | unique `job_id` | **Profile-independent**: every user reuses it |
| `matches` | score per (job, profile version) | unique (`job_id`,`profile_hash`) | Same profile never re-scored |
| `outreach` | drafts per (job, profile, tone, kind) | unique `key` | Same draft never regenerated |
| `tracker` | status, notes, HR link, job snapshot | unique (`user_id`,`job_id`) | Upsert-safe saves |
| `api_usage` | calls/remaining per provider per month | unique (`provider`,`month`) | Quota counter |
| `llm_usage` | model, tokens, latency, fallback depth | **TTL 30 d** on `ts` | Usage page and evals |
| `app_settings` | model chains, model health | `_id` | Switch models without redeploying |
| `search_events` | per-search summary | – | Cache hit rate, recent searches |

`profile_hash` = hash of role + sorted skills + years. Editing your skills changes the hash, so stale scores are never reused, and no cache invalidation code is needed.

### 3.5 Job source layer

| Order | Provider | Free quota | Key | Notes |
|---|---|---|---|---|
| 1 | JSearch | ~200 / month, hard limit | `RAPIDAPI_KEY` | Google for Jobs: LinkedIn, Naukri (when indexed), Indeed, Glassdoor, company sites |
| 2 | Adzuna | 2,500 / month | `ADZUNA_APP_ID/KEY` | India + 18 countries, salaries |
| 3 | Remotive | ~4 calls / day suggested | none | Remote only, 24 h delay |
| 4 | Arbeitnow | free | none | Mostly EU; filtered by title relevance |
| 5 | Demo | ∞ | none | Fictional dataset, flagged `demo: true` |

**`JobSourceRegistry.search()` step by step**
1. `cache_key = sha256(normalised role + filters)` (min score excluded: it's applied locally). A fresh cache hit returns stored jobs with **zero API calls**.
2. For each provider: skip if no key, if it can't serve the filters (Remotive for on-site jobs), or if this month's quota is spent.
3. Call it with a cleaned query (`search_query()`: "MERN Stack + Python AI Engineer (Remote)" → "MERN Stack Python AI"). One page only.
4. A 429/402/403 response marks the provider exhausted and falls through; network or 5xx errors fall through.
5. Results are deduped (same title+company+location, keeping the LinkedIn copy), filtered to LinkedIn-only or Naukri-only if chosen, stored, and cached.
6. If nothing works, the demo dataset is served.

### 3.6 Agent pipeline (LangGraph)

```
START → search ──(0 jobs)──► END
          │
          ▼
      prefilter → analyzer → matcher → ranker → END
```

| Node | Job | Input → Output | Model |
|---|---|---|---|
| `search` | Fetch jobs via registry | profile, filters → `jobs`, `meta` | none |
| `prefilter` | Keep top 12 by cheap score | `jobs` → `candidates` | none (Python) |
| `analyzer` | Extract required / nice-to-have skills, min years, seniority, summary | `candidates` → `analyses` | **small** (gpt-oss-20b → Gemini Flash-Lite → OpenRouter free) |
| `matcher` | Score fit | `analyses` + profile → `matches` | **mid** (gpt-oss-120b → Gemini Flash → OpenRouter free) |
| `ranker` | Min-score filter, order LinkedIn → Naukri → others, then score | → `ranked` | none |
| `outreach` (separate) | Draft message / cover letter / bullets on click | job + match + profile → draft | **mid** |

How the agents communicate: they don't call each other. Each node reads the shared `PipelineState` and returns only the keys it changes; LangGraph merges them. Services come in through `Runtime[PipelineDeps]`, LangGraph 1.x's typed context, so nodes are pure functions of (state, runtime) and easy to test with fakes. Progress is pushed with `runtime.stream_writer(...)` and streamed with `stream_mode=["custom","updates"]`.

### 3.7 LLM client and why it isn't LiteLLM's Router

`services/llm/client.py` wraps `litellm.acompletion` in an explicit priority loop:

```
for model in chain[tier]:
    skip if: no key · marked unavailable · cooling down after a 429
    call → success: log tokens, mark ok, return
    429            → cool down 60 s, next model
    retired / 404  → mark "unavailable" (persisted, shown in UI), next
    other error    → next
all failed → LLMUnavailableError → node falls back to deterministic logic
```

The plan said "LiteLLM Router". I used LiteLLM's unified API with my own ~80-line loop because the app needs three things Router doesn't give directly: (1) a **strict, user-editable order** saved in Mongo, (2) a **per-model health state** the UI can show, and (3) a **free-only guard** on every model id. It's also simpler to explain and test.

**Fallback order reasoning:** Groq first (fastest, generous per-model daily limits), Gemini second (separate quota, strong JSON), OpenRouter last (only 50 free requests a day).

**Model health / switching.** `health.check_all()` fetches each provider's model list (Groq `/openai/v1/models`, Gemini `models.list`, OpenRouter `/api/v1/models` with price 0). Any configured model missing from its provider's list becomes "Retired or unavailable". The UI shows a banner on every page, and the admin picks a replacement from the free suggestions. `PUT /models` validates through `free_guard` and swaps the chain in memory immediately, with no restart.

### 3.8 Cost optimisation, mapped to code

| Technique | Where | Effect |
|---|---|---|
| Filters sent to the job API | `jsearch.py build_params`, `adzuna.py build_params` | Fewer, more relevant jobs per call |
| 6 h search cache (TTL index) | `registry.py`, `repositories/jobs.py`, `db/mongo.py` | Repeat search = 0 API calls |
| One page per search, manual refresh | `jsearch.py` (`num_pages=1`), refresh button | Bounded quota use |
| Quota counter + skip exhausted | `registry.quota_left`, `usage.py` | Never wastes a call on a dead quota |
| Source fallback chain + demo | `registry.py`, `demo.py` | Always returns something |
| Zero-token pre-filter, top-K = 12 | `text/prefilter.py`, `nodes/prefilter.py` | LLM cost capped regardless of results |
| JD trimming | `text/jd_trimmer.py` | ~50–70% fewer input tokens |
| Small vs mid model tiers | `config.py` chains, `analyzer.py` / `matcher.py` | Cheap model for extraction |
| Batching 4 jobs per call | `analyzer.py`, `matcher.py` | 12 jobs = 3 calls, not 12 (RPM is the binding free-tier limit) |
| Analysis cached per job (all profiles) | `job_analyses` | Second user pays nothing |
| Match cached per (job, profile_hash) | `matches` | Re-run = 0 tokens |
| Lazy outreach + cache | `routes/jobs.py`, `agents/outreach.py` | Drafts only on click, once |
| Strict JSON + `max_tokens` + temperature 0 | `structured.py`, nodes | Short, parseable answers |
| `reasoning_effort="low"` for gpt-oss | `client.py` | Reasoning tokens don't eat the budget |
| Static prompt prefix | `prompts.py` | Provider-side prompt caching can apply |
| Semaphore(3) | `client.py` | Stays under RPM, avoids 429 cascades |
| Cooldown after 429 | `client.py` | Doesn't hammer a limited provider |
| Per-user rate limits | `rate_limit.py`, routes | One visitor can't drain shared quota |

### 3.9 Scoring and anti-hallucination

1. **Skill sets are computed in code**, never by the LLM: `matched = profile ∩ (required ∪ nice)`, `missing = required − profile`, after alias normalisation ("ReactJS" = "react", "MERN" implies MongoDB, Express, React, Node).
2. **Grounding:** any skill the analyzer returns that doesn't literally appear in the posting is dropped (`skills.is_grounded`).
3. **Base score** = 100 × (0.8 × required coverage + 0.2 × nice coverage)^0.75, minus 8 points per missing year of experience (max −25). The exponent was **fitted on hand labels**: MAE went 19.1 → 13.2 (splitting required vs nice) → 7.8 (calibration).
4. **LLM nudge:** the mid model sees the computed sets and returns only `fit_adjustment ∈ [−15, 15]`, seniority fit and a ≤30-word reason. Code clamps it, so the LLM can move a score but never invent it.
5. **Outreach prompts** list only matched skills and say "skills still learning: do not claim", so drafts can't claim skills you don't have.

---

## 4. Frontend (React + Vite, JavaScript)

### 4.1 File map

| File | Use |
|---|---|
| `main.jsx` | Providers: TanStack `QueryClient`, `BrowserRouter`, `AuthProvider`, `ToastProvider`. |
| `App.jsx` | Routes; `RequireAuth` guard; every page lazy-loaded (route-level code splitting). |
| `api/client.js` | `api()` fetch wrapper: base URL, JWT header, JSON, unified `ApiError`, 401 → logout hook. Token in memory + `localStorage` (wrapped in try/catch). |
| `api/endpoints.js` | One function per backend endpoint. |
| `api/search.js` | `streamSearch()` reads the POST response body as a stream; `createSSEParser()` turns arbitrary chunks into `{event, data}` frames. |
| `context/AuthContext.jsx` | `user`, `signIn(mode, form)`, `logout`; restores the session with `/auth/me`. |
| `hooks/useSearchStream.js` | Runs a search; converts SSE events into `stages`, `log`, `results`, `meta`, `status`; `AbortController` for Stop. `reduceProgress()` is a pure reducer (unit-tested). |
| `hooks/queries.js` | TanStack Query hooks for profiles, tracker (optimistic status updates), status, models. |
| `components/agent/AgentThread.jsx` | Chat-style live reasoning trace: one step per agent, the active line shimmers and types out, progress bars, a shortlist funnel, timings, per-step update history. Folds into a one-line summary when done. |
| `components/three/cardPhysics.js` | Card layouts + oriented-box collision (separating-axis test, 15 axes). Layouts are relaxed once; the scene runs the solver every frame so cards push each other aside mid-transition instead of passing through. Unit-tested: every layout is collision-free. |
| `components/agent/DemoThread.jsx` | Scripted replay of a real run through the same reducer + AgentThread, shown on the landing page when scrolled into view. |
| `components/three/GlassCards.jsx` | Photoreal glass job cards (MeshPhysicalMaterial transmission + iridescence, RoomEnvironment studio light, no HDR download). Story mode follows scroll through the pipeline (orbital ring → fetched wall → shortlist → read grid → ranked stack) with a camera move per stage; fan mode is the idle visual. Lazy chunk, pauses off-screen, half-res refraction buffer, static under reduced motion. |
| `components/jobs/JobCard.jsx` | Publisher badge (LinkedIn/Naukri highlighted), animated score ring, matched/missing chips, apply / draft / save / company actions, attribution. Memoised. |
| `components/outreach/OutreachDialog.jsx` | Native `<dialog>` side sheet with `showModal()` and `closedby="any"`. Browser handles focus trap, Esc and focus return; light-dismiss fallback for Safari. Kind and tone controls, editable draft, Copy, LinkedIn recruiter search, HR-link save. |
| `components/filters/FilterPanel.jsx` | All filters; segmented controls built on native radios. |
| `components/search/Composer.jsx`, `profile/SkillInput.jsx` | One composer for the search brief: profile picker, role, years, skills, with Filters and About you folding out inline; chip input with datalist autocomplete. |
| `components/layout/AppShell.jsx` | Sticky nav + `ModelBanner` (warns when an AI step has no working model or there are no keys). |
| `components/ui/*` | `Segmented`, `ScoreRing`, `Toast`, `Logo`. |
| `pages/Landing.jsx` | Hero with 3D constellation; GSAP ScrollTrigger pins the "five agents" section and lights each step while scrolling (inside `gsap.matchMedia` for reduced motion). |
| `pages/SearchPage.jsx` | Filters + profile (left, sticky), pipeline + results (right). Saves the profile before searching, persists filters, sorts results (LinkedIn first / best match). |
| `pages/ModelsPage.jsx` | Per-tier model list with status, Test, reorder, remove, add from the live free list or by id, Save, Restore defaults. |
| `pages/StatusPage.jsx` | Quota meters, AI calls and tokens, cache hit rate, models used, recent searches. |
| `pages/TrackerPage.jsx` | Four-column board with status select, notes and links. |
| `styles/index.css` | Tailwind v4 `@theme` tokens (porcelain paper, ink, cobalt signal, lime, ok/warn/bad; Archivo with its width axis for display), surface/composer/field/btn/chip classes, height-auto `.reveal` disclosure, shimmer text, dialog styles, reduced-motion rules. |

### 4.2 Packages and why

React 19 + Vite (fast dev, ESM build) · react-router-dom 7 (routing) · @tanstack/react-query (server-state cache, invalidation, optimistic updates) · tailwindcss v4 (tokens in CSS via `@theme`) · gsap + @gsap/react (`useGSAP` cleans up automatically; ScrollTrigger for the pinned story) · three + @react-three/fiber (declarative 3D) · lucide-react (icons) · vitest + Testing Library + MSW (tests with a mocked network).

### 4.3 Streaming UI: how live progress works

1. `SearchPage` calls `run({profile_id, filters})`.
2. `streamSearch` POSTs to `/api/search`. `EventSource` can't POST, so it reads `res.body.getReader()` and decodes chunks.
3. `createSSEParser` buffers text and splits on blank lines. Frames can be cut anywhere by the network, which a unit test covers.
4. `progress` events go through `reduceProgress`: the stage becomes active or done, and earlier stages are marked done. They're appended to the log with elapsed time.
5. The `result` event sets results + meta. `error` shows a message. Stop aborts the fetch.

### 4.4 State and data flow

- **Server state** (profiles, tracker, status, models): TanStack Query. Mutations invalidate their query, and tracker status updates are optimistic with rollback.
- **Search state**: local to `useSearchStream`, since it's a stream rather than a cacheable GET.
- **Auth**: context + token in `client.js`. Any 401 triggers `logout`.
- **Per-viewer conveniences**: filters in `localStorage` (try/catch, safe if storage is blocked).

### 4.5 Performance and accessibility

Route and 3D code splitting (the three.js chunk loads only on pages with the scene) · `memo(JobCard)` · skeleton loaders · native `<dialog>`, radio-based segmented controls, labelled inputs, `aria-live` log and toasts, visible focus rings · `prefers-reduced-motion` disables GSAP/3D motion · no horizontal scroll at 390 px (checked with headless Edge).

---

## 5. End-to-end request flow (one search)

1. **UI:** user sets filters (India, hybrid, 1–3 yrs, 7 days, all sources, min 40%) and profile (MERN Stack Developer, react/node/mongodb/python, 2 yrs) and clicks **Search**.
2. **Profile save:** if new or edited, `PUT/POST /profiles` runs first, so outreach can reference `profile_id` later.
3. **`POST /api/search`** (JWT, rate-limited). The route loads the profile, builds `PipelineDeps`, and returns a `StreamingResponse` of `run_pipeline(...)`.
4. **search node →** `registry.search("MERN Stack Developer", filters)`:
   - cache key hit? → return stored jobs (0 API calls)
   - else JSearch with `country=in, date_posted=week, job_requirements=under_3_years_experience` → 10 jobs, quota header 187 → `api_usage` updated → jobs upserted → cache saved.
   - progress: "Querying jsearch…", "Found 10 jobs via jsearch".
5. **prefilter node:** extracts skills with the taxonomy, scores coverage + title similarity + experience → keeps 10 (≤12).
6. **analyzer node:** 4 already cached in `job_analyses` (another profile saw them), 6 new → 2 batched calls to the small model → JSON validated → ungrounded skills dropped → saved.
7. **matcher node:** `matches` cache miss for this `profile_hash` → deterministic base per job → 3 batched calls to the mid model for ±15 nudges → saved.
8. **ranker node:** drops < 40%, sorts LinkedIn (0) → Naukri (1) → others (2), then score.
9. **Stream end:** `result` event with ranked jobs + meta (source, cached, elapsed, last model). A search event is logged for the Usage page.
10. **UI:** pipeline shows all green; cards animate in. User clicks **Draft HR message** → `POST /jobs/{id}/outreach {tone: friendly}` → cache miss → mid model drafts using only matched skills → cached → shown with Copy and "Search recruiters on LinkedIn". User sends it themselves and saves the HR profile link to the tracker.

---

## 6. Services and infrastructure

| Service | Role | Free tier |
|---|---|---|
| Groq | Primary LLM (gpt-oss-20b / 120b) | Per-model RPM/RPD, no card |
| Google AI Studio | LLM backup (Gemini Flash / Flash-Lite) | Per-project limits, no billing |
| OpenRouter | Last LLM backup (`:free` models) | 20 RPM, 50/day |
| JSearch (RapidAPI) | LinkedIn/Naukri via Google for Jobs | ~200/month, hard limit |
| Adzuna | Job backup | 2,500/month |
| Remotive, Arbeitnow | Keyless remote boards | Light use |
| MongoDB Atlas | Storage | M0, 512 MB |
| Hosting (when deployed) | Render/Railway (API), Vercel/Netlify (frontend) | Free tiers |

**Environment variables (names only):** `MONGODB_URI`, `MONGODB_DB`, `JWT_SECRET`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `RAPIDAPI_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `CORS_ORIGINS`, and optional tuning (`JSEARCH_MONTHLY_QUOTA`, `SEARCH_CACHE_TTL_HOURS`, `PREFILTER_TOP_K`, …). Frontend: `VITE_API_URL` (empty in dev; the Vite proxy forwards `/api`), `API_PORT` (dev proxy target).

**Run locally:** see README. **Deploy:** backend as a web service (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`) with env vars set; frontend `npm run build` with `VITE_API_URL=https://<api-host>`; add the frontend origin to `CORS_ORIGINS`; set Atlas network access.

**Testing:** 67 backend tests (unit: text, scoring, guard, security, providers via respx, registry fallback/quota/cache, LLM fallback/cooldown/retired-model/repair, health checks, graph nodes, outreach; integration: full API through ASGI with SSE parsing). 12 frontend tests (SSE parser, reducer, components, dialog, auth, banner). Opt-in live tests. Evals in `backend/evals`.

---

## 7. Design decisions and trade-offs

- **Aggregator APIs instead of scraping LinkedIn/Naukri.** Neither offers a public jobs API, and scraping breaks their terms, gets IPs banned and breaks when the HTML changes. JSearch (Google for Jobs) legally carries LinkedIn and some Naukri postings. Trade-off: Naukri coverage depends on Google's index, and the app says so instead of hiding it.
- **Manual sending only.** Auto-messaging recruiters gets accounts flagged as spam and breaks platform rules. The app drafts and links; the human sends.
- **Filters before search.** Filters go into the API request, so one call returns relevant jobs, which saves quota and LLM tokens downstream.
- **Hybrid scoring.** Pure LLM scores drift and can hallucinate skills; pure keyword scores miss seniority and domain. Code owns the facts, the LLM owns judgement, with a bounded say.
- **Own fallback loop over LiteLLM Router** (see 3.7): visible health, editable order, free-only guard.
- **SSE over WebSockets.** Traffic is one-way (server → client) and short-lived; SSE is plain HTTP, works through proxies and needs no extra server state.
- **In-memory DB fallback.** The app runs before Atlas is configured; tests need no database server.
- **Free-tier limits handled by:** caching at three levels, quotas tracked and skipped, fallbacks for both jobs and models, batching, a demo dataset, and a UI that tells the user what's happening.

---

## 8. Interview Q&A

1. **Why didn't you scrape LinkedIn?** No public API, scraping breaks LinkedIn's terms, accounts and IPs get banned, and it breaks whenever the HTML changes. I used JSearch, which reads Google for Jobs and legally includes LinkedIn postings, and I rank LinkedIn results first.

2. **How did you reduce API and LLM costs?** Three layers. Fewer calls: filters in the API request, a 6-hour cache, one page per search, a quota counter. Fewer jobs reach the LLM: a zero-token Python pre-filter keeps the top 12. Fewer tokens per job: trimmed descriptions, batching 4 jobs per call, small model for extraction, strict JSON, and caches per job and per (job, profile). A repeated search costs zero API calls and zero LLM calls; the eval table shows it.

3. **How do your agents communicate, and what does LangGraph do?** They share a typed state. Each node returns only the keys it changes and LangGraph merges them, runs nodes in order, handles the conditional "no jobs → end" edge, and streams custom progress events. Dependencies come through LangGraph's runtime context, so nodes are testable pure functions.

4. **How do you score a match, and how do you know it's accurate?** Code computes matched and missing skills and a calibrated coverage score. The LLM adds at most ±15 for seniority and domain. I hand-labelled 20 jobs and measured mean absolute error: it went from 19.1 to 7.8 after separating nice-to-have skills and fitting a calibration curve, with 90% of scores within ±15 of my label.

5. **What happens when a job API hits its rate limit?** A 429/402/403 marks that provider exhausted for the month in `api_usage`, and the registry moves to the next source: JSearch → Adzuna → Remotive → Arbeitnow → demo data. The UI shows which source answered and how many searches are left.

6. **What happens when an LLM is rate-limited or retired?** A 429 puts that model in a 60-second cooldown and the next model in the chain answers. A "decommissioned" or 404 error marks it unavailable, which is persisted, shown on the Models page and in a banner. The admin can pick a free replacement from the provider's live list without a redeploy. If every model fails, the pipeline still returns keyword-based scores and template drafts.

7. **How do you stop the LLM from inventing skills or job details?** Skill sets come from set operations in code. Any skill the analyzer returns that isn't literally in the posting is dropped. The matcher can only nudge a score within ±15. Outreach prompts list only matched skills and tell the model not to claim the missing ones. All output is schema-validated JSON.

8. **How do you guarantee only free models are used?** `free_guard.check_free()` is applied when chains load from the DB, when the admin saves them (422 on violation) and before a test call. Gemini Pro, non-`:free` OpenRouter models and unknown providers are rejected.

9. **Why SSE instead of WebSockets or polling?** It's one-way, short-lived progress. SSE is plain HTTP, streams through the Vite proxy and load balancers, and needs no connection registry. I used POST with a fetch-stream reader because the request carries a body, and wrote a parser that handles frames split across chunks.

10. **Why MongoDB?** Jobs from different providers have uneven fields, and documents fit that. TTL indexes give the search cache and log expiry for free, and compound unique indexes make the caches upsert-safe.

11. **How is auth handled?** bcrypt-hashed passwords, a stateless JWT (HS256, 24 h) in the `Authorization` header, a `current_user` dependency on protected routes, every query scoped by `user_id`, the same error for unknown email and wrong password, and per-user rate limits.

12. **How did you test it?** Pytest with an in-memory Mongo, respx for HTTP and a scriptable fake for `litellm.acompletion`: unit tests per module plus API integration tests that parse the SSE stream. Vitest + MSW for the frontend. Opt-in live tests and an eval script for real behaviour. No test can spend real quota, because the conftest blanks every key.

13. **How would you scale this to 10,000 users?** Run uvicorn workers behind a load balancer (state is in Mongo, auth is stateless). Move cooldowns, rate limits and model health to Redis so workers share them. Put searches on a queue (Celery/Arq) with the SSE endpoint reading progress from Redis pub/sub. Shared job and analysis caches make cost grow with *distinct jobs*, not users. Paid job APIs or partnerships would be needed at that volume, plus per-user quotas.

14. **Why a custom LLM fallback loop instead of LiteLLM Router?** I needed a strict user-editable order, per-model health for the UI and a free-only guard. LiteLLM still gives one call shape for all providers; my loop adds about 80 tested lines of policy on top.

15. **What does the pre-filter do, and why not send everything to the LLM?** It scores skill coverage (50%), fuzzy title similarity (35%) and experience fit (15%) in microseconds with no tokens, and keeps the top 12. LLM cost stays fixed whether the API returns 10 jobs or 100.

16. **How do caches stay correct when the profile changes?** Match keys include `profile_hash` (role + sorted skills + years). Any edit produces a new hash, so old scores simply aren't looked up. Job analyses don't depend on the profile, so they're shared.

17. **How is the frontend organised?** Pages compose feature components. All HTTP goes through `api/`. Server state lives in TanStack Query, the search stream in a custom hook with a pure reducer, auth in context. The heavy 3D and GSAP code is lazy-loaded per route.

18. **How did you handle accessibility with so much animation?** Native `<dialog>` (focus trap, Esc, focus return for free), radio-based segmented controls, labelled fields, `aria-live` progress and toasts, visible focus rings. GSAP runs inside `matchMedia("(prefers-reduced-motion: no-preference)")`, the 3D scene renders once and stays still for reduced motion, and CSS animations are disabled too.

19. **What would you improve next?** A Redis-backed job queue, embedding-based skill similarity (so "Postgres" partially matches "MySQL"), more labelled eval data, Greenhouse/Lever company watchlists, and email alerts for new high-score matches.

20. **What was the hardest bug?** Two stand out. A library mismatch: mongomock's `bulk_write` breaks with current PyMongo operation objects, so the in-memory adapter translates them. And query quality: sending the raw role "MERN Stack + Python AI Engineer" to job boards returned almost nothing, which a live smoke run caught; `search_query()` now cleans it.
