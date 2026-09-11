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
    <div className="relative flex min-h-dvh flex-col bg-[#0D1110] text-[#F1F5F2]">
      <AuroraBackdrop />
      <ColdStartNotice />

      <header className="sticky top-0 z-40 border-b border-[#2A332F] bg-[#141A18]/95 backdrop-blur-md">
        <nav className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex items-center gap-4 sm:gap-8">
            <Link to="/" className="flex items-center gap-2 shrink-0">
              <span
                className="grid size-7 place-items-center rounded-md bg-[#B7F34A] font-mono text-xs font-bold text-[#0D1110]"
                aria-hidden="true"
              >
                J
              </span>
              <span className="text-base font-bold tracking-tight text-[#F1F5F2] font-mono">
                JudgeX
              </span>
              <span className="hidden sm:inline-block rounded bg-[#1A211F] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#A7B2AC] border border-[#2A332F]">
                ENGINE
              </span>
            </Link>

            <div className="hidden items-center gap-1 md:flex">
              {links.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    [
                      "rounded-md px-3 py-1.5 font-mono text-xs font-semibold transition-all",
                      isActive
                        ? "bg-[#1A211F] text-[#B7F34A] border border-[#2A332F]"
                        : "text-[#A7B2AC] hover:bg-[#1A211F] hover:text-[#F1F5F2]",
                    ].join(" ")
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {user ? (
              <div className="flex items-center gap-2 sm:gap-3">
                <div className="hidden sm:block text-right">
                  <p className="text-xs font-mono font-semibold text-[#F1F5F2]">
                    {user.username}
                  </p>
                  {user.is_admin && (
                    <p className="font-mono text-[9px] font-semibold tracking-wider text-[#B7F34A] uppercase">
                      Admin
                    </p>
                  )}
                </div>
                <span
                  className="hidden sm:grid size-8 place-items-center rounded-md bg-[#1A211F] border border-[#2A332F] font-mono text-xs font-bold text-[#B7F34A] shrink-0"
                  aria-hidden="true"
                >
                  {user.username.slice(0, 1).toUpperCase()}
                </span>
                <button
                  onClick={() => {
                    logout();
                    navigate("/");
                  }}
                  className="hidden sm:inline-block btn-ghost px-3 py-1.5 text-xs font-mono font-semibold"
                >
                  Sign out
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  to="/login"
                  className="hidden sm:inline-block btn-ghost px-3.5 py-1.5 text-xs font-mono font-semibold"
                >
                  Sign in
                </Link>
                <Link
                  to="/register"
                  className="btn-lime px-3 py-1.5 text-xs font-mono font-semibold uppercase tracking-wider whitespace-nowrap"
                >
                  Get started
                </Link>
              </div>
            )}

            <button
              onClick={() => setMenuOpen((open) => !open)}
              className="btn-ghost grid size-8 place-items-center rounded-md md:hidden text-[#A7B2AC] shrink-0"
              aria-label="Toggle navigation"
              aria-expanded={menuOpen}
            >
              <span aria-hidden="true">{menuOpen ? "✕" : "☰"}</span>
            </button>
          </div>
        </nav>

        {menuOpen && (
          <div className="border-t border-[#2A332F] bg-[#141A18] px-4 py-3 md:hidden animate-swiss-in">
            {links.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  [
                    "block rounded-md px-3 py-2 font-mono text-xs font-semibold mb-1",
                    isActive
                      ? "bg-[#1A211F] text-[#B7F34A] border border-[#2A332F]"
                      : "text-[#A7B2AC] hover:bg-[#1A211F]",
                  ].join(" ")
                }
              >
                {item.label}
              </NavLink>
            ))}
            <div className="mt-2 border-t border-[#2A332F] pt-2">
              {user ? (
                <div className="flex items-center justify-between px-3 py-1">
                  <span className="font-mono text-xs text-[#F1F5F2] font-semibold">{user.username}</span>
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      logout();
                      navigate("/");
                    }}
                    className="font-mono text-xs text-[#B7F34A] font-semibold hover:underline"
                  >
                    Sign out
                  </button>
                </div>
              ) : (
                <Link
                  to="/login"
                  onClick={() => setMenuOpen(false)}
                  className="block rounded-md px-3 py-2 font-mono text-xs font-semibold text-[#A7B2AC] hover:bg-[#1A211F]"
                >
                  Sign in
                </Link>
              )}
            </div>
          </div>
        )}
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-[#2A332F] bg-[#141A18] py-6">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 px-4 text-xs font-mono text-[#6F7B75] sm:flex-row sm:px-6">
          <p>
            JudgeX — Sandboxed Competitive Programming Engine by{" "}
            <a
              href="https://github.com/rithvikkaki"
              target="_blank"
              rel="noreferrer"
              className="text-[#F1F5F2] font-semibold underline decoration-[#2A332F] hover:decoration-[#B7F34A]"
            >
              Rithvik Kaki
            </a>
          </p>
          <div className="flex items-center gap-4">
            <a
              href="https://github.com/rithvikkaki/JudgeX"
              target="_blank"
              rel="noreferrer"
              className="hover:text-[#F1F5F2] transition-colors"
            >
              Source
            </a>
            <span className="text-[#2A332F]">•</span>
            <a
              href={`${import.meta.env.VITE_API_BASE_URL ?? ""}/docs`}
              target="_blank"
              rel="noreferrer"
              className="hover:text-[#F1F5F2] transition-colors"
            >
              API Reference
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
    <div className="border-b border-[#4F4220] bg-[#332B15] py-2">
      <div className="mx-auto flex max-w-7xl items-center gap-2.5 px-4 text-xs font-mono text-[#F5C451] sm:px-6">
        <Spinner size={14} />
        <p>
          <span className="font-bold">Waking judge instance...</span>{" "}
          <span className="text-[#A7B2AC]">
            Free environment sleeps when idle and requires ~30s to initialize.
          </span>
        </p>
      </div>
    </div>
  );
}

