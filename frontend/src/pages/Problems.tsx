import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { ProblemSummary } from "../lib/types";
import {
  Alert,
  Badge,
  Card,
  DifficultyBadge,
  EmptyState,
  Input,
  PageContainer,
  PageHeading,
  Select,
  Skeleton,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "../components/ui";

const DIFFICULTIES = ["All", "Easy", "Medium", "Hard"] as const;
const PAGE_SIZE = 20;

export function Problems() {
  const { user } = useAuth();
  const [problems, setProblems] = useState<ProblemSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [difficulty, setDifficulty] = useState<(typeof DIFFICULTIES)[number]>("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .problems({
        search: search.trim() || undefined,
        difficulty: difficulty === "All" ? undefined : difficulty,
        limit: PAGE_SIZE,
        offset,
      })
      .then((res) => {
        setProblems(res.items);
        setTotal(res.total);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [search, difficulty, offset]);

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <PageContainer className="py-8">
      <PageHeading
        eyebrow="Practice"
        title="Problem Archive"
        description="Solve algorithmic challenges running inside isolated Linux containers with strict execution limits."
      />

      <div className="mb-6 flex flex-wrap items-center gap-4">
        <div className="w-full max-w-sm">
          <Input
            placeholder="Search problems by title..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
        </div>
        <div className="w-44">
          <Select
            value={difficulty}
            onChange={(e) => {
              setDifficulty(e.target.value as (typeof DIFFICULTIES)[number]);
              setOffset(0);
            }}
          >
            {DIFFICULTIES.map((d) => (
              <option key={d} value={d} className="bg-slate-900 text-white">
                {d === "All" ? "All Difficulties" : d}
              </option>
            ))}
          </Select>
        </div>

        <div className="ml-auto text-sm text-violet-200/50">
          Showing <span className="font-semibold text-violet-100">{total}</span> problems
        </div>
      </div>

      {error ? (
        <Alert tone="fail">{error}</Alert>
      ) : loading ? (
        <div className="space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : problems.length === 0 ? (
        <Card solid>
          <EmptyState
            title="No problems found"
            description="Try adjusting your search criteria or difficulty filter."
          />
        </Card>
      ) : (
        <div className="space-y-4">
          <Table>
            <Thead>
              <Tr>
                <Th className="w-12">Status</Th>
                <Th>Title</Th>
                <Th className="w-32">Difficulty</Th>
                <Th className="w-32 text-right">Action</Th>
              </Tr>
            </Thead>
            <Tbody>
              {problems.map((p) => (
                <Tr key={p.id}>
                  <Td>
                    {user && p.solved_by_me ? (
                      <Badge tone="pass">✓</Badge>
                    ) : (
                      <span className="text-violet-300/30">—</span>
                    )}
                  </Td>
                  <Td>
                    <Link
                      to={`/problems/${p.slug}`}
                      className="font-medium text-violet-100 hover:text-violet-300 transition-colors"
                    >
                      {p.title}
                    </Link>
                  </Td>
                  <Td>
                    <DifficultyBadge difficulty={p.difficulty} />
                  </Td>
                  <Td className="text-right">
                    <Link
                      to={`/problems/${p.slug}`}
                      className="btn-ghost inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-semibold text-violet-100"
                    >
                      Solve →
                    </Link>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-white/8 pt-4">
              <button
                disabled={offset === 0}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
                className="btn-ghost rounded-lg px-4 py-2 text-sm disabled:opacity-40"
              >
                ← Previous
              </button>
              <span className="text-xs font-medium text-violet-200/60">
                Page {page} of {totalPages}
              </span>
              <button
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
                className="btn-ghost rounded-lg px-4 py-2 text-sm disabled:opacity-40"
              >
                Next →
              </button>
            </div>
          )}
        </div>
      )}
    </PageContainer>
  );
}
