import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createSSEParser } from "../api/search";
import { reduceProgress, STAGES } from "../hooks/useSearchStream";
import { sortResults } from "../pages/SearchPage";
import { scoreTone, publisherKind, describeFilters, DEFAULT_FILTERS } from "../utils/format";
import AgentThread, { summarize } from "../components/agent/AgentThread";
import { hrSearchUrl } from "../utils/links";
import JobCard from "../components/jobs/JobCard";
import Segmented from "../components/ui/Segmented";
import OutreachDialog from "../components/outreach/OutreachDialog";
import { ModelBanner } from "../components/layout/AppShell";
import AuthPage from "../pages/AuthPage";
import { AuthProvider } from "../context/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import { JOB, server } from "./server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function wrap(ui, { route = "/" } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[route]}>
        <AuthProvider>
          <ToastProvider>{ui}</ToastProvider>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SSE parser", () => {
  it("handles frames split across arbitrary chunk boundaries", () => {
    const feed = createSSEParser();
    const raw = 'event: progress\ndata: {"stage":"search","message":"Hi"}\n\nevent: result\ndata: {"jobs":[1,2]}\n\n';
    const events = [];
    for (let i = 0; i < raw.length; i += 7) events.push(...feed(raw.slice(i, i + 7)));
    expect(events).toEqual([
      { event: "progress", data: { stage: "search", message: "Hi" } },
      { event: "result", data: { jobs: [1, 2] } },
    ]);
  });

  it("normalises CRLF and ignores malformed frames", () => {
    const feed = createSSEParser();
    expect(feed('event: x\r\ndata: {bad\r\n\r\nevent: y\r\ndata: {"ok":1}\r\n\r\n')).toEqual([{ event: "y", data: { ok: 1 } }]);
  });
});

describe("pipeline progress", () => {
  const empty = Object.fromEntries(STAGES.map((s) => [s, { status: "waiting" }]));

  it("marks earlier stages done when a later stage starts", () => {
    const s = reduceProgress(empty, { stage: "analyzer", message: "Reading", progress: 2, total: 12 });
    expect(s.search.status).toBe("done");
    expect(s.prefilter.status).toBe("done");
    expect(s.analyzer).toMatchObject({ status: "active", progress: 2, total: 12 });
    expect(s.ranker.status).toBe("waiting");
  });

  it("ignores unknown stages", () => {
    expect(reduceProgress(empty, { stage: "start", message: "x" })).toBe(empty);
  });
});

describe("helpers", () => {
  it("sorts by score only when asked", () => {
    const a = { match: { score: 40 } }, b = { match: { score: 90 } };
    expect(sortResults([a, b], "priority")).toEqual([a, b]);
    expect(sortResults([a, b], "score")).toEqual([b, a]);
  });
  it("labels scores and publishers", () => {
    expect(scoreTone(80).label).toBe("Strong fit");
    expect(scoreTone(10).label).toBe("Long shot");
    expect(publisherKind("Naukri.com")).toBe("naukri");
    expect(hrSearchUrl("Acme Labs")).toContain("keywords=Acme%20Labs%20recruiter");
  });
});

describe("components", () => {
  it("Segmented is a keyboard-accessible radio group", async () => {
    const onChange = vi.fn();
    render(<Segmented label="Tone" value="a" onChange={onChange} options={[{ value: "a", label: "A" }, { value: "b", label: "B" }]} />);
    expect(screen.getByRole("group", { name: "Tone" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "B" }));
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("JobCard shows score, matched and missing skills, and actions", async () => {
    const onDraft = vi.fn();
    wrap(<JobCard item={JOB} onDraft={onDraft} onTrack={() => {}} tracked={false} />);
    expect(screen.getByRole("img", { name: /match score 82/i })).toBeInTheDocument();
    expect(screen.getByText("LinkedIn")).toBeInTheDocument();
    expect(screen.getByText("aws")).toHaveClass("chip-miss");
    expect(screen.getByRole("link", { name: /apply/i })).toHaveAttribute("href", "https://apply.test/1");
    await userEvent.click(screen.getByRole("button", { name: /draft hr message/i }));
    expect(onDraft).toHaveBeenCalledWith(JOB);
  });

  it("OutreachDialog writes a draft on demand and copies it", async () => {
    const writeText = vi.fn().mockResolvedValue();
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    wrap(<OutreachDialog item={JOB} profileId="p1" onClose={() => {}} onSaveHr={() => {}} />);
    expect(screen.getByRole("link", { name: /search recruiters on linkedin/i }).href).toContain("Nimbus%20Labs");
    await userEvent.click(screen.getByRole("button", { name: /write draft/i }));
    const box = await screen.findByLabelText(/your draft/i);
    expect(box.value).toContain("Hello recruiter");
    await userEvent.click(screen.getByRole("button", { name: /^copy$/i }));
    expect(writeText).toHaveBeenCalledWith(box.value);
    expect(await screen.findByText("Copied to clipboard")).toBeInTheDocument();
  });

  it("ModelBanner warns when a model tier has no working model", async () => {
    wrap(<ModelBanner />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/no working ai model for the small step/i);
    expect(screen.getByRole("link", { name: /switch models/i })).toHaveAttribute("href", "/app/models");
  });
});

describe("agent thread", () => {
  const stages = {
    search: { status: "done", count: 47 }, prefilter: { status: "done", count: 12 },
    analyzer: { status: "active", progress: 4, total: 12 }, matcher: { status: "waiting" }, ranker: { status: "waiting" },
  };
  const log = [
    { stage: "search", message: "Found 47 jobs via JSearch", t: 900 },
    { stage: "prefilter", message: "Kept top 12 of 47 candidates", t: 1200 },
    { stage: "analyzer", message: "Extracting required skills…", t: 1500 },
  ];

  it("shows each step with its state, live progress and the finished steps' messages", () => {
    render(<AgentThread stages={stages} log={log} status="running" startedAt={performance.now()} />);
    expect(screen.getByRole("button", { name: /hide steps/i })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("heading", { name: /searching live job boards, done/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /reading the job descriptions, in progress/i })).toBeInTheDocument();
    expect(screen.getByText("4 of 12")).toBeInTheDocument();
    expect(screen.getByText("Kept top 12 of 47 candidates")).toBeInTheDocument();
  });

  it("folds into a one-line summary when finished", () => {
    const done = { ...stages, analyzer: { status: "done" }, matcher: { status: "done", progress: 12 }, ranker: { status: "done" } };
    render(<AgentThread stages={done} log={log} status="done" elapsedMs={6200} />);
    expect(screen.getByRole("button", { name: /show steps/i })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("Searched 47 live jobs, shortlisted 12 and scored them in 6.2s.")).toBeInTheDocument();
  });

  it("summarises partial runs and filters in plain words", () => {
    expect(summarize({ search: { count: 1 }, prefilter: {}, matcher: {} }, 800)).toBe("Searched 1 live job in 0.8s.");
    expect(describeFilters(DEFAULT_FILTERS)).toBe("India, any work type, posted in the last 7 days");
  });
});

describe("auth", () => {
  it("shows the server error on a wrong password", async () => {
    wrap(<AuthPage mode="login" />, { route: "/login" });
    await userEvent.type(screen.getByLabelText("Email"), "sam@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password");
  });

  it("stores the token after signing in", async () => {
    wrap(<AuthPage mode="login" />, { route: "/login" });
    await userEvent.type(screen.getByLabelText("Email"), "sam@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "password123");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(localStorage.getItem("jhc.token")).toBe("tok"));
  });
});
