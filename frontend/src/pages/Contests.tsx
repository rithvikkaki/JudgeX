import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { countdown, formatDate } from "../lib/format";
import type { Contest } from "../lib/types";
import {
  Alert,
  Badge,
  Card,
  EmptyState,
  PageContainer,
  PageHeading,
  Skeleton,
} from "../components/ui";

const STATE_TONE = {
  Running: "pass",
  Upcoming: "info",
  Ended: "muted",
} as const;

export function Contests() {
  const [contests, setContests] = useState<Contest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .contests({ limit: 50 })
      .then((page) => setContests(page.items))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <PageContainer className="py-12">
      <PageHeading
        eyebrow="Compete"
        title="Contests"
        description="Timed rounds with ICPC-style scoring: points on first solve, plus a penalty for time elapsed and rejected attempts."
      />

      {error && <Alert tone="fail">{error}</Alert>}

      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 2 }).map((_, index) => (
            <Skeleton key={index} className="h-40 w-full" />
          ))}
        </div>
      ) : contests.length === 0 ? (
        <Card solid>
          <EmptyState
            title="No contests yet"
            description="An administrator can create one from the API."
          />
        </Card>
      ) : (
        <div className="space-y-4">
          {contests.map((contest, index) => (
            <ContestCard key={contest.id} contest={contest} index={index} />
          ))}
        </div>
      )}
    </PageContainer>
  );
}

function ContestCard({ contest, index }: { contest: Contest; index: number }) {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (contest.state === "Ended") return;
    const timer = setInterval(() => setTick((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [contest.state]);

  const target = contest.state === "Upcoming" ? contest.start_time : contest.end_time;

  return (
    <Link
      to={`/contests/${contest.id}`}
      className="block animate-swiss-in"
      style={{ animationDelay: `${index * 50}ms` }}
      key={tick}
    >
      <Card className="p-6 bg-graphite-surface border border-graphite-border hover:border-graphite-border-hover transition-colors rounded-lg">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="mb-2.5 flex flex-wrap items-center gap-2.5">
              <Badge tone={STATE_TONE[contest.state]}>
                {contest.state === "Running" && (
                  <span
                    className="size-1.5 rounded-full bg-graphite-lime animate-pulse"
                    aria-hidden="true"
                  />
                )}
                {contest.state.toUpperCase()}
              </Badge>
              {contest.is_registered && <Badge tone="info">REGISTERED</Badge>}
            </div>

            <h2 className="text-lg font-bold font-mono tracking-tight text-graphite-text-primary group-hover:text-graphite-lime transition-colors">
              {contest.title}
            </h2>
            <p className="mt-1.5 line-clamp-2 text-xs text-graphite-text-secondary font-sans leading-relaxed">
              {contest.description}
            </p>

            <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-2 font-mono text-xs text-graphite-text-muted">
              <div className="flex gap-1.5">
                <dt className="text-graphite-text-muted">STARTS:</dt>
                <dd className="font-semibold text-graphite-text-primary">
                  {formatDate(contest.start_time)}
                </dd>
              </div>
              <div className="flex gap-1.5">
                <dt className="text-graphite-text-muted">DURATION:</dt>
                <dd className="font-semibold text-graphite-text-primary">
                  {Math.round(contest.duration_minutes / 60)}h
                </dd>
              </div>
              <div className="flex gap-1.5">
                <dt className="text-graphite-text-muted">PROBLEMS:</dt>
                <dd className="font-semibold text-graphite-text-primary">{contest.problem_count}</dd>
              </div>
              <div className="flex gap-1.5">
                <dt className="text-graphite-text-muted">PARTICIPANTS:</dt>
                <dd className="font-semibold text-graphite-text-primary">
                  {contest.participant_count}
                </dd>
              </div>
            </dl>
          </div>

          {contest.state !== "Ended" && (
            <div className="shrink-0 border border-graphite-border bg-graphite-code px-5 py-3 text-center font-mono rounded-md">
              <p className="text-[10px] font-bold tracking-wider text-graphite-text-muted uppercase">
                {contest.state === "Upcoming" ? "Starts In" : "Ends In"}
              </p>
              <p className="mt-1 font-mono text-base font-bold tabular-nums text-graphite-lime">
                {countdown(target)}
              </p>
            </div>
          )}
        </div>
      </Card>
    </Link>
  );
}
