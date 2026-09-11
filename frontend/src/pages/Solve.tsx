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
  const [mobilePane, setMobilePane] = useState<"problem" | "code" | "output">("code");

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

  // Polling effect for async submissions
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
        // Stop polling on error
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
      setMobilePane("output");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Run failed");
      setMobilePane("output");
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
      setMobilePane("output");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Submission failed");
      setMobilePane("output");
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-[1600px] space-y-4 px-4 py-10 sm:px-6">
        <Skeleton className="h-10 w-80 rounded" />
        <div className="grid gap-5 lg:grid-cols-2">
          <Skeleton className="h-[520px] rounded" />
          <Skeleton className="h-[520px] rounded" />
        </div>
      </div>
    );
  }

  if (loadError || !problem) {
    return (
      <div className="mx-auto max-w-lg px-4 py-24">
        <Alert tone="fail">{loadError ?? "Problem not found"}</Alert>
        <Link
          to="/problems"
          className="mt-4 inline-block font-mono text-xs text-[#B7F34A] hover:underline"
        >
          ← Back to problem archive
        </Link>
      </div>
    );
  }

  const isPendingJudging =
    result?.status === "QUEUED" || result?.status === "RUNNING";

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6">
      {/* Screen reader live region */}
      <div aria-live="polite" className="sr-only">
        {isPendingJudging
          ? `Submission status is ${result?.status}`
          : result
          ? `Submission judged: ${result.verdict}`
          : ""}
      </div>

      {/* Header Bar */}
      <div className="mb-4 border border-[#2A332F] bg-[#141A18] p-4 rounded-md flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 font-mono text-xs text-[#A7B2AC] mb-1">
            <Link
              to="/problems"
              className="hover:text-[#B7F34A] transition-colors uppercase tracking-wider"
            >
              ← PROBLEMS
            </Link>
            <span>/</span>
            <span className="text-[#F1F5F2] font-semibold">{problem.slug}</span>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-[#F1F5F2] font-mono">
              {problem.title}
            </h1>
            <DifficultyBadge difficulty={problem.difficulty} />
            {problem.solved_by_me && <Badge tone="pass">✓ SOLVED</Badge>}
          </div>
        </div>

        <div className="flex items-center gap-4 font-mono text-xs text-[#A7B2AC] bg-[#1A211F] border border-[#2A332F] px-3 py-2 rounded">
          <div><span className="text-[#6F7B75]">TIME LIMIT:</span> <strong className="text-[#F1F5F2]">{problem.time_limit_ms}ms</strong></div>
          <div className="h-3 w-px bg-[#2A332F]" />
          <div><span className="text-[#6F7B75]">MEMORY LIMIT:</span> <strong className="text-[#F1F5F2]">{problem.memory_limit_mb}MB</strong></div>
          <div className="h-3 w-px bg-[#2A332F]" />
          <div><span className="text-[#6F7B75]">TEST SUITE:</span> <strong className="text-[#F1F5F2]">{problem.total_test_case_count} cases</strong></div>
        </div>
      </div>

      {/* Mobile Workspace Switcher */}
      <div className="lg:hidden flex border border-[#2A332F] bg-[#1A211F] p-1 font-mono text-xs rounded mb-3">
        {(["problem", "code", "output"] as const).map((key) => (
          <button
            key={key}
            onClick={() => setMobilePane(key)}
            className={[
              "flex-1 py-1.5 font-bold uppercase transition-colors rounded",
              mobilePane === key
                ? "bg-[#141A18] text-[#B7F34A] border border-[#2A332F]"
                : "text-[#A7B2AC] hover:text-[#F1F5F2]",
            ].join(" ")}
          >
            [ {key} ]
          </button>
        ))}
      </div>

      {/* Split Workbench Grid */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        {/* Left Pane: Statement & Specs */}
        <div className={mobilePane === "problem" ? "block" : "hidden lg:block"}>
          <Card className="bg-[#141A18] border border-[#2A332F] rounded-md overflow-hidden">
            <div className="max-h-[calc(100dvh-13rem)] space-y-6 overflow-y-auto p-6 lg:sticky lg:top-20">
              <Section title="Problem Description">
                <Markdown text={problem.description} />
              </Section>
              <Section title="Input Specification">
                <Markdown text={problem.input_format} />
              </Section>
              <Section title="Output Specification">
                <Markdown text={problem.output_format} />
              </Section>
              <Section title="Constraints">
                <div className="bg-[#0A0F0E] border border-[#2A332F] p-3 font-mono text-xs text-[#F1F5F2] whitespace-pre-wrap rounded">
                  {problem.constraints}
                </div>
              </Section>

              <div>
                <h2 className="mb-3 text-[11px] font-mono font-bold tracking-wider text-[#A7B2AC] uppercase">
                  Sample Test Cases
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
                      className="overflow-hidden border border-[#2A332F] bg-[#0A0F0E] rounded"
                    >
                      <div className="grid sm:grid-cols-2">
                        <ExampleBlock label="Sample Input" body={example.input} />
                        <div className="border-t border-[#2A332F] sm:border-t-0 sm:border-l">
                          <ExampleBlock label="Sample Output" body={example.output} />
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          setStdin(example.input);
                          setTab("input");
                          setMobilePane("output");
                        }}
                        className="w-full border-t border-[#2A332F] bg-[#1A211F] py-1.5 font-mono text-xs font-semibold text-[#B7F34A] transition-colors hover:bg-[#202824]"
                      >
                        Load into custom input ↓
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Right Pane: Code Editor & Execution Console */}
        <div className="space-y-4">
          <div className={mobilePane === "code" || mobilePane === "output" ? "block" : "hidden lg:block"}>
            <div className={mobilePane === "code" ? "block" : "hidden lg:block"}>
              <Card className="bg-[#141A18] border border-[#2A332F] rounded-md overflow-hidden mb-4">
                {/* Language Selection & Reset Toolbar */}
                <div className="flex flex-wrap items-center justify-between border-b border-[#2A332F] bg-[#1A211F] px-4 py-2.5 font-mono text-xs">
                  <div
                    className="flex gap-1"
                    role="group"
                    aria-label="Language selection"
                  >
                    {LANGUAGES.map((id) => (
                      <button
                        key={id}
                        onClick={() => setLanguage(id)}
                        aria-pressed={language === id}
                        className={[
                          "px-3 py-1 font-mono text-xs font-semibold transition-colors uppercase border rounded",
                          language === id
                            ? "bg-[#B7F34A] text-[#0D1110] border-[#B7F34A] font-bold"
                            : "bg-[#141A18] text-[#A7B2AC] border-[#2A332F] hover:bg-[#202824]",
                        ].join(" ")}
                      >
                        {LANGUAGE_LABELS[id]}
                      </button>
                    ))}
                  </div>

                  <button
                    onClick={() => persistDraft(STARTERS[language])}
                    className="text-xs font-mono text-[#6F7B75] transition-colors hover:text-[#F1F5F2] underline"
                  >
                    Reset Code
                  </button>
                </div>

                <CodeEditor
                  value={code}
                  onChange={persistDraft}
                  language={language}
                  height="420px"
                />

                {/* Controls Bar */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#2A332F] bg-[#1A211F] px-4 py-3">
                  <div className="flex items-center gap-3 w-full sm:w-auto">
                    <Button
                      variant="ghost"
                      onClick={handleRun}
                      loading={busy === "run"}
                      disabled={busy !== null || isPendingJudging || !user}
                      className="btn-secondary flex-1 sm:flex-initial px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wider justify-center"
                    >
                      ▷ Run Custom
                    </Button>
                    <Button
                      onClick={handleSubmit}
                      loading={busy === "submit" || isPendingJudging}
                      disabled={busy !== null || isPendingJudging || !user}
                      className="btn-lime flex-1 sm:flex-initial px-5 py-2 font-mono text-xs font-bold uppercase tracking-wider justify-center"
                    >
                      Submit Solution
                    </Button>
                  </div>

                  {!user && (
                    <p className="text-xs font-mono text-[#6F7B75]">
                      <Link
                        to="/login"
                        state={{ from: `/problems/${slug}` }}
                        className="font-semibold text-[#B7F34A] hover:underline"
                      >
                        Sign in
                      </Link>{" "}
                      required to judge.
                    </p>
                  )}
                </div>
              </Card>
            </div>

            {/* Console / Output Dock */}
            <div className={mobilePane === "output" ? "block" : "hidden lg:block"}>
              <Card className="bg-[#141A18] border border-[#2A332F] rounded-md overflow-hidden">
                <div className="flex border-b border-[#2A332F] bg-[#1A211F] font-mono text-xs">
                  {(["verdict", "input"] as const).map((key) => (
                    <button
                      key={key}
                      onClick={() => setTab(key)}
                      aria-pressed={tab === key}
                      className={[
                        "px-5 py-2.5 font-semibold transition-colors uppercase border-r border-[#2A332F]",
                        tab === key
                          ? "bg-[#141A18] border-t-2 border-t-[#B7F34A] text-[#B7F34A]"
                          : "text-[#A7B2AC] hover:text-[#F1F5F2] hover:bg-[#141A18]",
                      ].join(" ")}
                    >
                      {key === "verdict" ? "Execution Output" : "Custom Stdin"}
                    </button>
                  ))}
                </div>

                <div className="p-5 font-sans">
                  {tab === "input" ? (
                    <div>
                      <label
                        htmlFor="stdin"
                        className="mb-1.5 block text-[11px] font-mono font-semibold tracking-wider text-[#A7B2AC] uppercase"
                      >
                        Standard Input (stdin)
                      </label>
                      <textarea
                        id="stdin"
                        value={stdin}
                        onChange={(event) => setStdin(event.target.value)}
                        rows={5}
                        spellCheck={false}
                        className="graphite-input resize-y font-mono text-xs bg-[#0A0F0E] text-[#F1F5F2] border border-[#2A332F] focus:border-[#B7F34A]"
                        placeholder="Input fed into your program on 'Run Custom'..."
                      />
                      <p className="mt-2 text-xs font-mono text-[#6F7B75]">
                        Used only for custom test execution. <strong>Submit Solution</strong> runs against hidden judge test cases.
                      </p>
                    </div>
                  ) : actionError ? (
                    <Alert tone="fail">{actionError}</Alert>
                  ) : busy === "run" ? (
                    <JudgingState mode="run" />
                  ) : isPendingJudging && result ? (
                    <AsyncJudgingState status={result.status} />
                  ) : result ? (
                    <SubmissionResult submission={result} />
                  ) : runResult ? (
                    <RunOutput result={runResult} />
                  ) : (
                    <p className="py-8 text-center font-mono text-xs text-[#6F7B75]">
                      Ready. Press <strong>Run Custom</strong> to test code, or <strong>Submit Solution</strong> to evaluate.
                    </p>
                  )}
                </div>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- helpers */

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="mb-2 text-[11px] font-mono font-bold tracking-wider text-[#B7F34A] uppercase pb-1 border-b border-[#2A332F]">
        {title}
      </h2>
      <div className="text-xs leading-relaxed text-[#A7B2AC] font-sans">{children}</div>
    </div>
  );
}

