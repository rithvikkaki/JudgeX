import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { countdown, formatDate } from "../lib/format";
import type { Contest, ContestProblem, Leaderboard } from "../lib/types";
import {
  Alert,
  Badge,
  Button,
  Card,
  DifficultyBadge,
  EmptyState,
  PageContainer,
  Skeleton,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "../components/ui";

export function ContestDetail() {
  const { id = "" } = useParams();
  const { user } = useAuth();

  const [contest, setContest] = useState<Contest | null>(null);
  const [problems, setProblems] = useState<ContestProblem[]>([]);
  const [board, setBoard] = useState<Leaderboard | null>(null);
  const [problemsLocked, setProblemsLocked] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [joining, setJoining] = useState(false);
  const [tick, setTick] = useState(0);

  const load = useCallback(async () => {
    try {
      const found = await api.contest(id);
      setContest(found);

      const [problemResult, boardResult] = await Promise.allSettled([
        api.contestProblems(found.id),
        api.leaderboard(found.id),
      ]);

      if (problemResult.status === "fulfilled") {
        setProblems(problemResult.value);
        setProblemsLocked(null);
      } else {
        setProblemsLocked(
          problemResult.reason?.message ?? "Problems are not available yet",
        );
      }

      if (boardResult.status === "fulfilled") setBoard(boardResult.value);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Contest not found");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (contest?.state === "Ended") return;
    const timer = setInterval(() => setTick((v) => v + 1), 1000);
    return () => clearInterval(timer);
  }, [contest?.state]);

  async function handleJoin() {
    if (!contest) return;
    setJoining(true);
    try {
      await api.joinContest(contest.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not join contest");
    } finally {
      setJoining(false);
    }
  }

  async function handleLeave() {
    if (!contest) return;
    setJoining(true);
    try {
      await api.leaveContest(contest.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not leave contest");
    } finally {
      setJoining(false);
    }
  }

  if (loading) {
    return (
      <PageContainer className="py-12 space-y-6">
        <Skeleton className="h-40 w-full" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </PageContainer>
    );
  }

  if (!contest) {
    return (
      <PageContainer className="py-24 max-w-lg">
        <Alert tone="fail">{error ?? "Contest not found"}</Alert>
        <Link to="/contests" className="mt-4 inline-block text-xs font-mono text-graphite-lime hover:underline">
          ← BACK TO CONTESTS
        </Link>
      </PageContainer>
    );
  }

  const target = contest.state === "Upcoming" ? contest.start_time : contest.end_time;

  return (
    <PageContainer key={tick} className="py-10">
      {/* Header */}
      <Card className="mb-8 p-6 sm:p-8 bg-graphite-surface border border-graphite-border rounded-lg">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0 flex-1">
            <Link
              to="/contests"
              className="mb-3 inline-block font-mono text-xs text-graphite-text-muted hover:text-graphite-lime uppercase tracking-wider transition-colors"
            >
              ← CONTESTS
            </Link>
            <div className="mb-2 flex flex-wrap items-center gap-2.5">
              <Badge
                tone={
                  contest.state === "Running"
                    ? "pass"
                    : contest.state === "Upcoming"
                    ? "info"
                    : "muted"
                }
              >
                {contest.state.toUpperCase()}
              </Badge>
              {contest.is_registered && <Badge tone="info">REGISTERED</Badge>}
            </div>
            <h1 className="text-2xl font-bold font-mono tracking-tight text-graphite-text-primary sm:text-3xl">
              {contest.title}
            </h1>
            <p className="mt-2 text-xs leading-relaxed text-graphite-text-secondary font-sans">
              {contest.description}
            </p>

            <dl className="mt-6 flex flex-wrap gap-x-8 gap-y-2 font-mono text-xs text-graphite-text-muted">
              <div>
                <dt className="inline text-graphite-text-muted">STARTS: </dt>
                <dd className="inline font-semibold text-graphite-text-primary">{formatDate(contest.start_time)}</dd>
              </div>
              <div>
                <dt className="inline text-graphite-text-muted">ENDS: </dt>
                <dd className="inline font-semibold text-graphite-text-primary">{formatDate(contest.end_time)}</dd>
              </div>
              <div>
                <dt className="inline text-graphite-text-muted">WRONG ATTEMPT PENALTY: </dt>
                <dd className="inline font-semibold text-graphite-text-primary">+{contest.penalty_minutes_per_wrong}m</dd>
              </div>
            </dl>
          </div>

          <div className="flex flex-col items-stretch gap-4 sm:items-end font-mono">
            {contest.state !== "Ended" && (
              <div className="border border-graphite-border bg-graphite-code px-6 py-3 text-center rounded-md">
                <p className="text-[10px] font-bold tracking-wider text-graphite-text-muted uppercase">
                  {contest.state === "Upcoming" ? "Starts In" : "Ends In"}
                </p>
                <p className="mt-1 font-mono text-xl font-bold tabular-nums text-graphite-lime">
                  {countdown(target)}
                </p>
              </div>
            )}

            {user ? (
              contest.is_registered ? (
                <Button
                  variant="ghost"
                  onClick={handleLeave}
                  loading={joining}
                  disabled={joining || contest.state === "Ended"}
                  className="btn-ghost text-xs font-mono font-semibold"
                >
                  Leave Contest
                </Button>
              ) : (
                <Button
                  onClick={handleJoin}
                  loading={joining}
                  disabled={joining || contest.state === "Ended"}
                  className="btn-lime text-xs font-mono font-semibold uppercase tracking-wider"
                >
                  Register for Contest
                </Button>
              )
            ) : (
              <Link
                to="/login"
                className="btn-lime block px-5 py-2.5 text-center text-xs font-mono font-semibold uppercase tracking-wider rounded-md"
              >
                Sign In To Participate
              </Link>
            )}
          </div>
        </div>
      </Card>

      {error && (
        <div className="mb-6">
          <Alert tone="fail">{error}</Alert>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        {/* Problems */}
        <section>
          <h2 className="mb-4 text-xs font-mono font-bold tracking-wider text-graphite-text-primary uppercase">Contest Problems</h2>

          {problemsLocked ? (
            <Card className="bg-graphite-surface border border-graphite-border">
              <EmptyState
                title="Problems Are Sealed"
                description={problemsLocked}
              />
            </Card>
          ) : problems.length === 0 ? (
            <Card className="bg-graphite-surface border border-graphite-border">
              <EmptyState title="No problems assigned to contest" />
            </Card>
          ) : (
            <ul className="space-y-3">
              {problems.map((entry) => (
                <li key={entry.id}>
                  <Link to={`/problems/${entry.problem.slug}`}>
                    <Card className="flex items-center gap-4 p-4 bg-graphite-surface border border-graphite-border hover:border-graphite-border-hover transition-colors rounded-lg">
                      <span
                        className="flex size-9 shrink-0 items-center justify-center border border-graphite-border bg-graphite-code font-mono text-sm font-bold text-graphite-lime rounded-md"
                        aria-hidden="true"
                      >
                        {entry.label ?? "?"}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-mono text-sm font-semibold text-graphite-text-primary">
                          {entry.problem.title}
                        </p>
                        <p className="font-mono text-xs text-graphite-text-muted">
                          {entry.points} PTS
                        </p>
                      </div>
                      <DifficultyBadge difficulty={entry.problem.difficulty} />
                    </Card>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Leaderboard */}
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xs font-mono font-bold tracking-wider text-graphite-text-primary uppercase">Live Standings Scoreboard</h2>
            {board && (
              <span className="font-mono text-xs text-graphite-text-muted">
                {board.total_participants} PARTICIPANTS
              </span>
            )}
          </div>

          {!board || board.entries.length === 0 ? (
            <Card className="bg-graphite-surface border border-graphite-border">
              <EmptyState
                title="No standings recorded"
                description="Register for the contest and submit solutions to appear on the matrix."
              />
            </Card>
          ) : (
            <div className="space-y-2 font-mono text-xs">
              <Table>
                <Thead>
                  <Tr>
                    <Th className="w-14">#</Th>
                    <Th>User</Th>
                    <Th className="text-right">Solved</Th>
                    <Th className="text-right">Score</Th>
                    <Th className="text-right">Penalty</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {board.entries.map((entry) => {
                    const isMe = user?.username === entry.username;
                    return (
                      <Tr
                        key={entry.user_id}
                        className={isMe ? "bg-graphite-lime/10 font-semibold border-l-2 border-l-graphite-lime" : ""}
                      >
                        <Td>
                          <RankBadge rank={entry.rank} />
                        </Td>
                        <Td>
                          <span className="font-semibold text-graphite-text-primary">
                            {entry.username}
                          </span>
                          {isMe && (
                            <span className="ml-2 text-[10px] font-mono font-bold text-graphite-lime uppercase">
                              (YOU)
                            </span>
                          )}
                          {entry.problems.some((cell) => cell.solved) && (
                            <div className="mt-1.5 flex gap-1">
                              {entry.problems.map((cell) => (
                                <span
                                  key={cell.problem_id}
                                  title={
                                    cell.solved
                                      ? `${cell.label ?? "?"} solved at +${cell.solved_at_minutes}m (${cell.attempts} attempt${cell.attempts === 1 ? "" : "s"})`
                                      : `${cell.label ?? "?"} unsolved`
                                  }
                                  className={[
                                    "flex size-5 items-center justify-center font-mono text-[10px] font-bold border rounded-sm",
                                    cell.solved
                                      ? "bg-emerald-950/60 border-emerald-600/60 text-emerald-400"
                                      : cell.attempts > 0
                                      ? "bg-rose-950/60 border-rose-600/60 text-rose-400"
                                      : "bg-graphite-code border-graphite-border text-graphite-text-muted",
                                  ].join(" ")}
                                >
                                  {cell.label ?? "?"}
                                </span>
                              ))}
                            </div>
                          )}
                        </Td>
                        <Td className="text-right font-mono text-graphite-text-secondary">
                          {entry.solved}
                        </Td>
                        <Td className="text-right font-mono font-bold text-graphite-lime">
                          {entry.score}
                        </Td>
                        <Td className="text-right font-mono text-graphite-text-muted">
                          {entry.penalty}
                        </Td>
                      </Tr>
                    );
                  })}
                </Tbody>
              </Table>

              <p className="px-2 pt-2 text-[11px] font-mono text-graphite-text-muted">
                Scoreboard ordered by score, then penalty time. Penalty includes elapsed minutes to each solve plus +{contest.penalty_minutes_per_wrong}m per rejected submission.
              </p>
            </div>
          )}
        </section>
      </div>
    </PageContainer>
  );
}

function RankBadge({ rank }: { rank: number }) {
  const medal =
    rank === 1
      ? "border-amber-500/60 bg-amber-950/50 text-amber-300 font-mono"
      : rank === 2
      ? "border-slate-400/60 bg-slate-800/60 text-slate-200 font-mono"
      : rank === 3
      ? "border-amber-600/60 bg-amber-950/30 text-amber-500 font-mono"
      : "border-graphite-border bg-graphite-subtle text-graphite-text-muted font-mono";

  return (
    <span
      className={`flex size-7 items-center justify-center border font-mono text-xs font-bold rounded-md ${medal}`}
    >
      {rank}
    </span>
  );
}
