import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { LANGUAGE_LABELS, formatMemory } from "../lib/format";
import type {
  LanguageId,
  Problem,
  RunResult,
  Submission,
  TestCasePublic,
} from "../lib/types";
import { CodeEditor, STARTERS } from "../components/CodeEditor";
import { Markdown } from "../components/Markdown";
import {
  Alert,
  Badge,
  Button,
  Card,
  DifficultyBadge,
  Skeleton,
  VerdictBadge,
  Spinner,
} from "../components/ui";

const LANGUAGES: LanguageId[] = ["python", "cpp", "java"];

const draftKey = (slug: string, language: string) =>
  `judgex.draft.${slug}.${language}`;
const legacyDraftKey = (slug: string, language: string) =>
  `crucible.draft.${slug}.${language}`;

export function Solve() {
  const { slug = "" } = useParams();
  const { user } = useAuth();

  const [problem, setProblem] = useState<Problem | null>(null);
  const [samples, setSamples] = useState<TestCasePublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [language, setLanguage] = useState<LanguageId>("python");
  const [code, setCode] = useState("");
  const [stdin, setStdin] = useState("");

  const [result, setResult] = useState<Submission | null>(null);
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [busy, setBusy] = useState<"run" | "submit" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [tab, setTab] = useState<"verdict" | "input">("verdict");

  useEffect(() => {
    setLoading(true);
    setLoadError(null);

    api
      .problem(slug)
      .then(async (found) => {
        setProblem(found);
        setStdin(found.sample_input);
        try {
          const cases = await api.testCases(found.id);
          setSamples(cases.filter((testCase) => testCase.is_sample));
        } catch {
          setSamples([]);
        }
      })
      .catch((error) => setLoadError(error.message))
      .finally(() => setLoading(false));
  }, [slug]);

  useEffect(() => {
    if (!slug) return;
    const saved =
      localStorage.getItem(draftKey(slug, language)) ??
      localStorage.getItem(legacyDraftKey(slug, language));
    setCode(saved ?? STARTERS[language]);
  }, [slug, language]);

  const persistDraft = useCallback(
    (next: string) => {
      setCode(next);
      if (slug) localStorage.setItem(draftKey(slug, language), next);
    },
    [slug, language],
  );

  // Polling effect for async submissions (QUEUED / RUNNING -> COMPLETED / FAILED)
  useEffect(() => {
    if (!result) return;
    const status = result.status;
    if (status !== "QUEUED" && status !== "RUNNING") return;

    let cancelled = false;
    let timerId: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const updated = await api.submission(result.id);
        if (!cancelled) {
          setResult(updated);
          if (updated.status === "QUEUED" || updated.status === "RUNNING") {
            timerId = setTimeout(poll, 1500);
          }
        }
      } catch {
        // Stop polling on error to prevent infinite loops
      }
    };

    timerId = setTimeout(poll, 1500);

    return () => {
      cancelled = true;
      clearTimeout(timerId);
    };
  }, [result]);

  async function handleRun() {
    if (!problem) return;
    setBusy("run");
    setActionError(null);
    setResult(null);
    try {
      setRunResult(
        await api.run({
          language,
          source_code: code,
          stdin,
          problem_id: problem.id,
        }),
      );
      setTab("verdict");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Run failed");
    } finally {
      setBusy(null);
    }
  }

  async function handleSubmit() {
    if (!problem) return;
    setBusy("submit");
    setActionError(null);
    setRunResult(null);
    try {
      const sub = await api.submit({
        problem_id: problem.id,
        language,
        source_code: code,
      });
      setResult(sub);
      setTab("verdict");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Submission failed");
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-[1600px] space-y-4 px-4 py-10 sm:px-6">
        <Skeleton className="h-10 w-80" />
        <div className="grid gap-5 lg:grid-cols-2">
          <Skeleton className="h-[520px]" />
          <Skeleton className="h-[520px]" />
        </div>
      </div>
    );
  }

  if (loadError || !problem) {
    return (
      <div className="mx-auto max-w-lg px-4 py-24">
        <Alert>{loadError ?? "Problem not found"}</Alert>
        <Link
          to="/problems"
          className="mt-4 inline-block text-sm text-violet-300 hover:text-violet-200"
        >
          ← Back to problems
        </Link>
      </div>
    );
  }

  const isPendingJudging =
    result?.status === "QUEUED" || result?.status === "RUNNING";

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-8 sm:px-6">
      {/* Screen reader live region for status transitions */}
      <div aria-live="polite" className="sr-only">
        {isPendingJudging
          ? `Submission status is ${result?.status}`
          : result
          ? `Submission judged: ${result.verdict}`
          : ""}
      </div>

      {/* Header */}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            to="/problems"
            className="mb-2 inline-block text-sm text-violet-300/70 hover:text-violet-200"
          >
            ← Problems
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-violet-50 sm:text-3xl">
              {problem.title}
            </h1>
            <DifficultyBadge difficulty={problem.difficulty} />
            {problem.solved_by_me && <Badge tone="pass">✓ Solved</Badge>}
          </div>
          <p className="mt-2 font-mono text-xs text-violet-200/45">
            {problem.time_limit_ms} ms · {problem.memory_limit_mb} MB ·{" "}
            {problem.total_test_case_count} tests (
            {problem.sample_test_case_count} shown)
          </p>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        {/* Statement */}
        <Card solid className="overflow-hidden">
          <div className="max-h-[calc(100dvh-14rem)] space-y-6 overflow-y-auto p-6 lg:sticky lg:top-20">
            <Section title="Problem">
              <Markdown text={problem.description} />
            </Section>
            <Section title="Input">
              <Markdown text={problem.input_format} />
            </Section>
            <Section title="Output">
              <Markdown text={problem.output_format} />
            </Section>
            <Section title="Constraints">
              <p className="whitespace-pre-wrap font-mono text-[13px]">
                {problem.constraints}
              </p>
            </Section>

            <div>
              <h2 className="mb-3 text-xs font-semibold tracking-[0.16em] text-violet-300/70 uppercase">
                Examples
              </h2>
              <div className="space-y-3">
                {(samples.length > 0
                  ? samples.map((s) => ({
                      input: s.input_data ?? "",
                      output: s.expected_output ?? "",
                    }))
                  : [
                      {
                        input: problem.sample_input,
                        output: problem.sample_output,
                      },
                    ]
                ).map((example, index) => (
                  <div
                    key={index}
                    className="overflow-hidden rounded-xl border border-white/10 bg-black/25"
                  >
                    <div className="grid sm:grid-cols-2">
                      <ExampleBlock label="Input" body={example.input} />
                      <div className="border-t border-white/8 sm:border-t-0 sm:border-l">
                        <ExampleBlock label="Output" body={example.output} />
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        setStdin(example.input);
                        setTab("input");
                      }}
                      className="w-full border-t border-white/8 py-2 text-xs text-violet-300/70 transition-colors hover:bg-white/5 hover:text-violet-200"
                    >
                      Load into custom input ↓
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>

        {/* Workspace */}
        <div className="space-y-4">
          <Card solid className="overflow-hidden">
            <div className="flex flex-wrap items-center gap-2 border-b border-white/8 px-4 py-3">
              <div
                className="flex gap-1 rounded-lg border border-white/10 bg-white/5 p-1"
                role="group"
                aria-label="Language"
              >
                {LANGUAGES.map((id) => (
                  <button
                    key={id}
                    onClick={() => setLanguage(id)}
                    aria-pressed={language === id}
                    className={[
                      "rounded-md px-3 py-1.5 text-xs font-semibold transition-colors",
                      language === id
                        ? "bg-white/12 text-violet-50"
                        : "text-violet-200/55 hover:text-violet-100",
                    ].join(" ")}
                  >
                    {LANGUAGE_LABELS[id]}
                  </button>
                ))}
              </div>

              <button
                onClick={() => persistDraft(STARTERS[language])}
                className="ml-auto text-xs text-violet-300/60 transition-colors hover:text-violet-200"
              >
                Reset code
              </button>
            </div>

            <CodeEditor
              value={code}
              onChange={persistDraft}
              language={language}
              height="440px"
            />

            <div className="flex flex-wrap items-center gap-3 border-t border-white/8 px-4 py-3">
              <Button
                variant="ghost"
                onClick={handleRun}
                loading={busy === "run"}
                disabled={busy !== null || isPendingJudging || !user}
              >
                ▷ Run
              </Button>
              <Button
                onClick={handleSubmit}
                loading={busy === "submit" || isPendingJudging}
                disabled={busy !== null || isPendingJudging || !user}
              >
                Submit solution
              </Button>

              {!user && (
                <p className="text-sm text-violet-200/55">
                  <Link
                    to="/login"
                    state={{ from: `/problems/${slug}` }}
                    className="font-semibold text-violet-300 hover:text-violet-200"
                  >
                    Sign in
                  </Link>{" "}
                  to run or submit.
                </p>
              )}
            </div>
          </Card>

          {/* Results */}
          <Card solid className="overflow-hidden">
            <div className="flex border-b border-white/8">
              {(["verdict", "input"] as const).map((key) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  aria-pressed={tab === key}
                  className={[
                    "px-5 py-3 text-sm font-medium transition-colors",
                    tab === key
                      ? "border-b-2 border-violet-400 text-violet-50"
                      : "text-violet-200/50 hover:text-violet-100",
                  ].join(" ")}
                >
                  {key === "verdict" ? "Result" : "Custom input"}
                </button>
              ))}
            </div>

            <div className="p-5">
              {tab === "input" ? (
                <div>
                  <label
                    htmlFor="stdin"
                    className="mb-2 block text-xs font-semibold tracking-wide text-violet-200/70 uppercase"
                  >
                    stdin
                  </label>
                  <textarea
                    id="stdin"
                    value={stdin}
                    onChange={(event) => setStdin(event.target.value)}
                    rows={6}
                    spellCheck={false}
                    className="field resize-y font-mono text-sm"
                    placeholder="Input passed to your program when you press Run"
                  />
                  <p className="mt-2 text-xs text-violet-200/40">
                    Used by <strong>Run</strong> only. <strong>Submit</strong>{" "}
                    always uses the full hidden test suite.
                  </p>
                </div>
              ) : actionError ? (
                <Alert>{actionError}</Alert>
              ) : busy === "run" ? (
                <JudgingState mode="run" />
              ) : isPendingJudging && result ? (
                <AsyncJudgingState status={result.status} />
              ) : result ? (
                <SubmissionResult submission={result} />
              ) : runResult ? (
                <RunOutput result={runResult} />
              ) : (
                <p className="py-8 text-center text-sm text-violet-200/45">
                  Run your code against custom input, or submit it to be judged
                  against every test case.
                </p>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- helpers */

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="mb-2 text-xs font-semibold tracking-[0.16em] text-violet-300/70 uppercase">
        {title}
      </h2>
      <div className="text-sm leading-relaxed text-violet-100/80">{children}</div>
    </div>
  );
}