function ExampleBlock({ label, body }: { label: string; body: string }) {
  return (
    <div className="p-3">
      <p className="mb-1 text-[10px] font-mono font-semibold tracking-wider text-[#6F7B75] uppercase">
        {label}
      </p>
      <pre className="overflow-x-auto font-mono text-xs whitespace-pre-wrap text-[#F1F5F2]">
        {body}
      </pre>
    </div>
  );
}

function JudgingState({ mode }: { mode: "run" | "submit" }) {
  return (
    <div className="flex flex-col items-center gap-3 py-8">
      <Spinner size={24} />
      <p className="font-mono text-xs text-[#A7B2AC]">
        {mode === "submit"
          ? "Transmitting payload to judge worker..."
          : "Executing code in isolated container..."}
      </p>
    </div>
  );
}

function AsyncJudgingState({ status }: { status: string }) {
  const isQueued = status === "QUEUED";

  return (
    <div className="flex flex-col items-center gap-3 py-8 text-center font-mono">
      <Spinner size={28} />
      <div>
        <h3 className="text-sm font-bold text-[#F1F5F2] uppercase">
          {isQueued ? "QUEUED IN WORKER POOL" : "EXECUTING TEST SUITE"}
        </h3>
        <p className="mt-1 text-xs text-[#A7B2AC]">
          {isQueued
            ? "Waiting for available Docker sandbox runner..."
            : "Running program against test cases..."}
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
      <div className="space-y-4 font-mono text-xs">
        <Badge tone="fail">✕ SYSTEM EXECUTION FAILED</Badge>
        <Alert tone="fail">
          {submission.error_message || "Submission processing encountered a system error."}
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-5 font-mono text-xs">
      <div className="flex flex-wrap items-center gap-3">
        <VerdictBadge verdict={submission.verdict} className="text-sm" />
        {submission.failed_test_index != null && (
          <span className="text-xs text-[#6F7B75]">
            Failed on test #{submission.failed_test_index}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric
          label="TEST SUITE"
          value={`${submission.passed_tests}/${submission.total_tests}`}
          tone={passed ? "pass" : "fail"}
        />
        <Metric label="SCORE" value={String(submission.score)} />
        <Metric label="EXEC TIME" value={`${submission.execution_time_ms.toFixed(1)} ms`} />
        <Metric label="MEMORY" value={formatMemory(submission.memory_kb)} />
      </div>

      {submission.total_tests > 0 && (
        <div>
          <div className="mb-1 flex justify-between text-xs text-[#A7B2AC]">
            <span>Pass Ratio</span>
            <span>
              {Math.round(
                (submission.passed_tests / submission.total_tests) * 100,
              )}
              %
            </span>
          </div>
          <div className="h-2 overflow-hidden bg-[#0A0F0E] border border-[#2A332F] rounded">
            <div
              className={[
                "h-full transition-[width] duration-500",
                passed ? "bg-[#B7F34A]" : "bg-[#FF6B6B]",
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
          <p className="mb-1.5 text-[11px] font-bold text-[#FF6B6B] uppercase">
            Compiler / Runtime Trace
          </p>
          <pre className="max-h-52 overflow-auto border border-[#522323] bg-[#351A1A] p-3 font-mono text-xs whitespace-pre-wrap text-[#FF6B6B] rounded">
            {submission.error_message}
          </pre>
        </div>
      )}

      {submission.test_results && submission.test_results.length > 0 && (
        <div>
          <p className="mb-2 text-[11px] font-bold text-[#A7B2AC] uppercase">
            Test Case Telemetry
          </p>
          <div className="space-y-2">
            {submission.test_results.map((test) => (
              <div
                key={test.index}
                className="border border-[#2A332F] bg-[#1A211F] p-3 rounded"
              >
                <div className="flex items-center gap-2.5">
                  <span
                    className={[
                      "flex size-5 items-center justify-center text-xs font-bold border rounded",
                      test.passed
                        ? "border-[#2A3A19] bg-[#1B2A12] text-[#B7F34A]"
                        : "border-[#522323] bg-[#351A1A] text-[#FF6B6B]",
                    ].join(" ")}
                    aria-hidden="true"
                  >
                    {test.passed ? "✓" : "✕"}
                  </span>
                  <span className="font-bold text-[#F1F5F2]">
                    Test #{test.index}
                  </span>
                  <Badge tone={test.is_sample ? "info" : "muted"}>
                    {test.is_sample ? "sample" : "hidden"}
                  </Badge>
                  <span className="ml-auto text-[#6F7B75]">
                    {test.execution_time_ms.toFixed(1)} ms
                  </span>
                </div>

                {test.is_sample && test.expected_output != null && (
                  <div className="mt-3 grid gap-2 sm:grid-cols-2 font-sans">
                    <Diff label="Expected Output" body={test.expected_output} ok />
                    <Diff
                      label="Actual Output"
                      body={test.actual_output ?? ""}
                      ok={test.passed}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-[#6F7B75]">
            * Hidden test inputs and expected outputs are concealed for evaluation integrity.
          </p>
        </div>
      )}
    </div>
  );
}

function RunOutput({ result }: { result: RunResult }) {
  const ok = result.outcome === "ok";
  return (
    <div className="space-y-4 font-mono text-xs">
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone={ok ? "pass" : "fail"}>
          {ok ? "✓ EXECUTED CLEANLY" : `✕ ${result.outcome.replace(/_/g, " ").toUpperCase()}`}
        </Badge>
        <span className="text-[#A7B2AC]">
          {result.execution_time_ms.toFixed(1)} ms · {formatMemory(result.memory_kb)} · exit code {result.exit_code}
        </span>
      </div>

      <div>
        <p className="mb-1 text-[11px] font-bold text-[#A7B2AC] uppercase">
          Standard Output (stdout)
        </p>
        <pre className="max-h-60 overflow-auto border border-[#2A332F] bg-[#0A0F0E] p-3 font-mono text-xs text-[#F1F5F2] rounded">
          {result.stdout || <span className="italic text-[#6F7B75]">(no output)</span>}
        </pre>
      </div>

      {result.stderr && (
        <div>
          <p className="mb-1 text-[11px] font-bold text-[#FF6B6B] uppercase">
            Standard Error (stderr)
          </p>
          <pre className="max-h-40 overflow-auto border border-[#522323] bg-[#351A1A] p-3 font-mono text-xs text-[#FF6B6B] rounded">
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
    <div className="border border-[#2A332F] bg-[#1A211F] p-3 text-center rounded">
      <p className="text-[10px] font-mono font-bold tracking-wider text-[#6F7B75] uppercase">
        {label}
      </p>
      <p
        className={[
          "mt-1 font-mono text-sm font-bold",
          tone === "pass"
            ? "text-[#B7F34A]"
            : tone === "fail"
            ? "text-[#FF6B6B]"
            : "text-[#F1F5F2]",
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
    <div className="border border-[#2A332F] bg-[#0A0F0E] p-2.5 rounded">
      <p
        className={[
          "mb-1 text-[10px] font-mono font-bold uppercase",
          ok ? "text-[#B7F34A]" : "text-[#FF6B6B]",
        ].join(" ")}
      >
        {label}
      </p>
      <pre className="overflow-x-auto font-mono text-xs whitespace-pre-wrap text-[#F1F5F2]">
        {body || <span className="italic text-[#6F7B75]">(empty)</span>}
      </pre>
    </div>
  );
}
