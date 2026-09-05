import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Health } from "../lib/types";
import { Badge, Card, PageContainer } from "../components/ui";

const FEATURES = [
  {
    icon: "🛡️",
    title: "Container-isolated execution",
    body: "Every submission runs in a throw-away sandbox: network disabled, hard memory ceiling, CPU quota, process cap, read-only root filesystem and Linux capability drop.",
  },
  {
    icon: "⚡",
    title: "Seven distinct verdicts",
    body: "Accepted, Wrong Answer, Time Limit Exceeded, Memory Limit Exceeded, Runtime Error, Compilation Error, and Output Limit Exceeded.",
  },
  {
    icon: "🧪",
    title: "Sample and hidden suites",
    body: "Samples run first so a wrong solution fails fast. Hidden test data never leaves the server — only its index and timings reach a response.",
  },
  {
    icon: "🏆",
    title: "ICPC-style contest engine",
    body: "Time-windowed contests with penalty points for wrong submissions, live leaderboards, and real-time score updates.",
  },
  {
    icon: "⚙️",
    title: "Async task queue",
    body: "Celery worker pool powered by Redis for non-blocking submission judging under high concurrent platform load.",
  },
  {
    icon: "🔒",
    title: "Production security",
    body: "Strict CORS policies, proxy-aware rate limiters, isolated staging permissions, and JWT token authentication.",
  },
];