function ExampleBlock({ label, body }: { label: string; body: string }) {
  return (
    <div className="p-3.5">
      <p className="mb-1.5 text-[10px] font-semibold tracking-wider text-violet-300/50 uppercase">
        {label}
      </p>
      <pre className="overflow-x-auto font-mono text-[13px] whitespace-pre-wrap text-violet-100/90">
        {body}
      </pre>
    </div>
  );
}

function JudgingState({ mode }: { mode: "run" | "submit" }) {
  return (
    <div className="flex flex-col items-center gap-3 py-10">
      <Spinner size={24} />
      <p className="text-sm text-violet-200/70">
        {mode === "submit"
          ? "Preparing submission..."
          : "Running your code..."}
      </p>
    </div>
  );
}

function AsyncJudgingState({ status }: { status: string }) {
  const isQueued = status === "QUEUED";

  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <Spinner size={28} />
      <div>
        <h3 className="text-base font-semibold text-violet-50">
          {isQueued ? "Queued" : "Running"}
        </h3>
        <p className="mt-1 text-sm text-violet-200/70">
          {isQueued
            ? "Waiting for a judge worker..."
            : "Executing your submission..."}
        </p>
      </div>
      <Badge tone={isQueued ? "info" : "warn"} className="mt-1">
        {status}
      </Badge>
    </div>
  );
}

