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
      className="block animate-rise"
      style={{ animationDelay: `${index * 70}ms` }}
      key={tick}
    >
      <Card hover edge className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex flex-wrap items-center gap-2.5">
              <Badge tone={STATE_TONE[contest.state]}>
                {contest.state === "Running" && (
                  <span
                    className="size-1.5 rounded-full bg-current animate-pulse-ring"
                    aria-hidden="true"
                  />
                )}
                {contest.state}
              </Badge>
              {contest.is_registered && <Badge tone="info">Registered</Badge>}
            </div>

            <h2 className="text-xl font-bold tracking-tight text-violet-50">
              {contest.title}
            </h2>
            <p className="mt-1.5 line-clamp-2 text-sm text-violet-200/60">
              {contest.description}
            </p>

            <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-2 font-mono text-xs text-violet-200/50">
              <div className="flex gap-1.5">
                <dt>Starts</dt>
                <dd className="text-violet-100/80">
                  {formatDate(contest.start_time)}
                </dd>
              </div>
              <div className="flex gap-1.5">
                <dt>Duration</dt>
                <dd className="text-violet-100/80">
                  {Math.round(contest.duration_minutes / 60)}h
                </dd>
              </div>
              <div className="flex gap-1.5">
                <dt>Problems</dt>
                <dd className="text-violet-100/80">{contest.problem_count}</dd>
              </div>
              <div className="flex gap-1.5">
                <dt>Participants</dt>
                <dd className="text-violet-100/80">
                  {contest.participant_count}
                </dd>
              </div>
            </dl>
          </div>

          {contest.state !== "Ended" && (
            <div className="shrink-0 rounded-xl border border-white/10 bg-white/5 px-5 py-3 text-center">
              <p className="text-[10px] font-semibold tracking-wider text-violet-300/60 uppercase">
                {contest.state === "Upcoming" ? "Starts in" : "Ends in"}
              </p>
              <p className="mt-1 font-mono text-lg font-bold tabular-nums text-violet-50">
                {countdown(target)}
              </p>
            </div>
          )}
        </div>
      </Card>
    </Link>
  );
}
