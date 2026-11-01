import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

export const JOB = {
  job: {
    id: "jsearch:abc==", source: "jsearch", publisher: "LinkedIn", title: "MERN Stack Developer", company: "Nimbus Labs",
    location: "Chennai, India", work_type: "hybrid", job_type: "FULLTIME", posted_at: new Date().toISOString(),
    closes_at: null, apply_url: "https://apply.test/1", company_url: "https://nimbus.test", attribution: null,
  },
  match: { score: 82, matched_skills: ["react", "mongodb"], missing_skills: ["aws"], reasoning: "Strong overlap.", method: "llm" },
  analysis: { required_skills: ["react", "mongodb", "aws"] },
  priority: 0,
};

export const handlers = [
  http.post("/api/auth/login", async ({ request }) => {
    const body = await request.json();
    if (body.password !== "password123") {
      return HttpResponse.json({ error: { code: "unauthorized", message: "Incorrect email or password" } }, { status: 401 });
    }
    return HttpResponse.json({ access_token: "tok", user: { id: "u1", name: "Sam", email: body.email, is_admin: true } });
  }),
  http.get("/api/auth/me", () => HttpResponse.json({ id: "u1", name: "Sam", email: "s@x.io", is_admin: true })),
  http.post("/api/jobs/:id/outreach", () =>
    HttpResponse.json({ job_id: JOB.job.id, tone: "short", kind: "message", subject: "Hi", body: "Hello recruiter, I fit this role.", method: "llm", model: "groq/openai/gpt-oss-120b", cached: false }),
  ),
  http.get("/api/models", () =>
    HttpResponse.json({
      tiers: { small: [{ model: "groq/a", status: "unavailable", detail: "retired" }], mid: [{ model: "groq/b", status: "ok" }] },
      tier_ok: { small: false, mid: true },
      providers: { groq: true, gemini: false, openrouter: false },
      suggestions: {},
    }),
  ),
];

export const server = setupServer(...handlers);
