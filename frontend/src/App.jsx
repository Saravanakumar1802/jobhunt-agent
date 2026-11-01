import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import { useAuth } from "./context/AuthContext";
import AuthPage from "./pages/AuthPage";

// Route-level code splitting: the landing page (GSAP + 3D) never loads for signed-in pages and vice versa.
const Landing = lazy(() => import("./pages/Landing"));
const SearchPage = lazy(() => import("./pages/SearchPage"));
const TrackerPage = lazy(() => import("./pages/TrackerPage"));
const ModelsPage = lazy(() => import("./pages/ModelsPage"));
const StatusPage = lazy(() => import("./pages/StatusPage"));

function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="grid min-h-dvh place-items-center text-ink-400">Loading your workspace…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

export default function App() {
  return (
    <Suspense fallback={<div className="grid min-h-dvh place-items-center text-ink-400">Loading…</div>}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<AuthPage mode="login" />} />
        <Route path="/register" element={<AuthPage mode="register" />} />
        <Route path="/app" element={<RequireAuth><AppShell /></RequireAuth>}>
          <Route index element={<SearchPage />} />
          <Route path="tracker" element={<TrackerPage />} />
          <Route path="models" element={<ModelsPage />} />
          <Route path="status" element={<StatusPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
