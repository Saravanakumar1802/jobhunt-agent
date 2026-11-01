import { lazy, Suspense, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import Logo from "../components/ui/Logo";
import { useAuth } from "../context/AuthContext";

const GlassCards = lazy(() => import("../components/three/GlassCards"));

export default function AuthPage({ mode }) {
  const isRegister = mode === "register";
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [show, setShow] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/app" replace />;
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(mode, isRegister ? form : { email: form.email, password: form.password });
      navigate("/app");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.1fr_1fr]">
      <aside className="relative hidden flex-col justify-between overflow-hidden p-10 lg:flex">
        <Link to="/" className="relative z-10"><Logo /></Link>
        <Suspense fallback={null}>
          <GlassCards mode="fan" className="absolute inset-0" />
        </Suspense>
        <div className="relative z-10 max-w-md">
          <p className="font-wide text-4xl font-bold leading-[1]">Your next role is one search away.</p>
          <p className="mt-4 text-ink-600">Live LinkedIn and Naukri postings, scored against your skills, with the recruiter note drafted.</p>
        </div>
      </aside>

      <main className="flex flex-col justify-center bg-surface px-5 py-10 sm:px-12 lg:rounded-l-[36px] lg:shadow-[-30px_0_60px_-40px_rgb(11_14_20/0.25)]">
        <div className="mx-auto w-full max-w-sm">
          <Link to="/" className="mb-10 inline-block lg:hidden"><Logo /></Link>
          <form onSubmit={submit} className="space-y-5">
            <div>
              <h1 className="font-wide text-[2.2rem] font-bold leading-none">{isRegister ? "Create your account" : "Welcome back"}</h1>
              <p className="mt-3 text-ink-500">
                {isRegister ? "Your profiles and tracked jobs are saved to this account." : "Sign in to pick up your search."}
              </p>
            </div>

            {isRegister && (
              <div>
                <label className="label" htmlFor="name">Name</label>
                <input id="name" className="field py-3" required autoComplete="name" enterKeyHint="next" value={form.name} onChange={set("name")} />
              </div>
            )}
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input id="email" type="email" className="field py-3" required autoComplete="username" spellCheck="false"
                enterKeyHint="next" value={form.email} onChange={set("email")} />
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <div className="relative">
                <input id="password" type={show ? "text" : "password"} className="field py-3 pr-11" required
                  minLength={isRegister ? 8 : 1} autoComplete={isRegister ? "new-password" : "current-password"}
                  enterKeyHint="done" value={form.password} onChange={set("password")}
                  aria-describedby={isRegister ? "pw-hint" : undefined} />
                <button type="button" onClick={() => setShow((s) => !s)} aria-pressed={show}
                  aria-label={show ? "Hide password" : "Show password"}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-ink-400 hover:text-ink-950">
                  {show ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
              {isRegister && <p id="pw-hint" className="mt-1.5 text-xs text-ink-400">At least 8 characters.</p>}
            </div>

            {error && <p role="alert" className="rounded-xl bg-bad-50 p-3 text-sm text-bad-700">{error}</p>}

            <button className="btn btn-ink w-full py-3.5" disabled={busy}>
              {busy ? "Please wait…" : isRegister ? "Create account" : "Sign in"}
            </button>
            <p className="text-center text-sm text-ink-500">
              {isRegister ? "Already have an account? " : "New here? "}
              <Link to={isRegister ? "/login" : "/register"} className="font-semibold text-signal-600 underline underline-offset-4">
                {isRegister ? "Sign in" : "Create an account"}
              </Link>
            </p>
          </form>
        </div>
      </main>
    </div>
  );
}
