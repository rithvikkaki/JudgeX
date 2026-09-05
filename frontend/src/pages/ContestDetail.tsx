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
        <Link to="/contests" className="mt-4 inline-block text-sm text-violet-300">
          ← Back to contests
        </Link>
      </PageContainer>
    );
  }

  const target = contest.state === "Upcoming" ? contest.start_time : contest.end_time;

  return (
    <PageContainer key={tick} className="py-12">
      {/* Header */}
      <Card edge className="mb-8 p-6 sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0 flex-1">
            <Link
              to="/contests"
              className="mb-3 inline-block text-sm text-violet-300/70 hover:text-violet-200"
            >
              ← Contests
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
                {contest.state}
              </Badge>
              {contest.is_registered && <Badge tone="info">Registered</Badge>}
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-violet-50 sm:text-3xl">
              {contest.title}
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-violet-200/70">
              {contest.description}
            </p>

            <dl className="mt-6 flex flex-wrap gap-x-8 gap-y-2 font-mono text-xs text-violet-200/50">
              <div>
                <dt className="inline text-violet-300/50">Starts: </dt>
                <dd className="inline text-violet-100">{formatDate(contest.start_time)}</dd>
              </div>
              <div>
                <dt className="inline text-violet-300/50">Ends: </dt>
                <dd className="inline text-violet-100">{formatDate(contest.end_time)}</dd>
              </div>
              <div>
                <dt className="inline text-violet-300/50">Wrong try penalty: </dt>
                <dd className="inline text-violet-100">+{contest.penalty_minutes_per_wrong}m</dd>
              </div>
            </dl>
          </div>

          <div className="flex flex-col items-stretch gap-4 sm:items-end">
            {contest.state !== "Ended" && (
              <div className="rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-center">
                <p className="text-[10px] font-semibold tracking-wider text-violet-300/60 uppercase">
                  {contest.state === "Upcoming" ? "Starts in" : "Ends in"}
                </p>
                <p className="mt-1 font-mono text-xl font-bold tabular-nums text-violet-50">
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
                >
                  Leave contest
                </Button>
              ) : (
                <Button
                  onClick={handleJoin}
                  loading={joining}
                  disabled={joining || contest.state === "Ended"}
                >
                  Join contest
                </Button>
              )
            ) : (
              <Link
                to="/login"
                className="btn-primary block rounded-xl px-5 py-2.5 text-center text-sm font-semibold text-white"
              >
                Sign in to join
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
          <h2 className="mb-4 text-lg font-semibold text-violet-50">Problems</h2>

          {problemsLocked ? (
            <Card solid>
              <EmptyState
                title="Problems are sealed"
                description={problemsLocked}
              />
            </Card>
          ) : problems.length === 0 ? (
            <Card solid>
              <EmptyState title="No problems in this contest yet" />
            </Card>
          ) : (
            <ul className="space-y-3">
              {problems.map((entry) => (
                <li key={entry.id}>
                  <Link to={`/problems/${entry.problem.slug}`}>
                    <Card hover className="flex items-center gap-4 p-4">
                      <span
                        className="grid size-9 shrink-0 place-items-center rounded-lg border border-violet-400/25 bg-violet-400/12 font-mono text-sm font-bold text-violet-200"
                        aria-hidden="true"
                      >
                        {entry.label ?? "?"}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-semibold text-violet-50">
                          {entry.problem.title}
                        </p>
                        <p className="font-mono text-xs text-violet-200/45">
                          {entry.points} points
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
            <h2 className="text-lg font-semibold text-violet-50">Leaderboard</h2>
            {board && (
              <span className="font-mono text-xs text-violet-200/45">
                {board.total_participants} participants
              </span>
            )}
          </div>

          {!board || board.entries.length === 0 ? (
            <Card solid>
              <EmptyState
                title="No standings yet"
                description="Join the contest and submit a solution to appear here."
              />
            </Card>
          ) : (
            <div className="space-y-2">
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
                        className={isMe ? "bg-violet-400/10" : ""}
                      >
                        <Td>
                          <RankBadge rank={entry.rank} />
                        </Td>
                        <Td>
                          <span className="font-medium text-violet-50">
                            {entry.username}
                          </span>
                          {isMe && (
                            <span className="ml-2 text-[10px] font-semibold tracking-wider text-violet-300/70 uppercase">
                              you
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
                                    "grid size-5 place-items-center rounded font-mono text-[10px] font-bold",
                                    cell.solved
                                      ? "bg-emerald-400/20 text-emerald-300"
                                      : cell.attempts > 0
                                      ? "bg-rose-400/15 text-rose-300"
                                      : "bg-white/6 text-violet-200/35",
                                  ].join(" ")}
                                >
                                  {cell.label ?? "?"}
                                </span>
                              ))}
                            </div>
                          )}
                        </Td>
                        <Td className="text-right font-mono text-violet-100">
                          {entry.solved}
                        </Td>
                        <Td className="text-right font-mono font-bold text-violet-50">
                          {entry.score}
                        </Td>
                        <Td className="text-right font-mono text-violet-200/55">
                          {entry.penalty}
                        </Td>
                      </Tr>
                    );
                  })}
                </Tbody>
              </Table>

              <p className="px-2 pt-2 text-xs text-violet-200/40">
                Ranked by score, then by penalty. Penalty counts minutes to each
                solve plus {contest.penalty_minutes_per_wrong}m per rejected
                attempt on problems eventually solved.
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
      ? "border-amber-400/40 bg-amber-400/15 text-amber-300"
      : rank === 2
      ? "border-slate-300/35 bg-slate-300/12 text-slate-200"
      : rank === 3
      ? "border-orange-400/35 bg-orange-400/12 text-orange-300"
      : "border-white/10 bg-white/5 text-violet-200/60";

  return (
    <span
      className={`grid size-7 place-items-center rounded-lg border font-mono text-xs font-bold ${medal}`}
    >
      {rank}
    </span>
  );
}