export function Landing() {
  const { user } = useAuth();
  const [health, setHealth] = useState<Health | null>(null);
  const [problemCount, setProblemCount] = useState<number | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api
      .problems({ limit: 1 })
      .then((p) => setProblemCount(p.total))
      .catch(() => setProblemCount(null));
  }, []);

  return (
    <PageContainer className="pt-12 sm:pt-16">
      {/* Hero */}
      <section className="mx-auto max-w-4xl text-center">
        <div className="mb-4 flex items-center justify-center gap-2">
          <Badge tone="info">JudgeX Engine</Badge>
          <span className="text-xs text-violet-300/40">•</span>
          <span className="text-xs text-violet-300/60 font-mono">
            {health?.execution.active ? `${health.execution.active} mode` : "Sandboxed"}
          </span>
        </div>

        <h1 className="text-4xl font-extrabold tracking-tight text-violet-50 sm:text-6xl sm:leading-[1.1]">
          Online Coding Judge & <br className="hidden sm:inline" />
          <span className="gradient-text">Competitive Programming</span>
        </h1>

        <p className="mx-auto mt-6 max-w-2xl text-base text-violet-200/70 sm:text-lg">
          JudgeX executes untrusted code safely inside isolated environments, evaluates correctness against test suites, and enforces hard resource constraints.
        </p>

        <div className="mt-8 flex flex-wrap justify-center gap-4">
          <Link
            to={user ? "/problems" : "/register"}
            className="btn-primary rounded-xl px-7 py-3.5 text-sm font-semibold text-white shadow-lg"
          >
            {user ? "Explore Problems" : "Get Started Free"}
          </Link>
          <Link
            to="/problems"
            className="btn-ghost rounded-xl px-7 py-3.5 text-sm font-semibold text-violet-100"
          >
            View Problem Archive →
          </Link>
        </div>
      </section>

      {/* Code Demo */}
      <section className="py-16">
        <div className="mx-auto max-w-3xl">
          <Card solid edge className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/8 px-5 py-3 text-xs font-medium text-violet-300/60">
              <div className="flex items-center gap-2">
                <span className="size-3 rounded-full bg-rose-500/80" />
                <span className="size-3 rounded-full bg-amber-500/80" />
                <span className="size-3 rounded-full bg-emerald-500/80" />
                <span className="ml-2 font-mono text-violet-200/50">solution.py</span>
              </div>
              <span className="font-mono text-violet-300/40">A + B Problem</span>
            </div>

            <div className="grid gap-0 md:grid-cols-[1.4fr_1fr]">
              <pre className="overflow-x-auto px-5 py-5 font-mono text-[13px] leading-relaxed text-violet-100/90">
                <code>
                  <span className="text-violet-200/30">1  </span>
                  <span className="text-sky-300">a</span>,{" "}
                  <span className="text-sky-300">b</span> ={" "}
                  <span className="text-fuchsia-300">map</span>(
                  <span className="text-emerald-300">int</span>,{" "}
                  <span className="text-fuchsia-300">input</span>().
                  <span className="text-fuchsia-300">split</span>()){"\n"}
                  <span className="text-violet-200/30">2  </span>
                  <span className="text-fuchsia-300">print</span>(a + b)
                </code>
              </pre>

              <div className="border-t border-white/8 p-5 md:border-t-0 md:border-l">
                <div className="mb-4 flex items-center gap-2">
                  <Badge tone="pass">✓ Accepted</Badge>
                </div>
                <dl className="space-y-2.5 font-mono text-sm">
                  {[
                    ["Tests", "6 / 6"],
                    ["Time", "63.1 ms"],
                    ["Memory", "9.0 MB"],
                    ["Score", "100"],
                  ].map(([label, value]) => (
                    <div key={label} className="flex justify-between">
                      <dt className="text-violet-200/50">{label}</dt>
                      <dd className="tabular-nums text-violet-50">{value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* Metrics */}
      <section className="grid grid-cols-2 gap-4 pb-16 lg:grid-cols-4">
        {[
          { label: "Problems", value: problemCount ?? "—" },
          { label: "Languages", value: health?.languages.length ?? 3 },
          { label: "Verdicts", value: 7 },
          {
            label: "Database",
            value: health?.database.connected ? "Online" : "Offline",
          },
        ].map((stat, index) => (
          <Card
            key={stat.label}
            hover
            edge
            className="animate-rise p-5 text-center"
            style={{ animationDelay: `${index * 60}ms` }}
          >
            <p className="font-mono text-3xl font-bold tabular-nums text-violet-50">
              {stat.value}
            </p>
            <p className="mt-1 text-[11px] font-semibold tracking-[0.14em] text-violet-300/60 uppercase">
              {stat.label}
            </p>
          </Card>
        ))}
      </section>

      {/* Features */}
      <section className="pb-20">
        <div className="mb-12 text-center">
          <p className="mb-2 text-xs font-semibold tracking-[0.2em] text-violet-300/70 uppercase">
            Platform Capabilities
          </p>
          <h2 className="text-3xl font-bold tracking-tight text-violet-50 sm:text-4xl">
            Built for security, accuracy, and scale
          </h2>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature, index) => (
            <Card
              key={feature.title}
              hover
              edge
              className="animate-rise p-6"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div
                className="mb-4 grid size-11 place-items-center rounded-xl border border-white/12 bg-gradient-to-br from-violet-500/25 to-fuchsia-500/15 text-lg text-violet-200"
                aria-hidden="true"
              >
                {feature.icon}
              </div>
              <h3 className="mb-2 text-base font-semibold text-violet-50">
                {feature.title}
              </h3>
              <p className="text-sm leading-relaxed text-violet-200/60">
                {feature.body}
              </p>
            </Card>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="pb-20">
        <Card edge className="overflow-hidden p-10 text-center sm:p-14">
          <h2 className="text-3xl font-bold tracking-tight text-violet-50 sm:text-4xl">
            Ready to test your code?
          </h2>
          <p className="mx-auto mt-3 max-w-md text-pretty text-violet-200/60">
            Select a problem from the archive, write your solution in Python, C++, or Java, and receive instant verdicts.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link
              to={user ? "/problems" : "/register"}
              className="btn-primary rounded-xl px-6 py-3 text-sm font-semibold text-white"
            >
              {user ? "Go to Problems" : "Create an Account"}
            </Link>
            <Link
              to="/contests"
              className="btn-ghost rounded-xl px-6 py-3 text-sm font-semibold text-violet-100"
            >
              View Contests
            </Link>
          </div>
        </Card>
      </section>
    </PageContainer>
  );
}
