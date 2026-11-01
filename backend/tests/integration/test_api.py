"""End-to-end API tests through the real FastAPI app (in-memory DB, mocked externals)."""

import json
from urllib.parse import quote

import httpx
import pytest
import respx

from app.main import create_app, init_services


@pytest.fixture
async def client(db):
    app = create_app()
    await init_services(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        c.app = app
        yield c
    await app.state.http.aclose()


async def register(client, email="sam@example.com", name="Sam"):
    r = await client.post("/api/auth/register", json={"name": name, "email": email, "password": "password123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]


PROFILE = {"name": "Main", "target_role": "MERN Stack Developer", "skills": ["ReactJS", "node", "MongoDB", "Python"],
           "years_experience": 2, "description": "Full stack dev"}


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


async def search(client, headers, profile_id, **filters):
    with respx.mock(assert_all_called=False) as mock:
        mock.route(host="test").pass_through()
        mock.get("https://remotive.com/api/remote-jobs").mock(return_value=httpx.Response(200, json={"jobs": []}))
        mock.get("https://www.arbeitnow.com/api/job-board-api").mock(return_value=httpx.Response(200, json={"data": []}))
        r = await client.post("/api/search", headers=headers, json={"profile_id": profile_id, "filters": filters})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    return parse_sse(r.text)


class TestAuth:
    async def test_register_login_me(self, client):
        headers, user = await register(client)
        assert user["is_admin"] is True  # first account
        _, second = await register(client, "b@example.com", "B")
        assert second["is_admin"] is False

        r = await client.post("/api/auth/login", json={"email": "SAM@example.com", "password": "password123"})
        assert r.status_code == 200
        assert (await client.get("/api/auth/me", headers=headers)).json()["email"] == "sam@example.com"

    async def test_errors(self, client):
        await register(client)
        dup = await client.post("/api/auth/register", json={"name": "x", "email": "sam@example.com", "password": "password123"})
        assert dup.status_code == 409 and dup.json()["error"]["code"] == "conflict"
        bad = await client.post("/api/auth/login", json={"email": "sam@example.com", "password": "nope"})
        assert bad.status_code == 401
        assert (await client.get("/api/profiles")).status_code == 401
        short = await client.post("/api/auth/register", json={"name": "x", "email": "z@example.com", "password": "123"})
        assert short.status_code == 422 and short.json()["error"]["details"][0]["field"] == "password"


class TestProfiles:
    async def test_crud_and_isolation(self, client):
        headers, _ = await register(client)
        other, _ = await register(client, "o@example.com", "O")
        p = (await client.post("/api/profiles", headers=headers, json=PROFILE)).json()
        assert p["skills"] == ["react", "node.js", "mongodb", "python"]  # normalised
        assert len((await client.get("/api/profiles", headers=headers)).json()) == 1
        assert (await client.get(f"/api/profiles/{p['id']}", headers=other)).status_code == 404  # other user's

        upd = await client.put(f"/api/profiles/{p['id']}", headers=headers, json={**PROFILE, "target_role": "AI Engineer"})
        assert upd.json()["target_role"] == "AI Engineer"
        assert (await client.delete(f"/api/profiles/{p['id']}", headers=headers)).status_code == 204
        skills = (await client.get("/api/profiles/skills/suggestions")).json()
        js = next(x for x in skills if x["name"] == "javascript")
        assert {"js", "es6"} <= set(js["aliases"])
        roles = (await client.get("/api/profiles/roles/suggestions")).json()
        assert any(r["role"] == "SAP Security Consultant" and "sap security" in r["skills"] for r in roles)


class TestSearchFlow:
    async def test_search_stream_outreach_tracker_status(self, client, fake_llm):
        headers, _ = await register(client)
        profile = (await client.post("/api/profiles", headers=headers, json=PROFILE)).json()

        events = await search(client, headers, profile["id"], min_score=0)
        kinds = [k for k, _ in events]
        assert kinds[0] == "progress" and kinds[-1] == "result"
        result = events[-1][1]
        jobs, meta = result["jobs"], result["meta"]
        assert meta["demo"] is True and jobs and jobs[0]["match"]["method"] == "llm"
        assert {"search", "prefilter", "analyzer", "matcher", "ranker"} <= {d.get("stage") for _, d in events}

        job_id = jobs[0]["job"]["id"]
        enc = quote(job_id, safe="")
        assert (await client.get(f"/api/jobs/{enc}", headers=headers)).json()["id"] == job_id
        link = (await client.get(f"/api/jobs/{enc}/hr-search-link", headers=headers)).json()
        assert "linkedin.com/search/results/people" in link["url"]

        body = {"profile_id": profile["id"], "tone": "friendly", "kind": "message"}
        d1 = (await client.post(f"/api/jobs/{enc}/outreach", headers=headers, json=body)).json()
        d2 = (await client.post(f"/api/jobs/{enc}/outreach", headers=headers, json=body)).json()
        assert d1["method"] == "llm" and not d1["cached"] and d2["cached"]

        t = await client.post(f"/api/tracker?profile_hash={meta['profile_hash']}", headers=headers,
                              json={"job_id": job_id, "status": "saved"})
        assert t.status_code == 201 and t.json()["score"] == jobs[0]["match"]["score"]
        p = await client.patch(f"/api/tracker/{enc}", headers=headers,
                               json={"status": "applied", "hr_profile_url": "https://www.linkedin.com/in/someone"})
        assert p.json()["status"] == "applied"
        assert len((await client.get("/api/tracker", headers=headers)).json()) == 1
        assert (await client.delete(f"/api/tracker/{enc}", headers=headers)).status_code == 204

        # repeat search is served from cache
        again = await search(client, headers, profile["id"])
        assert again[-1][1]["meta"]["match_cache_hits"] == len(jobs)

        status = (await client.get("/api/status", headers=headers)).json()
        assert status["database"] == "memory" and status["llm"]["calls_24h"] > 0
        assert {q["provider"] for q in status["job_sources"]} == {"jsearch", "adzuna", "remotive", "arbeitnow"}


class TestModels:
    async def test_admin_can_switch_models_free_only(self, client):
        admin, _ = await register(client)
        user, _ = await register(client, "u@example.com", "U")
        rep = (await client.get("/api/models", headers=user)).json()
        assert set(rep["tiers"]) == {"small", "mid"} and rep["providers"]["groq"] is False

        chains = {"small": ["groq/openai/gpt-oss-20b"], "mid": ["gemini/gemini-2.5-flash"]}
        assert (await client.put("/api/models", headers=user, json=chains)).status_code == 403
        ok = await client.put("/api/models", headers=admin, json=chains)
        assert ok.status_code == 200 and ok.json()["tiers"]["mid"][0]["model"] == "gemini/gemini-2.5-flash"

        paid = await client.put("/api/models", headers=admin, json={"small": ["gemini/gemini-2.5-pro"], "mid": chains["mid"]})
        assert paid.status_code == 422 and "billing" in paid.text
        rejected = (await client.post("/api/models/test", headers=admin, json={"model": "openai/gpt-4o"})).json()
        assert rejected["status"] == "rejected"
        reset = (await client.post("/api/models/reset", headers=admin)).json()
        assert len(reset["tiers"]["small"]) == 3
