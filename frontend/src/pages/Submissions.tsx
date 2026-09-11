import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { LANGUAGE_LABELS, formatMemory, relativeTime } from "../lib/format";
import type { Submission } from "../lib/types";
import {
  Alert,
  Badge,
  Card,
  EmptyState,
  PageContainer,
  PageHeading,
  Skeleton,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
  VerdictBadge,
} from "../components/ui";

const PAGE_SIZE = 20;

export function Submissions() {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .submissions({ limit: PAGE_SIZE, offset })
      .then((res) => {
        setSubmissions(res.items);
        setTotal(res.total);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [offset]);

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <PageContainer className="py-8">
      <PageHeading
        eyebrow="History"
        title="My Submissions"
        description="Track all your solution evaluation attempts, execution metrics, and verdicts."
      />

      {error ? (
        <Alert tone="fail">{error}</Alert>
      ) : loading ? (
        <div className="space-y-3">
          <Skeleton className="h-12 w-full rounded" />
          <Skeleton className="h-12 w-full rounded" />
          <Skeleton className="h-12 w-full rounded" />
        </div>
      ) : submissions.length === 0 ? (
        <Card className="bg-[#141A18] border border-[#2A332F]">
          <EmptyState
            title="No submission records"
            description="Pick a problem from the archive and submit your first solution!"
          />
        </Card>
      ) : (
        <div className="space-y-4 font-mono text-xs">
          <Table>
            <Thead>
              <Tr>
                <Th className="w-16">ID</Th>
                <Th>Problem</Th>
                <Th>Language</Th>
                <Th>Status / Verdict</Th>
                <Th>Time</Th>
                <Th>Memory</Th>
                <Th className="text-right">Submitted</Th>
              </Tr>
            </Thead>
            <Tbody>
              {submissions.map((sub) => (
                <Tr key={sub.id}>
                  <Td className="font-mono text-xs text-[#A7B2AC] font-semibold">
                    #{sub.id}
                  </Td>
                  <Td>
                    <Link
                      to={`/problems/${sub.problem_id}`}
                      className="font-semibold text-[#F1F5F2] hover:text-[#B7F34A] transition-colors"
                    >
                      Problem #{sub.problem_id}
                    </Link>
                  </Td>
                  <Td className="text-xs text-[#A7B2AC]">
                    {LANGUAGE_LABELS[sub.language] ?? sub.language}
                  </Td>
                  <Td>
                    {sub.status === "QUEUED" ? (
                      <Badge tone="info">QUEUED</Badge>
                    ) : sub.status === "RUNNING" ? (
                      <Badge tone="warn">RUNNING</Badge>
                    ) : sub.status === "FAILED" ? (
                      <Badge tone="fail">FAILED</Badge>
                    ) : (
                      <VerdictBadge verdict={sub.verdict} />
                    )}
                  </Td>
                  <Td className="font-mono text-xs text-[#A7B2AC]">
                    {sub.status === "COMPLETED"
                      ? `${sub.execution_time_ms.toFixed(1)} ms`
                      : "—"}
                  </Td>
                  <Td className="font-mono text-xs text-[#A7B2AC]">
                    {sub.status === "COMPLETED"
                      ? formatMemory(sub.memory_kb)
                      : "—"}
                  </Td>
                  <Td className="text-right text-xs text-[#6F7B75]">
                    {relativeTime(sub.created_at)}
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>

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
