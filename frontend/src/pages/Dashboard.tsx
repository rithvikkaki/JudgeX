import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { LANGUAGE_LABELS, formatMemory, relativeTime } from "../lib/format";
import type { Dashboard as DashboardData } from "../lib/types";
import {
  Alert,
  Card,
  PageContainer,
  PageHeading,
  Skeleton,
  Stat,
  VerdictBadge,
} from "../components/ui";

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .dashboard()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <PageContainer className="py-12 space-y-5">
        <Skeleton className="h-12 w-72" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-72" />
      </PageContainer>
    );
  }

  if (error || !data) {
    return (
      <PageContainer className="py-24 max-w-lg">
        <Alert tone="fail">{error ?? "Could not load dashboard"}</Alert>
      </PageContainer>
    );
  }

  return (
    <PageContainer className="py-12">
      <PageHeading
        eyebrow="Overview"
        title="Dashboard"
        description="Personal statistics, solve rate, verdict distribution, and execution metrics."
      />

      {/* Primary KPI Grid */}
      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Problems solved"
          value={String(data.problems_solved)}
          hint={`${data.problems_attempted} attempted`}
          tone="pass"
        />
        <Stat
          label="Acceptance rate"
          value={`${data.acceptance_rate.toFixed(1)}%`}
          hint={`${data.accepted_submissions} accepted of ${data.total_submissions}`}
          tone="info"
        />
        <Stat
          label="Contests"
          value={String(data.contests_participated)}
          hint={
            data.best_contest_rank
              ? `Best rank #${data.best_contest_rank}`
              : "Contests joined"
          }
        />
        <Stat
          label="Submissions"
          value={String(data.total_submissions)}
          hint="Total code executions"
        />
      </div>

      {/* Analytics breakdown */}
      <div className="grid gap-6 lg:grid-cols-2">
        <VerdictChart data={data} />
        <DifficultyChart data={data} />
        <LanguageChart data={data} />
        <RecentActivity data={data} />
      </div>
    </PageContainer>
  );
}

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <Card solid className="p-6">
      <div className="mb-5">
        <h2 className="text-base font-semibold text-violet-50">{title}</h2>
        {subtitle && (
          <p className="mt-0.5 text-xs text-violet-200/45">{subtitle}</p>
        )}
      </div>
      {children}
    </Card>
  );
}

