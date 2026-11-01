# Setting up your free accounts and keys

Every service below is **free with no credit or debit card**. Free tiers have limits (listed for each), which the app works around with caching and fallbacks. Checked in October 2026. Free plans change, so if a signup page ever asks for a card, stop and skip that service: the app keeps working with the others.

All keys go in **`backend/.env`**. Create it once:

```bash
cd backend
copy .env.example .env      # Windows (use `cp` on macOS/Linux)
```

After editing `.env`, restart the backend. Then open **AI models** in the app and press **Check models now** to confirm the keys are picked up.

| # | Account | Needed for | `.env` variables | Required? |
|---|---------|-----------|------------------|-----------|
| 1 | Groq | Main AI (fastest) | `GROQ_API_KEY` | Recommended |
| 2 | Google AI Studio (Gemini) | AI backup #1 | `GEMINI_API_KEY` | Recommended |
| 3 | OpenRouter | AI backup #2 | `OPENROUTER_API_KEY` | Optional |
| 4 | RapidAPI (JSearch) | LinkedIn and Naukri jobs | `RAPIDAPI_KEY` | Recommended |
| 5 | Adzuna | Job backup (India + 18 countries) | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Optional |
| 6 | MongoDB Atlas | Permanent storage | `MONGODB_URI` | Optional (memory DB otherwise) |
| 7 | JWT secret | Login tokens | `JWT_SECRET` | Required before deploying |

With no keys at all the app still runs: it uses Remotive and Arbeitnow (no key needed) or the demo jobs, keyword-only scoring and template drafts.

---

## 1. Groq (AI, primary)

**Free tier:** per-model limits. For example, `openai/gpt-oss-20b` and `openai/gpt-oss-120b` allow about 30 requests a minute and 1,000+ a day. No card.

1. Go to **https://console.groq.com** and sign up with Google, GitHub or email.
2. In the left menu open **API Keys**, then **Create API Key**.
3. Name it `job-copilot`, then copy the key (starts with `gsk_`). It's shown only once.
4. In `backend/.env`: `GROQ_API_KEY=gsk_...`

> Groq retired its Llama models for free users in August 2026. The app defaults to the `gpt-oss` models, and the Models page flags any model Groq retires later.

## 2. Google AI Studio / Gemini (AI, backup #1)

**Free tier:** Gemini Flash and Flash-Lite models. Limits are per project. No billing account needed.

1. Go to **https://aistudio.google.com** and sign in with a **personal Gmail** account. Workspace (work/school) accounts may be restricted.
2. Click **Get API key**, then **Create API key**. Let it create a new project.
3. Copy the key (starts with `AIza`).
4. In `backend/.env`: `GEMINI_API_KEY=AIza...`

> **Don't** click "Set up billing" on this project. Enabling billing removes the free tier for it. The app's free-only guard also refuses Gemini Pro models.

## 3. OpenRouter (AI, backup #2)

**Free tier:** models whose id ends in `:free`, at 20 requests a minute and 50 a day. Works with a $0 balance.

1. Go to **https://openrouter.ai** and sign up with email, Google or GitHub.
2. Open **Keys** (top-right menu), then **Create Key**. Leave the credit limit empty.
3. Copy the key (starts with `sk-or-`).
4. In `backend/.env`: `OPENROUTER_API_KEY=sk-or-...`

> Don't buy credits. The app only calls `:free` models, and a negative balance can block even free models.

## 4. RapidAPI: JSearch (LinkedIn and Naukri jobs)

**Free tier:** the **Basic** plan is about 200 requests a month with a **hard limit**. Requests stop at the limit instead of being billed. No card.

1. Go to **https://rapidapi.com** and sign up.
2. Search for **JSearch** (by OpenWeb Ninja / letscrape) and open **Pricing**.
3. Choose **Basic ($0.00 / mo)** and click **Subscribe**. If it asks for a card, the plan has changed: skip JSearch and use Adzuna.
4. Open the **Endpoints** tab and copy the `X-RapidAPI-Key` value from the code sample.
5. In `backend/.env`: `RAPIDAPI_KEY=...`

> JSearch reads Google for Jobs, which includes LinkedIn postings and some Naukri postings. Naukri coverage depends on what Google indexes. The app ranks LinkedIn jobs first and Naukri second. Each identical search is cached for 6 hours, so it costs one request.

## 5. Adzuna (job backup)

**Free tier:** 25 calls a minute, 250 a day, 2,500 a month. Free registration.

1. Go to **https://developer.adzuna.com** and click **Register**.
2. Confirm your email, then open **Dashboard** and **API Access Details**.
3. Copy the **Application ID** and **Application Key**.
4. In `backend/.env`:
   ```
   ADZUNA_APP_ID=...
   ADZUNA_APP_KEY=...
   ```

> Adzuna's terms require crediting them. The app shows "Jobs by Adzuna" on those listings.

## 6. MongoDB Atlas (storage)

**Free tier:** M0 cluster, 512 MB, free forever. No card.

1. Go to **https://www.mongodb.com/cloud/atlas/register** and sign up.
2. Create a cluster and choose **M0 Free**. Pick a region near you (for example Mumbai, `ap-south-1`).
3. **Database Access**, then **Add New Database User**: username and an auto-generated password. Copy the password.
4. **Network Access**, then **Add IP Address**: **Add current IP address**. Use `0.0.0.0/0` only if you deploy to a host with changing IPs.
5. **Database**, then **Connect**, **Drivers**, **Python**, and copy the connection string:
   `mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
6. Replace `<password>` (URL-encode special characters such as `@` → `%40`).
7. In `backend/.env`: `MONGODB_URI=mongodb+srv://...`

Collections and indexes are created automatically on first start.

## 7. JWT secret

Generate a random secret and paste it in:

```bash
python -c "import secrets;print(secrets.token_urlsafe(48))"
```

`JWT_SECRET=<the output>`

---

## Check that it works

```bash
cd backend
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on macOS/Linux)
python -m scripts.check_models  # lists every model as OK / retired / no key (uses zero tokens)
pytest -m live                  # one real call per configured provider
```

## If a model is retired later

Open **AI models** in the app. A retired model shows **Retired or unavailable** and a banner appears on every page. Pick a replacement from **Add a free model from the live list**, move it to the top, and press **Save model order**. No restart or code change needed.
