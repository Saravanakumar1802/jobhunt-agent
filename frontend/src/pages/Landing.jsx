/**
 * Public landing page. The glass cards stay pinned behind the hero and four story steps;
 * scroll position drives their layout and the camera through the stages the pipeline runs:
 * orbital ring → fetched → shortlisted → read → ranked.
 *
 * Motion: Lenis smooth scroll feeds ScrollTrigger. Everything is scrubbed to scroll except
 * the one hero entrance. All of it is skipped under prefers-reduced-motion, and the blur filters are
 * left out on small screens, where re-filtering every scrolled frame costs more than it shows.
 */
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import Lenis from "lenis";
import "lenis/dist/lenis.css";
import { ArrowDown, ArrowRight } from "lucide-react";
import Logo from "../components/ui/Logo";
import DemoThread from "../components/agent/DemoThread";

gsap.registerPlugin(useGSAP, ScrollTrigger);
// Phones resize the viewport as the address bar slides away; don't recompute every trigger when that happens.
ScrollTrigger.config({ ignoreMobileResize: true });
const GlassCards = lazy(() => import("../components/three/GlassCards"));

const STEPS = [
  {
    title: "Search",
    lead: "Pulls every live opening that matches your filters.",
    body: "LinkedIn postings come first and Naukri second. If a source runs out of free quota, Adzuna and remote job boards take over.",
    stat: ["1", "API call per search. Repeats come from a six-hour cache."],
  },
  {
    title: "Shortlist",
    lead: "Throws out the obvious misses before any AI runs.",
    body: "Every job is scored against your skills in plain Python. Only the best dozen move on, so the free AI limits last.",
    stat: ["0", "AI tokens spent on this step."],
  },
  {
    title: "Read",
    lead: "Reads each posting for what it really asks for.",
    body: "A small, fast model lists the required and nice-to-have skills, four jobs per call. Skills that aren't in the posting are thrown out.",
    stat: ["4", "jobs read per AI call."],
  },
  {
    title: "Rank",
    lead: "Scores your fit and puts the best on top.",
    body: "Your score comes from the skills you have and the ones you're missing. A larger model adjusts it for seniority, then LinkedIn jobs are ranked first.",
    stat: ["±15", "points is the most the AI can move a score."],
  },
];

const SOURCES = [
  ["LinkedIn", "Through JSearch, which reads Google for Jobs. Always ranked first."],
  ["Naukri", "Naukri listings that Google for Jobs carries. Ranked second."],
  ["Adzuna", "India and 18 other countries, with salary data when it's listed."],
  ["Remotive and Arbeitnow", "Remote roles, used when the others hit their monthly limit."],
];

const FREE = ["Groq", "Google Gemini", "OpenRouter", "JSearch", "Adzuna", "MongoDB Atlas"];
const BAND = [
  ["Search", "Shortlist", "Read", "Rank", "Draft", "Apply"],
  ["LinkedIn", "Naukri", "Adzuna", "Remotive", "Arbeitnow", "Groq", "Gemini"],
];
const WATCH_TITLE = "Watch it think, step by step.";

function Band({ words, className }) {
  // Repeated so the row never runs out while it slides.
  const row = [...words, ...words, ...words];
  return (
    <div className={`band-row flex w-max items-center gap-8 whitespace-nowrap sm:gap-12 ${className}`} aria-hidden>
      {row.map((w, i) => (
        <span key={i} className="flex items-center gap-8 sm:gap-12">
          <span className={`font-wide text-[clamp(3rem,9vw,8rem)] font-bold leading-none ${i % 2 ? "text-outline" : "text-ink-950"}`}>{w}</span>
          <span className="size-3 rotate-45 rounded-[3px] bg-lime-300 sm:size-4" />
        </span>
      ))}
    </div>
  );
}

