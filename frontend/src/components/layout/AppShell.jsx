import { NavLink, Link, Outlet } from "react-router-dom";
import { AlertTriangle, Cpu, Gauge, KanbanSquare, LogOut, Search } from "lucide-react";
import Logo from "../ui/Logo";
import { useAuth } from "../../context/AuthContext";
import { useModels } from "../../hooks/queries";
import { initials } from "../../utils/format";

const NAV = [
  { to: "/app", label: "Find jobs", icon: Search, end: true },
  { to: "/app/tracker", label: "Tracker", icon: KanbanSquare },
  { to: "/app/models", label: "AI models", icon: Cpu },
  { to: "/app/status", label: "Usage", icon: Gauge },
];

/** Shown on every page when a model tier has no working model, so the user can switch models. */
export function ModelBanner() {
  const { data } = useModels();
  if (!data) return null;
  const noKeys = !Object.values(data.providers).some(Boolean);
  const broken = Object.entries(data.tier_ok).filter(([, ok]) => !ok).map(([t]) => t);
  if (!noKeys && broken.length === 0) return null;

  const message = noKeys
    ? "No AI keys yet, so scores use keyword matching only and drafts use templates. Add free keys to backend/.env."
    : `No working AI model for the ${broken.join(" and ")} step. A model may have been retired or hit its limit.`;
  return (
    <div role="alert" className="mx-auto max-w-6xl px-4 pt-3 sm:px-6">
      <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-warn-50 px-4 py-2.5 text-sm text-warn-700">
        <AlertTriangle size={16} className="shrink-0 text-warn-500" aria-hidden />
        <span className="flex-1">{message}</span>
        <Link to="/app/models" className="font-semibold underline underline-offset-4">
          {noKeys ? "See setup" : "Switch models"}
        </Link>
      </div>
    </div>
  );
}

export default function AppShell() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-dvh pb-24 sm:pb-0">
      <header className="sticky top-0 z-30 border-b border-line/70 bg-paper/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
          <Link to="/app" aria-label="Job Hunt Copilot home"><Logo /></Link>
          <nav aria-label="Main" className="hidden items-center gap-0.5 rounded-full bg-surface p-1 shadow-[0_0_0_1px_var(--color-line)] sm:flex">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-semibold transition-colors duration-200 ${
                    isActive ? "bg-ink-950 text-white" : "text-ink-500 hover:text-ink-950"
                  }`
                }>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden text-sm text-ink-500 lg:inline">{user?.name}</span>
            <span className="grid size-9 place-items-center rounded-full bg-lime-300 text-sm font-bold text-ink-950" aria-hidden>
              {initials(user?.name)}
            </span>
            <button type="button" onClick={logout} className="btn btn-plain p-2.5" aria-label="Sign out" title="Sign out">
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </header>
      <ModelBanner />

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
        <Outlet />
      </main>

      {/* Phones: a bottom tab bar within thumb reach. */}
      <nav aria-label="Main" className="fixed inset-x-3 bottom-3 z-30 grid grid-cols-4 rounded-[22px] bg-ink-950/95 p-1.5 shadow-2xl backdrop-blur sm:hidden"
        style={{ marginBottom: "env(safe-area-inset-bottom)" }}>
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end}
            className={({ isActive }) =>
              `flex flex-col items-center gap-1 rounded-2xl py-2 text-[0.7rem] font-semibold transition-colors ${
                isActive ? "bg-white/12 text-white" : "text-white/55"
              }`
            }>
            <Icon size={19} aria-hidden />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
