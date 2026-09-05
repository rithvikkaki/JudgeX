import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Suspense, lazy, type ReactNode } from "react";
import { AuthProvider, useAuth } from "./lib/auth";
import { Layout } from "./components/Layout";
import { Spinner } from "./components/ui";
import { Landing } from "./pages/Landing";
import { AuthPage } from "./pages/Auth";
import { Problems } from "./pages/Problems";
import { Contests } from "./pages/Contests";
import { ContestDetail } from "./pages/ContestDetail";
import { Submissions } from "./pages/Submissions";
import { Dashboard } from "./pages/Dashboard";
import { NotFound } from "./pages/NotFound";

// The code editor is ~210 kB gzipped — two thirds of the whole bundle — and is
// only needed once someone opens a problem. Splitting it here keeps the
// landing page, which is what a first-time visitor loads, small.
const Solve = lazy(() =>
  import("./pages/Solve").then((module) => ({ default: module.Solve })),
);

function RouteFallback() {
  return (
    <div className="grid min-h-[60dvh] place-items-center text-violet-300">
      <Spinner size={26} />
    </div>
  );
}

/** Gates a route behind authentication, remembering where the user was headed. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="grid min-h-[60dvh] place-items-center text-violet-300">
        <Spinner size={26} />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Landing />} />
            <Route path="login" element={<AuthPage mode="login" />} />
            <Route path="register" element={<AuthPage mode="register" />} />

            <Route path="problems" element={<Problems />} />
            <Route
              path="problems/:slug"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <Solve />
                </Suspense>
              }
            />

            <Route path="contests" element={<Contests />} />
            <Route path="contests/:id" element={<ContestDetail />} />

            <Route
              path="submissions"
              element={
                <RequireAuth>
                  <Submissions />
                </RequireAuth>
              }
            />
            <Route
              path="dashboard"
              element={
                <RequireAuth>
                  <Dashboard />
                </RequireAuth>
              }
            />

            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
