import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { AuroraBackdrop, Spinner } from "./ui";

const NAV = [
  { to: "/problems", label: "Problems" },
  { to: "/contests", label: "Contests" },
  { to: "/submissions", label: "Submissions", private: true },
  { to: "/dashboard", label: "Dashboard", private: true },
];

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => setMenuOpen(false), [location.pathname]);

  const links = NAV.filter((item) => !item.private || user);

  return (
    <div className="relative flex min-h-dvh flex-col">
      <AuroraBackdrop />
      <ColdStartNotice />

      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#07060f]/80 backdrop-blur-xl">
        <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2.5 shrink-0">
              <span
                className="grid size-8 place-items-center rounded-lg bg-gradient-to-br from-violet-500 via-purple-500 to-fuchsia-500 text-sm font-black text-white shadow-lg shadow-purple-500/30"
                aria-hidden="true"
              >
                J
              </span>
              <span className="text-[15px] font-bold tracking-tight text-violet-50">
                JudgeX
              </span>
            </Link>

            <div className="hidden items-center gap-1 md:flex">
              {links.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    [
                      "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-white/10 text-violet-50"
                        : "text-violet-200/60 hover:bg-white/5 hover:text-violet-100",
                    ].join(" ")
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {user ? (
              <div className="flex items-center gap-3">
                <div className="hidden text-right sm:block">
                  <p className="text-sm font-semibold text-violet-50">
                    {user.username}
                  </p>
                  {user.is_admin && (
                    <p className="text-[10px] font-semibold tracking-wider text-fuchsia-300/80 uppercase">
                      Admin
                    </p>
                  )}
                </div>
                <span
                  className="grid size-9 place-items-center rounded-full bg-gradient-to-br from-violet-500/80 to-fuchsia-500/80 text-sm font-bold text-white shrink-0"
                  aria-hidden="true"
                >
                  {user.username.slice(0, 1).toUpperCase()}
                </span>
                <button
                  onClick={() => {
                    logout();
                    navigate("/");
                  }}
                  className="btn-ghost rounded-lg px-3 py-2 text-sm font-medium text-violet-100"
                >
                  Sign out
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  to="/login"
                  className="btn-ghost rounded-lg px-3.5 py-2 text-sm font-medium text-violet-100"
                >
                  Sign in
                </Link>
                <Link
                  to="/register"
                  className="btn-primary rounded-lg px-3.5 py-2 text-sm font-semibold text-white"
                >
                  Get started
                </Link>
              </div>
            )}

            <button
              onClick={() => setMenuOpen((open) => !open)}
              className="btn-ghost grid size-9 place-items-center rounded-lg md:hidden"
              aria-label="Toggle navigation"
              aria-expanded={menuOpen}
            >
              <span aria-hidden="true">{menuOpen ? "✕" : "☰"}</span>
            </button>
          </div>
        </nav>

        {menuOpen && (
          <div className="border-t border-white/8 bg-[#07060f]/95 px-4 py-3 md:hidden">
            {links.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  [
                    "block rounded-lg px-3 py-2.5 text-sm font-medium",
                    isActive
                      ? "bg-white/10 text-violet-50"
                      : "text-violet-200/70 hover:bg-white/5",
                  ].join(" ")
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        )}
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-white/8 py-8">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 px-4 text-sm text-violet-200/45 sm:flex-row sm:px-6">
          <p>
            JudgeX — sandboxed competitive-programming judge by{" "}
            <a
              href="https://github.com/dhanoliya-ji"
              target="_blank"
              rel="noreferrer"
              className="text-violet-300 hover:text-violet-200"
            >
              Gajendra Dhanoliya
            </a>
          </p>
          <div className="flex items-center gap-4">
            <a
              href="https://github.com/dhanoliya-ji/ONLINE-CODING-JUDGE"
              target="_blank"
              rel="noreferrer"
              className="hover:text-violet-200"
            >
              Source
            </a>
            <a
              href={`${import.meta.env.VITE_API_BASE_URL ?? ""}/docs`}
              target="_blank"
              rel="noreferrer"
              className="hover:text-violet-200"
            >
              API docs
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function ColdStartNotice() {
  const [state, setState] = useState<"checking" | "cold" | "ready">("checking");

  useEffect(() => {
    let cancelled = false;

    const slowTimer = setTimeout(() => {
      if (!cancelled) setState((s) => (s === "checking" ? "cold" : s));
    }, 1800);

    api
      .ping()
      .then(() => !cancelled && setState("ready"))
      .catch(() => !cancelled && setState("ready"))
      .finally(() => clearTimeout(slowTimer));

    return () => {
      cancelled = true;
      clearTimeout(slowTimer);
    };
  }, []);

  if (state !== "cold") return null;

  return (
    <div className="sticky top-0 z-50 border-b border-amber-400/25 bg-amber-500/12 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-2.5 text-sm text-amber-100 sm:px-6">
        <Spinner size={15} />
        <p>
          <span className="font-semibold">Waking the judge…</span>{" "}
          <span className="text-amber-100/75">
            The API sleeps on free hosting and takes up to a minute to start.
            This happens once.
          </span>
        </p>
      </div>
    </div>
  );
}
