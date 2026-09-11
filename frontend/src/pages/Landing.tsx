import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Health } from "../lib/types";
import { Badge, Card, PageContainer } from "../components/ui";

const FEATURES = [
  {
    icon: "🛡️",
    title: "Container-Isolated Execution",
    body: "Every submission runs in a throw-away sandbox: network disabled, hard memory ceiling, CPU quota, process cap, read-only root filesystem, and dropped Linux capabilities.",
  },
  {
    icon: "⚡",
    title: "Seven Distinct Verdicts",
    body: "Accepted, Wrong Answer, Time Limit Exceeded, Memory Limit Exceeded, Runtime Error, Compilation Error, and Output Limit Exceeded.",
  },
  {
    icon: "🧪",
    title: "Sample & Hidden Test Suites",
    body: "Samples run first so incorrect solutions fail fast. Hidden test cases stay on the server — only timing metrics and indices reach responses.",
  },
  {
    icon: "🏆",
    title: "ICPC Contest Engine",
    body: "Time-windowed contests with penalty points for wrong submissions, live standings leaderboards, and real-time score calculation.",
  },
  {
    icon: "⚙️",
    title: "Async Celery Queue",
    body: "Celery worker pool powered by Redis for non-blocking submission judging under concurrent platform load.",
  },
  {
    icon: "🔒",
    title: "Production Security",
    body: "Proxy-aware rate limiters, isolated staging permissions, JWT authentication, and strict CORS configuration.",
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
    <PageContainer className="pt-10 sm:pt-14">
      {/* Hero */}
      <section className="mx-auto max-w-4xl text-center">
        <div className="mb-4 flex items-center justify-center gap-2">
          <Badge tone="pass">JudgeX Engine v1.0</Badge>
          <span className="text-xs text-[#2A332F]">•</span>
          <span className="font-mono text-xs font-semibold text-[#A7B2AC]">
            {health?.execution.active ? `${health.execution.active.toUpperCase()} EXECUTION` : "SANDBOXED WORKSTATION"}
          </span>
        </div>

        <h1 className="text-3xl font-bold font-mono tracking-tight text-[#F1F5F2] sm:text-5xl sm:leading-[1.15]">
          Online Coding Judge & <br className="hidden sm:inline" />
          Competitive Programming Platform
        </h1>

        <p className="mx-auto mt-4 max-w-2xl text-xs leading-relaxed text-[#A7B2AC] font-sans sm:text-sm">
          JudgeX executes untrusted code safely inside isolated Linux container environments, evaluates correctness against test suites, and enforces hard resource limits.
        </p>

        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link
            to={user ? "/problems" : "/register"}
            className="btn-lime px-6 py-2.5 text-xs font-mono font-bold uppercase tracking-wider"
          >
            {user ? "Explore Problems" : "Get Started Free"}
          </Link>
          <Link
            to="/problems"
            className="btn-ghost border border-[#2A332F] px-6 py-2.5 text-xs font-mono font-semibold text-[#F1F5F2]"
          >
            View Problem Archive →
          </Link>
        </div>
      </section>

      {/* Code Demo */}
      <section className="pt-6 pb-10">
        <div className="mx-auto max-w-3xl">
          <Card className="overflow-hidden bg-[#141A18] border border-[#2A332F] rounded-md">
            <div className="flex items-center justify-between border-b border-[#2A332F] bg-[#1A211F] px-4 py-2.5 text-xs font-mono text-[#A7B2AC]">
              <div className="flex items-center gap-2">
                <span className="size-2.5 rounded-full bg-[#2A332F]" />
                <span className="size-2.5 rounded-full bg-[#2A332F]" />
                <span className="size-2.5 rounded-full bg-[#2A332F]" />
                <span className="ml-2 font-mono text-[#F1F5F2]">solution.py</span>
              </div>
              <span className="font-mono text-[#6F7B75]">Sum of Two Numbers</span>
            </div>

            <div className="grid gap-0 md:grid-cols-[1.4fr_1fr]">
              <pre className="overflow-x-auto bg-[#0A0F0E] p-4 font-mono text-xs leading-relaxed text-[#F1F5F2]">
                <code>
                  <span className="text-[#6F7B75]">1  </span>
                  <span className="text-[#B7F34A] font-semibold">a</span>,{" "}
                  <span className="text-[#B7F34A] font-semibold">b</span> ={" "}
                  <span className="text-[#70B7FF]">map</span>(
                  <span className="text-[#70B7FF]">int</span>,{" "}
                  <span className="text-[#70B7FF]">input</span>().
                  <span className="text-[#70B7FF]">split</span>()){"\n"}
                  <span className="text-[#6F7B75]">2  </span>
                  <span className="text-[#70B7FF]">print</span>(a + b)
                </code>
              </pre>

              <div className="border-t border-[#2A332F] bg-[#141A18] p-4 md:border-t-0 md:border-l">
                <div className="mb-3 flex items-center justify-between">
                  <Badge tone="pass">✓ ACCEPTED</Badge>
                  <span className="font-mono text-[11px] text-[#6F7B75]">Docker Sandbox</span>
                </div>
                <dl className="space-y-2 font-mono text-xs">
                  {[
                    ["Test Cases", "6 / 6 Passed"],
                    ["Time", "63.1 ms"],
                    ["Memory", "9.0 MB"],
                    ["Score", "100 / 100"],
                  ].map(([label, value]) => (
                    <div key={label} className="flex justify-between border-b border-[#2A332F] pb-1.5">
                      <dt className="text-[#6F7B75]">{label}</dt>
                      <dd className="font-semibold text-[#F1F5F2] tabular-nums">{value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* Metrics */}
      <section className="grid grid-cols-2 gap-3 pb-12 lg:grid-cols-4">
        {[
          { label: "Archive Problems", value: problemCount ?? "—" },
          { label: "Supported Toolchains", value: health?.languages.length ?? 3 },
          { label: "Verdict System", value: 7 },
          {
            label: "Database Status",
            value: health?.database.connected ? "Connected" : "Offline",
          },
        ].map((stat, index) => (
          <Card
            key={stat.label}
            hover
            className="animate-swiss-in p-4 text-center bg-[#141A18] border border-[#2A332F]"
            style={{ animationDelay: `${index * 40}ms` }}
          >
            <p className="font-mono text-2xl font-bold tabular-nums text-[#B7F34A]">
              {stat.value}
            </p>
            <p className="mt-1 font-mono text-[10px] font-semibold tracking-wider text-[#A7B2AC] uppercase">
              {stat.label}
            </p>
          </Card>
        ))}
      </section>

      {/* Features */}
      <section className="pb-16">
        <div className="mb-8 text-center">
          <p className="mb-1 font-mono text-xs font-semibold tracking-wider text-[#B7F34A] uppercase">
            Platform Specifications
          </p>
          <h2 className="text-2xl font-bold font-mono tracking-tight text-[#F1F5F2] sm:text-3xl">
            Engineered for Security, Accuracy, and Speed
          </h2>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature, index) => (
            <Card
              key={feature.title}
              hover
              className="animate-swiss-in p-5 bg-[#141A18] border border-[#2A332F]"
              style={{ animationDelay: `${index * 40}ms` }}
            >
              <div
                className="mb-3 grid size-9 place-items-center rounded border border-[#2A332F] bg-[#1A211F] text-base"
                aria-hidden="true"
              >
                {feature.icon}
              </div>
              <h3 className="mb-1.5 text-sm font-bold font-mono text-[#F1F5F2]">
                {feature.title}
              </h3>
              <p className="text-xs leading-relaxed text-[#A7B2AC] font-sans">
                {feature.body}
              </p>
            </Card>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="pb-16">
        <Card className="p-8 text-center sm:p-12 bg-[#141A18] border border-[#2A332F]">
          <h2 className="text-2xl font-bold font-mono tracking-tight text-[#F1F5F2] sm:text-3xl">
            Ready to test your algorithms?
          </h2>
          <p className="mx-auto mt-2 max-w-md text-xs font-sans text-[#A7B2AC]">
            Select a problem from the archive, write solutions in Python, C++, or Java, and receive instant verdicts.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link
              to={user ? "/problems" : "/register"}
              className="btn-lime px-5 py-2.5 text-xs font-mono font-bold uppercase tracking-wider"
            >
              {user ? "Open Problem Archive" : "Create Account"}
            </Link>
            <Link
              to="/contests"
              className="btn-ghost border border-[#2A332F] px-5 py-2.5 text-xs font-mono font-semibold text-[#F1F5F2]"
            >
              Explore Contests
            </Link>
          </div>
        </Card>
      </section>
    </PageContainer>
  );
}

