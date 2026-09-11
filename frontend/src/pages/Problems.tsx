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
              <option key={d} value={d} className="bg-[#141A18] text-[#F1F5F2]">
                {d === "All" ? "All Difficulties" : d}
              </option>
            ))}
          </Select>
        </div>

        <div className="ml-auto text-xs font-mono text-[#A7B2AC]">
          INDEX: <span className="font-semibold text-[#B7F34A]">{total}</span> RECORDS
        </div>
      </div>

      {error ? (
        <Alert tone="fail">{error}</Alert>
      ) : loading ? (
        <div className="space-y-3">
          <Skeleton className="h-12 w-full rounded" />
          <Skeleton className="h-12 w-full rounded" />
          <Skeleton className="h-12 w-full rounded" />
          <Skeleton className="h-12 w-full rounded" />
        </div>
      ) : problems.length === 0 ? (
        <Card className="bg-[#141A18] border border-[#2A332F]">
          <EmptyState
            title="No problems matched query"
            description="Try adjusting your search query or difficulty criteria."
          />
        </Card>
      ) : (
        <div className="space-y-4">
          <Table>
            <Thead>
              <Tr>
                <Th className="w-20 text-center">Status</Th>
                <Th>Problem Title</Th>
                <Th className="w-36">Difficulty</Th>
                <Th className="w-32 text-right">Action</Th>
              </Tr>
            </Thead>
            <Tbody>
              {problems.map((p) => (
                <Tr key={p.id}>
                  <Td className="text-center font-mono">
                    {user && p.solved_by_me ? (
                      <Badge tone="pass">✓ SOLVED</Badge>
                    ) : (
                      <span className="text-[#6F7B75]">—</span>
                    )}
                  </Td>
                  <Td>
                    <Link
                      to={`/problems/${p.slug}`}
                      className="font-mono text-sm font-semibold text-[#F1F5F2] hover:text-[#B7F34A] transition-colors"
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
                      className="btn-lime px-3 py-1 text-xs font-mono font-bold uppercase tracking-wider inline-block"
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
            <div className="flex items-center justify-between border-t border-[#2A332F] pt-4 font-mono text-xs">
              <button
                disabled={offset === 0}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
                className="btn-ghost px-3 py-1.5 border border-[#2A332F] text-[#A7B2AC] disabled:opacity-30"
              >
                ← PREV
              </button>
              <span className="text-[#6F7B75]">
                PAGE {page} OF {totalPages}
              </span>
              <button
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
                className="btn-ghost px-3 py-1.5 border border-[#2A332F] text-[#A7B2AC] disabled:opacity-30"
              >
                NEXT →
              </button>
            </div>
          )}
        </div>
      )}
    </PageContainer>
  );
}