function VerdictChart({ data }: { data: DashboardData }) {
  const rows = [...data.verdict_breakdown].sort((a, b) => b.count - a.count);
  const max = Math.max(...rows.map((row) => row.count), 1);

  return (
    <ChartCard
      title="Verdict distribution"
      subtitle={`${data.total_submissions} submissions total`}
    >
      <ul className="space-y-3.5">
        {rows.map((row) => {
          const share =
            data.total_submissions > 0
              ? (row.count / data.total_submissions) * 100
              : 0;
          return (
            <li key={row.verdict}>
              <div className="mb-1.5 flex items-center gap-2">
                <VerdictBadge verdict={row.verdict} />
                <span className="ml-auto font-mono text-sm font-semibold tabular-nums text-violet-50">
                  {row.count}
                </span>
                <span className="w-11 text-right font-mono text-xs tabular-nums text-violet-200/45">
                  {share.toFixed(0)}%
                </span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-white/6">
                <div
                  className="h-full rounded-full bg-violet-400 transition-[width] duration-700"
                  style={{ width: `${(row.count / max) * 100}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </ChartCard>
  );
}

function DifficultyChart({ data }: { data: DashboardData }) {
  const order = ["Easy", "Medium", "Hard"];
  const rows = [...data.difficulty_progress].sort(
    (a, b) => order.indexOf(a.difficulty) - order.indexOf(b.difficulty),
  );

  return (
    <ChartCard
      title="Progress by difficulty"
      subtitle="Distinct problems solved against those available"
    >
      <ul className="space-y-4">
        {rows.map((row) => {
          const pct =
            row.total_available > 0
              ? (row.solved / row.total_available) * 100
              : 0;
          return (
            <li key={row.difficulty}>
              <div className="mb-1.5 flex items-baseline justify-between">
                <span className="text-sm font-medium text-violet-100">
                  {row.difficulty}
                </span>
                <span className="font-mono text-sm tabular-nums text-violet-200/70">
                  {row.solved}
                  <span className="text-violet-200/35">
                    {" "}
                    / {row.total_available}
                  </span>
                </span>
              </div>
              <div
                className="h-2.5 overflow-hidden rounded-full bg-white/6"
                role="meter"
                aria-valuenow={row.solved}
                aria-valuemin={0}
                aria-valuemax={row.total_available}
                aria-label={`${row.difficulty} problems solved`}
              >
                <div
                  className="h-full rounded-full bg-violet-400 transition-[width] duration-700"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </ChartCard>
  );
}

function LanguageChart({ data }: { data: DashboardData }) {
  const rows = [...data.language_usage].sort(
    (a, b) => b.submissions - a.submissions,
  );
  const max = Math.max(...rows.map((row) => row.submissions), 1);

  return (
    <ChartCard
      title="Languages"
      subtitle="Accepted portion of each language's submissions"
    >
      <ul className="space-y-4">
        {rows.map((row) => (
          <li key={row.language}>
            <div className="mb-1.5 flex items-baseline justify-between">
              <span className="text-sm font-medium text-violet-100">
                {LANGUAGE_LABELS[row.language] ?? row.language}
              </span>
              <span className="font-mono text-xs tabular-nums text-violet-200/60">
                {row.accepted} accepted / {row.submissions}
              </span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-white/6">
              <div
                className="h-full rounded-full bg-violet-500/45"
                style={{ width: `${(row.submissions / max) * 100}%` }}
              >
                <div
                  className="h-full rounded-full bg-violet-300 transition-[width] duration-700"
                  style={{
                    width: `${
                      row.submissions > 0
                        ? (row.accepted / row.submissions) * 100
                        : 0
                    }%`,
                  }}
                />
              </div>
            </div>
          </li>
        ))}
      </ul>

      <div className="mt-5 flex items-center gap-4 border-t border-white/8 pt-4 text-xs text-violet-200/50">
        <span className="flex items-center gap-1.5">
          <span
            className="size-2.5 rounded-full bg-violet-300"
            aria-hidden="true"
          />
          Accepted
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="size-2.5 rounded-full bg-violet-500/45"
            aria-hidden="true"
          />
          All submissions
        </span>
      </div>
    </ChartCard>
  );
}

function RecentActivity({ data }: { data: DashboardData }) {
  return (
    <ChartCard title="Recent activity" subtitle="Your last ten submissions">
      {data.recent_submissions.length === 0 ? (
        <p className="py-6 text-center text-sm text-violet-200/45">
          No submissions yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {data.recent_submissions.map((submission) => (
            <li
              key={submission.id}
              className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/3 px-3 py-2.5"
            >
              <VerdictBadge verdict={submission.verdict} />
              <span className="min-w-0 flex-1 truncate font-mono text-xs text-violet-200/55">
                {LANGUAGE_LABELS[submission.language] ?? submission.language}
              </span>
              <span className="font-mono text-xs tabular-nums text-violet-200/45">
                {submission.execution_time_ms.toFixed(0)} ms
              </span>
              <span className="hidden font-mono text-xs tabular-nums text-violet-200/45 sm:inline">
                {formatMemory(submission.memory_kb)}
              </span>
              <span className="shrink-0 text-xs text-violet-200/35">
                {relativeTime(submission.created_at)}
              </span>
            </li>
          ))}
        </ul>
      )}

      <Link
        to="/submissions"
        className="mt-4 block text-center text-sm text-violet-300 hover:text-violet-200"
      >
        View all submissions →
      </Link>
    </ChartCard>
  );
}
