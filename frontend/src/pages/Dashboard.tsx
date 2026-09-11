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
    <Card className="p-6 bg-[#141A18] border border-[#2A332F] rounded-md shadow-lg">
      <div className="mb-5 pb-3 border-b border-[#2A332F]">
        <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#F1F5F2]">{title}</h2>
        {subtitle && (
          <p className="mt-1 text-xs text-[#A7B2AC] font-sans">{subtitle}</p>
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
      title="Verdict Distribution"
      subtitle={`${data.total_submissions} total submissions processed`}
    >
      <ul className="space-y-4">
        {rows.map((row) => {
          const share =
            data.total_submissions > 0
              ? (row.count / data.total_submissions) * 100
              : 0;
          return (
            <li key={row.verdict}>
              <div className="mb-1.5 flex items-center gap-2">
                <VerdictBadge verdict={row.verdict} />
                <span className="ml-auto font-mono text-xs font-semibold tabular-nums text-[#F1F5F2]">
                  {row.count}
                </span>
                <span className="w-12 text-right font-mono text-xs tabular-nums text-[#6F7B75]">
                  {share.toFixed(0)}%
                </span>
              </div>
              <div className="h-2 overflow-hidden bg-[#0A0F0E] border border-[#2A332F] rounded">
                <div
                  className="h-full bg-[#B7F34A] transition-[width] duration-500"
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
      title="Progress by Difficulty"
      subtitle="Distinct problems solved against total available repository"
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
                <span className="text-xs font-mono font-semibold uppercase tracking-wider text-[#F1F5F2]">
                  {row.difficulty}
                </span>
                <span className="font-mono text-xs tabular-nums text-[#A7B2AC]">
                  {row.solved}
                  <span className="text-[#6F7B75]">
                    {" "}
                    / {row.total_available}
                  </span>
                </span>
              </div>
              <div
                className="h-2 overflow-hidden bg-[#0A0F0E] border border-[#2A332F] rounded"
                role="meter"
                aria-valuenow={row.solved}
                aria-valuemin={0}
                aria-valuemax={row.total_available}
                aria-label={`${row.difficulty} problems solved`}
              >
                <div
                  className="h-full bg-[#B7F34A] transition-[width] duration-500"
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
      title="Language Breakdown"
      subtitle="Execution volume and acceptance ratio per runtime"
    >
      <ul className="space-y-4">
        {rows.map((row) => (
          <li key={row.language}>
            <div className="mb-1.5 flex items-baseline justify-between font-mono text-xs">
              <span className="font-semibold text-[#F1F5F2]">
                {LANGUAGE_LABELS[row.language] ?? row.language}
              </span>
              <span className="tabular-nums text-[#A7B2AC]">
                {row.accepted} accepted / {row.submissions} total
              </span>
            </div>
            <div className="h-2 overflow-hidden bg-[#0A0F0E] border border-[#2A332F] rounded">
              <div
                className="h-full bg-[#1A211F]"
                style={{ width: `${(row.submissions / max) * 100}%` }}
              >
                <div
                  className="h-full bg-[#B7F34A] transition-[width] duration-500"
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

      <div className="mt-5 flex items-center gap-6 border-t border-[#2A332F] pt-4 text-xs font-mono text-[#A7B2AC]">
        <span className="flex items-center gap-2">
          <span
            className="size-2 rounded-full bg-[#B7F34A]"
            aria-hidden="true"
          />
          Accepted
        </span>
        <span className="flex items-center gap-2">
          <span
            className="size-2 rounded-full bg-[#1A211F] border border-[#2A332F]"
            aria-hidden="true"
          />
          Total Submissions
        </span>
      </div>
    </ChartCard>
  );
}

function RecentActivity({ data }: { data: DashboardData }) {
  return (
    <ChartCard title="Execution Stream" subtitle="Your 10 most recent submission records">
      {data.recent_submissions.length === 0 ? (
        <p className="py-6 text-center text-xs font-mono text-[#6F7B75]">
          No execution telemetry recorded yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {data.recent_submissions.map((submission) => (
            <li
              key={submission.id}
              className="flex items-center gap-3 border border-[#2A332F] bg-[#1A211F]/60 px-3 py-2 transition-colors hover:bg-[#1A211F] rounded"
            >
              <VerdictBadge verdict={submission.verdict} />
              <span className="min-w-0 flex-1 truncate font-mono text-xs font-semibold text-[#F1F5F2]">
                {LANGUAGE_LABELS[submission.language] ?? submission.language}
              </span>
              <span className="font-mono text-xs tabular-nums text-[#A7B2AC]">
                {submission.execution_time_ms.toFixed(0)} ms
              </span>
              <span className="hidden font-mono text-xs tabular-nums text-[#A7B2AC] sm:inline">
                {formatMemory(submission.memory_kb)}
              </span>
              <span className="shrink-0 text-[11px] font-mono text-[#6F7B75]">
                {relativeTime(submission.created_at)}
              </span>
            </li>
          ))}
        </ul>
      )}

      <Link
        to="/submissions"
        className="mt-4 block text-center font-mono text-xs font-semibold text-[#B7F34A] hover:underline uppercase tracking-wider"
      >
        View Submissions Archive →
      </Link>
    </ChartCard>
  );
}