export default function Landing() {
  const root = useRef(null);
  const story = useRef(null);
  const hud = useRef(null);
  const progress = useRef(0);
  const [storyVisible, setStoryVisible] = useState(true);

  // Stop rendering the 3D scene once it has scrolled out of view.
  useEffect(() => {
    const io = new IntersectionObserver(([e]) => setStoryVisible(e.isIntersecting));
    io.observe(story.current);
    return () => io.disconnect();
  }, []);

  // Smooth, inertial scrolling that stays in sync with ScrollTrigger.
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const lenis = new Lenis({ duration: 1.15, anchors: true });
    lenis.on("scroll", ScrollTrigger.update);
    const tick = (time) => lenis.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    return () => {
      gsap.ticker.remove(tick);
      gsap.ticker.lagSmoothing(500, 33);
      lenis.destroy();
    };
  }, []);

  useGSAP(
    () => {
      // Scroll progress drives the 3D scene and the stage indicator (written to the DOM directly, no re-renders).
      const labels = gsap.utils.toArray(".hud-step");
      ScrollTrigger.create({
        trigger: story.current,
        start: "top top",
        end: "bottom bottom",
        onUpdate: (self) => {
          const p = self.progress;
          progress.current = p;
          if (!hud.current) return;
          hud.current.style.setProperty("--p", p.toFixed(4));
          hud.current.style.opacity = p > 0.08 && p < 0.995 ? 1 : 0;
          const active = Math.min(3, Math.round(p * 4) - 1);
          labels.forEach((el, i) => el.toggleAttribute("data-active", i === active));
        },
      });

      // The header turns to frosted glass once the page moves, so copy never runs under the logo.
      ScrollTrigger.create({ start: 40, end: "max", toggleClass: { targets: ".site-header", className: "is-scrolled" } });

      const mm = gsap.matchMedia();
      mm.add({ motion: "(prefers-reduced-motion: no-preference)", wide: "(min-width: 768px)" }, (ctx) => {
        const { motion, wide } = ctx.conditions;
        if (!motion) return;
        const blur = (px) => (wide ? { filter: `blur(${px}px)` } : {});

        // The one timed moment: the headline rises in on load.
        gsap.from(".hero-line", { yPercent: 105, duration: 1.2, ease: "expo.out", stagger: 0.1, delay: 0.15 });
        gsap.from(".hero-fade", { opacity: 0, y: 14, duration: 1, delay: 0.7, ease: "expo.out", stagger: 0.08 });

        // Hero copy lifts away and defocuses as the story begins.
        gsap.to(".hero-content, .hero-cue", {
          yPercent: -18, opacity: 0, ...blur(10), ease: "none",
          scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom 55%", scrub: true },
        });

        // Each step card: clip-reveal in, hold, then lift out. Blur lives on the inner content so
        // the card keeps its frosted backdrop.
        gsap.utils.toArray(".step").forEach((section) => {
          const card = section.querySelector(".step-card");
          const inner = section.querySelectorAll(".step-in");
          gsap.timeline({ scrollTrigger: { trigger: section, start: "top bottom", end: "bottom top", scrub: true } })
            .fromTo(card, { opacity: 0, y: 140, scale: 0.94, clipPath: "inset(22% 0% 22% 0% round 24px)" },
              { opacity: 1, y: 0, scale: 1, clipPath: "inset(0% 0% 0% 0% round 24px)", duration: 0.36, ease: "power3.out" })
            .fromTo(inner, { y: 36, opacity: 0, ...blur(10) },
              { y: 0, opacity: 1, ...blur(0), stagger: 0.04, duration: 0.24, ease: "power2.out" }, 0.1)
            .to(card, { duration: 0.28 })
            .to(card, { opacity: 0, y: -140, scale: 0.96, duration: 0.36, ease: "power2.in" });
        });

        // Heading reveals word by word as it scrolls into place.
        gsap.fromTo(".watch-word", { opacity: 0.14 }, {
          opacity: 1, stagger: 0.12, ease: "none",
          scrollTrigger: { trigger: ".watch-title", start: "top 85%", end: "top 40%", scrub: true },
        });

        // Two rows of type slide in opposite directions with the scroll.
        gsap.fromTo(".band-a", { xPercent: 0 }, { xPercent: -33, ease: "none", scrollTrigger: { trigger: ".band", start: "top bottom", end: "bottom top", scrub: true } });
        gsap.fromTo(".band-b", { xPercent: -33 }, { xPercent: 0, ease: "none", scrollTrigger: { trigger: ".band", start: "top bottom", end: "bottom top", scrub: true } });

        // Source rows: the rule draws across, then the row settles in.
        gsap.utils.toArray(".source-row").forEach((row) => {
          gsap.timeline({ scrollTrigger: { trigger: row, start: "top 88%", end: "top 55%", scrub: true } })
            .fromTo(row.querySelector(".source-rule"), { scaleX: 0 }, { scaleX: 1, ease: "none" })
            .fromTo(row.querySelectorAll(".source-in"), { opacity: 0, x: -30 }, { opacity: 1, x: 0, stagger: 0.1, ease: "power2.out" }, 0.2);
        });

        // The closing panel opens up to full width as it arrives.
        gsap.fromTo(".cta-panel", { scale: 0.86, borderRadius: "72px" }, {
          scale: 1, borderRadius: "32px", ease: "none",
          scrollTrigger: { trigger: ".cta-panel", start: "top bottom", end: "top 25%", scrub: true },
        });
        gsap.fromTo(".cta-glow", { yPercent: 30 }, {
          yPercent: -30, ease: "none", scrollTrigger: { trigger: ".cta-panel", start: "top bottom", end: "bottom top", scrub: true },
        });
      });
    },
    { scope: root },
  );

  return (
    <div ref={root} className="overflow-x-clip">
      <header className="site-header fixed inset-x-0 top-0 z-30 transition-[background-color,backdrop-filter,box-shadow] duration-500">
        <span aria-hidden className="scroll-progress absolute inset-x-0 top-0 h-[3px] bg-linear-to-r from-signal-500 to-lime-300" />
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
          <Link to="/" aria-label="Job Hunt Copilot home"><Logo /></Link>
          <nav className="flex items-center gap-1.5 rounded-full bg-surface/70 p-1 shadow-[0_0_0_1px_var(--color-line)] backdrop-blur-xl">
            <Link to="/login" className="btn btn-plain px-4 py-2 text-sm">Sign in</Link>
            <Link to="/register" className="btn btn-ink px-4 py-2 text-sm">Create account</Link>
          </nav>
        </div>
      </header>

      <div ref={story} className="relative">
        {/* Absolute track spanning the story; the sticky child pins the scene and stops at the story's end. */}
        <div className="absolute inset-0">
          <div className="sticky top-0 h-lvh">
            <Suspense fallback={null}>
              <GlassCards mode="story" progress={progress} active={storyVisible} className="h-full w-full" />
            </Suspense>

            {/* Stage indicator: one segment per step, filled by scroll progress. */}
            <div ref={hud} className="hud pointer-events-none absolute bottom-8 right-8 hidden items-end gap-4 opacity-0 transition-opacity duration-500 lg:flex" aria-hidden>
              {STEPS.map((s, i) => (
                <div key={s.title} className="hud-step w-28" style={{ "--i": i }}>
                  <span className="hud-label flex items-baseline gap-2 text-xs font-semibold">
                    <span className="tabular-nums">0{i + 1}</span>{s.title}
                  </span>
                  <span className="mt-2 block h-[3px] overflow-hidden rounded-full bg-ink-950/10">
                    <span className="hud-fill block h-full origin-left rounded-full bg-ink-950" />
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <section className="hero relative z-10 mx-auto flex min-h-svh max-w-7xl items-end px-4 pb-14 sm:px-6 lg:items-center lg:pb-0">
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-2/3 bg-linear-to-t from-paper via-paper/85 to-transparent lg:hidden" />
          <div className="hero-content relative max-w-2xl">
            <h1 className="font-wide text-[clamp(2.6rem,7vw,5.6rem)] font-bold leading-[0.92]">
              <span className="block overflow-hidden pb-1"><span className="hero-line block">The jobs</span></span>
              <span className="block overflow-hidden pb-1"><span className="hero-line block">that fit you,</span></span>
              <span className="block overflow-hidden pb-1"><span className="hero-line block">out of the noise.</span></span>
            </h1>
            <p className="hero-fade mt-6 max-w-lg text-lg leading-relaxed text-ink-600">
              Tell the copilot your role and skills. Its agents search live LinkedIn and Naukri postings, score each one against
              what you know, and draft the note to the recruiter. You decide what to send.
            </p>
            <div className="hero-fade mt-8 flex flex-wrap items-center gap-3">
              <Link to="/register" className="btn btn-signal px-6 py-3.5 text-base">Start your search <ArrowRight size={17} aria-hidden /></Link>
              <a href="#how" className="btn btn-quiet px-6 py-3.5 text-base">How it works <ArrowDown size={17} aria-hidden /></a>
            </div>
            <p className="hero-fade mt-6 text-sm text-ink-500">Runs on free tiers only. No card asked, anywhere.</p>
          </div>
          <div className="hero-cue hero-fade pointer-events-none absolute bottom-8 left-1/2 hidden -translate-x-1/2 flex-col items-center gap-2 text-xs font-medium text-ink-500 lg:flex" aria-hidden>
            Scroll to watch the agents work
            <span className="relative h-9 w-[22px] rounded-full border-2 border-ink-300">
              <span className="scroll-dot absolute left-1/2 top-1.5 size-1.5 -translate-x-1/2 rounded-full bg-ink-950" />
            </span>
          </div>
        </section>

        <div id="how">
          {STEPS.map((s, i) => (
            <section key={s.title} className="step relative z-10 mx-auto flex h-svh max-w-7xl items-end px-4 pb-8 sm:px-6 lg:items-center lg:pb-0"
              aria-labelledby={`step-${i}`}>
              <div className="step-card w-full max-w-md rounded-[24px] border border-white/70 bg-surface/80 p-6 shadow-[0_30px_80px_-30px_rgb(21_41_168/0.35)] backdrop-blur-md sm:p-8 md:backdrop-blur-2xl">
                <div className="step-in flex items-center gap-3 text-sm font-semibold text-ink-500">
                  <span className="grid size-7 place-items-center rounded-full bg-ink-950 text-xs text-white">{i + 1}</span>
                  Step {i + 1} of {STEPS.length}
                </div>
                <h2 id={`step-${i}`} className="step-in font-wide mt-4 text-[clamp(2rem,4vw,3rem)] font-bold leading-none">{s.title}</h2>
                <p className="step-in mt-3 text-lg font-semibold leading-snug">{s.lead}</p>
                <p className="step-in mt-2 leading-relaxed text-ink-600">{s.body}</p>
                <p className="step-in mt-5 flex items-baseline gap-3 border-t border-line pt-4">
                  <span className="font-wide text-3xl font-bold text-signal-500">{s.stat[0]}</span>
                  <span className="text-sm text-ink-500">{s.stat[1]}</span>
                </p>
              </div>
            </section>
          ))}
        </div>
      </div>

      <section className="relative z-10 border-t border-line bg-surface">
        <div className="mx-auto grid max-w-7xl gap-12 px-4 py-24 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:py-32">
          <div className="lg:sticky lg:top-28 lg:self-start">
            <h2 className="watch-title font-wide text-[clamp(2rem,4.4vw,3.4rem)] font-bold leading-[0.98]" aria-label={WATCH_TITLE}>
              {WATCH_TITLE.split(" ").map((w, i) => <span key={i} className="watch-word inline-block pr-[0.25em]" aria-hidden>{w}</span>)}
            </h2>
            <p className="mt-5 max-w-md text-lg leading-relaxed text-ink-600">
              Every search streams its work as it happens: which source answered, how many jobs made the shortlist, and how far
              the scoring has got. When it's done, the steps fold away and your matches take over.
            </p>
          </div>
          <div className="rounded-[28px] bg-paper p-4 sm:p-7"><DemoThread /></div>
        </div>
      </section>

      <section className="band overflow-hidden border-y border-line bg-paper py-10 sm:py-14">
        <Band words={BAND[0]} className="band-a" />
        <Band words={BAND[1]} className="band-b mt-4 sm:mt-6" />
      </section>

      <section className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:py-32">
        <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <h2 className="font-wide text-[clamp(2rem,4.4vw,3.4rem)] font-bold leading-[0.98]">Where the jobs come from</h2>
            <p className="mt-5 max-w-md text-lg leading-relaxed text-ink-600">
              LinkedIn and Naukri don't offer public job APIs, and scraping them breaks their rules. The copilot uses licensed job
              APIs that carry those postings instead, and it never signs in to your accounts.
            </p>
          </div>
          <ol className="border-b border-line">
            {SOURCES.map(([name, body], i) => (
              <li key={name} className="source-row relative grid gap-1 py-6 sm:grid-cols-[13rem_1fr] sm:gap-6">
                <span className="source-rule absolute inset-x-0 top-0 h-px origin-left bg-line-strong" aria-hidden />
                <span className="source-in font-semiwide text-xl font-bold"><span className="mr-3 text-ink-400 tabular-nums">{i + 1}</span>{name}</span>
                <span className="source-in text-ink-600">{body}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="px-3 pb-3 sm:px-4 sm:pb-4">
        <div className="cta-panel relative overflow-hidden rounded-[32px] bg-ink-950 px-6 py-20 text-white sm:px-14 sm:py-28">
          <div aria-hidden className="cta-glow absolute -right-24 -top-24 size-96 rounded-full bg-signal-500/45 blur-3xl" />
          <div aria-hidden className="cta-glow absolute -bottom-32 left-1/3 size-80 rounded-full bg-lime-300/15 blur-3xl" />
          <div aria-hidden className="absolute inset-0 opacity-[0.07] [background-image:linear-gradient(white_1px,transparent_1px),linear-gradient(90deg,white_1px,transparent_1px)] [background-size:48px_48px] [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]" />
          <div className="relative mx-auto max-w-4xl">
            <h2 className="font-wide text-[clamp(2.2rem,5.6vw,4.4rem)] font-bold leading-[0.95]">Free on every tier. No card on file.</h2>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-white/70">
              Every service runs on its free plan. Searches are cached for six hours and AI results are saved per job, so the
              limits last a whole job hunt.
            </p>
            <ul className="mt-8 flex flex-wrap gap-2">
              {FREE.map((f) => <li key={f} className="rounded-full border border-white/15 px-4 py-1.5 text-sm text-white/80">{f}</li>)}
            </ul>
            <Link to="/register" className="btn mt-10 bg-lime-300 px-7 py-4 text-base text-ink-950 hover:bg-lime-200">
              Create your free account <ArrowRight size={17} aria-hidden />
            </Link>
          </div>
        </div>
        <footer className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-3 py-8 text-sm text-ink-500">
          <Logo />
          <p>Job Hunt Copilot never sends messages for you.</p>
        </footer>
      </section>
    </div>
  );
}
