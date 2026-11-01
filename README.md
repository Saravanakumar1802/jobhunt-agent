# Job Hunt Copilot

An AI agent pipeline that finds live job openings (LinkedIn first, Naukri second), scores how well each one fits your skills, and drafts the message to HR. Every external service runs on a free tier with no card.

**Stack:** React 19 (Vite, JavaScript) · FastAPI · LangGraph · LiteLLM · MongoDB Atlas · Three.js · GSAP

```
React (Vite)  ──REST + SSE──►  FastAPI
                                 ├─ Job sources:  JSearch (LinkedIn/Naukri) → Adzuna → Remotive → Arbeitnow → demo
                                 ├─ LangGraph:    search → pre-filter → analyzer → matcher → ranker
                                 ├─ LLM client:   Groq → Gemini → OpenRouter (:free only), health-checked
                                 └─ MongoDB:      users, profiles, jobs, caches, tracker, usage
```

## Quick start

Needs Python 3.12+ and Node 20+.

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate                 # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env                 # add keys later; see docs/SETUP_KEYS.md
uvicorn app.main:app --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

If port 8000 is taken, run the backend with `--port 8001` and start the frontend with `API_PORT=8001` set (PowerShell: `$env:API_PORT='8001'; npm run dev`).

The first account you register becomes the admin, who can change AI models. With no keys the app still works: it uses keyless job boards or demo jobs, keyword scoring and template drafts.

## Keys

See **[docs/SETUP_KEYS.md](docs/SETUP_KEYS.md)** for step-by-step signup for each free account: Groq, Gemini, OpenRouter, JSearch, Adzuna, MongoDB Atlas.

## Tests

```bash
cd backend && pytest            # 67 tests: unit + API integration, all external calls mocked
cd backend && pytest -m live    # opt-in smoke tests against real APIs (uses your keys)
cd backend && ruff check .
cd frontend && npm test -- --run && npm run lint && npm run build
```

## Evaluation (20 hand-labelled jobs, `python -m evals.run_evals`)

| Metric | Value |
|---|---|
| Score MAE vs hand labels (deterministic path, no LLM) | 7.8 |
| Scores within ±15 of label | 90% |
| Skill extraction precision / recall | 97% / 99% |
| Job API calls for 2 identical searches | 1 (second from cache) |
| LLM calls on a repeated search | 0 (analysis + match caches) |

Run `python -m evals.run_evals --llm` after adding keys to measure the hybrid LLM path. Full output is in [backend/evals/RESULTS.md](backend/evals/RESULTS.md).

## Docs

- **[CODE_OVERVIEW.md](CODE_OVERVIEW.md)**: how everything works, file by file, with interview Q&A
- **[docs/SETUP_KEYS.md](docs/SETUP_KEYS.md)**: creating the free accounts