function SubmissionResult({ submission }: { submission: Submission }) {
  const passed = submission.verdict === "Accepted";

  if (submission.status === "FAILED") {
    return (
      <div className="space-y-4">
        <Badge tone="fail">✕ FAILED</Badge>
        <Alert tone="fail">
          {submission.error_message || "Submission processing failed."}
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <VerdictBadge verdict={submission.verdict} className="text-sm" />
        {submission.failed_test_index != null && (
          <span className="font-mono text-xs text-violet-200/55">
            failed at test #{submission.failed_test_index}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric
          label="Tests"
          value={`${submission.passed_tests}/${submission.total_tests}`}
          tone={passed ? "pass" : "fail"}
        />
        <Metric label="Score" value={String(submission.score)} />
        <Metric label="Time" value={`${submission.execution_time_ms.toFixed(1)} ms`} />
        <Metric label="Memory" value={formatMemory(submission.memory_kb)} />
      </div>

      {submission.total_tests > 0 && (
        <div>
          <div className="mb-1.5 flex justify-between text-xs text-violet-200/50">
            <span>Test suite</span>
            <span className="font-mono">
              {Math.round(
                (submission.passed_tests / submission.total_tests) * 100,
              )}
              %
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/8">
            <div
              className={[
                "h-full rounded-full transition-[width] duration-700",
                passed
                  ? "bg-gradient-to-r from-emerald-400 to-teal-300"
                  : "bg-gradient-to-r from-rose-400 to-orange-300",
              ].join(" ")}
              style={{
                width: `${(submission.passed_tests / submission.total_tests) * 100}%`,
              }}
            />
          </div>
        </div>
      )}

      {submission.error_message && (
        <div>
          <p className="mb-2 text-xs font-semibold tracking-wide text-violet-200/60 uppercase">
            Details
          </p>
          <pre className="max-h-52 overflow-auto rounded-xl border border-rose-400/20 bg-rose-950/25 p-3.5 font-mono text-xs whitespace-pre-wrap text-rose-200/90">
            {submission.error_message}
          </pre>
        </div>
      )}

      {submission.test_results && submission.test_results.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold tracking-wide text-violet-200/60 uppercase">
            Per-test results
          </p>
          <div className="space-y-2">
            {submission.test_results.map((test) => (
              <div
                key={test.index}
                className="rounded-xl border border-white/10 bg-white/4 p-3"
              >
                <div className="flex items-center gap-2.5">
                  <span
                    className={[
                      "grid size-6 place-items-center rounded-md text-xs font-bold",
                      test.passed
                        ? "bg-emerald-400/15 text-emerald-300"
                        : "bg-rose-400/15 text-rose-300",
                    ].join(" ")}
                    aria-hidden="true"
                  >
                    {test.passed ? "✓" : "✕"}
                  </span>
                  <span className="text-sm text-violet-100">
                    Test {test.index}
                  </span>
                  <Badge tone={test.is_sample ? "info" : "muted"}>
                    {test.is_sample ? "sample" : "hidden"}
                  </Badge>
                  <span className="ml-auto font-mono text-xs text-violet-200/45">
                    {test.execution_time_ms.toFixed(1)} ms
                  </span>
                </div>

                {test.is_sample && test.expected_output != null && (
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <Diff label="Expected" body={test.expected_output} ok />
                    <Diff
                      label="Your output"
                      body={test.actual_output ?? ""}
                      ok={test.passed}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-violet-200/35">
            Hidden test inputs and expected outputs are never sent to the
            browser.
          </p>
        </div>
      )}
    </div>
  );
}

function RunOutput({ result }: { result: RunResult }) {
  const ok = result.outcome === "ok";
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone={ok ? "pass" : "fail"}>
          {ok ? "✓ Ran" : `✕ ${result.outcome.replace(/_/g, " ")}`}
        </Badge>
        <span className="font-mono text-xs text-violet-200/50">
          {result.execution_time_ms.toFixed(1)} ms ·{" "}
          {formatMemory(result.memory_kb)} · exit {result.exit_code}
        </span>
      </div>

      <div>
        <p className="mb-1 text-xs font-semibold text-violet-300/60 uppercase">
          stdout
        </p>
        <pre className="max-h-60 overflow-auto rounded-xl border border-white/10 bg-black/30 p-3 font-mono text-xs text-violet-100">
          {result.stdout || <span className="italic opacity-50">(empty)</span>}
        </pre>
      </div>

      {result.stderr && (
        <div>
          <p className="mb-1 text-xs font-semibold text-rose-300/80 uppercase">
            stderr
          </p>
          <pre className="max-h-40 overflow-auto rounded-xl border border-rose-400/20 bg-rose-950/30 p-3 font-mono text-xs text-rose-200">
            {result.stderr}
          </pre>
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "pass" | "fail";
}) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/4 p-3 text-center">
      <p className="text-[10px] font-semibold tracking-wider text-violet-300/50 uppercase">
        {label}
      </p>
      <p
        className={[
          "mt-1 font-mono text-base font-bold",
          tone === "pass"
            ? "text-emerald-300"
            : tone === "fail"
            ? "text-rose-300"
            : "text-violet-50",
        ].join(" ")}
      >
        {value}
      </p>
    </div>
  );
}

function Diff({
  label,
  body,
  ok,
}: {
  label: string;
  body: string;
  ok: boolean;
}) {
  return (
    <div className="rounded-lg border border-white/8 bg-black/30 p-2.5">
      <p
        className={[
          "mb-1 text-[10px] font-semibold uppercase",
          ok ? "text-emerald-300/70" : "text-rose-300/70",
        ].join(" ")}
      >
        {label}
      </p>
      <pre className="overflow-x-auto font-mono text-xs whitespace-pre-wrap text-violet-100">
        {body || <span className="italic opacity-50">(empty)</span>}
      </pre>
    </div>
  );
}
