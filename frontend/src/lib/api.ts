import type {
  AuthResponse,
  Contest,
  ContestProblem,
  Dashboard,
  Health,
  Leaderboard,
  Page,
  Problem,
  ProblemSummary,
  RunResult,
  Submission,
  TestCasePublic,
  User,
} from "./types";

const BASE = (
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export const API_BASE = `${BASE}/api/v1`;

const TOKEN_KEY = "judgex.token";
const LEGACY_TOKEN_KEY = "crucible.token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(LEGACY_TOKEN_KEY),
  set: (token: string) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
  },
};

export class ApiError extends Error {
  // Declared explicitly rather than as constructor parameter properties, which
  // tsconfig's `erasableSyntaxOnly` disallows.
  status: number;
  fieldErrors?: { field: string; message: string }[];

  constructor(
    status: number,
    message: string,
    fieldErrors?: { field: string; message: string }[],
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

/** Raised when the request never reached the server at all. */
export class NetworkError extends Error {
  constructor(message = "Could not reach the judge") {
    super(message);
    this.name = "NetworkError";
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  /** Judging can legitimately take a while; callers override the default. */
  timeoutMs?: number;
  signal?: AbortSignal;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    method = "GET",
    body,
    auth = true,
    timeoutMs = 30_000,
    signal,
  } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const token = tokenStore.get();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  // Own timeout controller, merged with any caller-supplied signal.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  signal?.addEventListener("abort", () => controller.abort());

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (error) {
    clearTimeout(timer);
    if ((error as Error).name === "AbortError") {
      throw new NetworkError(
        "The judge took too long to respond. It may be waking from sleep — try again.",
      );
    }
    throw new NetworkError();
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let payload: unknown = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const data = payload as
      | { detail?: string; errors?: { field: string; message: string }[] }
      | null;

    // An expired or invalid token should log the user out rather than leave
    // the UI in a half-authenticated state.
    if (response.status === 401 && auth && token) {
      tokenStore.clear();
      window.dispatchEvent(new CustomEvent("judgex:unauthorised"));
      window.dispatchEvent(new CustomEvent("crucible:unauthorised"));
    }

    throw new ApiError(
      response.status,
      data?.detail ?? `Request failed (${response.status})`,
      data?.errors,
    );
  }

  return payload as T;
}

const qs = (params: Record<string, unknown>) => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
};

export const api = {
  // ---- system ----------------------------------------------------------
  ping: () => request<{ status: string }>("/ping", { auth: false, timeoutMs: 90_000 }),
  health: () => request<Health>("/health", { auth: false }),

  // ---- auth ------------------------------------------------------------
  register: (body: { username: string; email: string; password: string }) =>
    request<AuthResponse>("/auth/register", { method: "POST", body, auth: false }),
  login: (body: { email: string; password: string }) =>
    request<AuthResponse>("/auth/login", { method: "POST", body, auth: false }),
  me: () => request<User>("/auth/me"),

  // ---- problems --------------------------------------------------------
  problems: (params: {
    search?: string;
    difficulty?: string;
    limit?: number;
    offset?: number;
  }) => request<Page<ProblemSummary>>(`/problems${qs(params)}`),
  problem: (identifier: string | number) => request<Problem>(`/problems/${identifier}`),
  testCases: (problemId: number) =>
    request<TestCasePublic[]>(`/testcases/problem/${problemId}`),

  // ---- submissions -----------------------------------------------------
  submit: (body: {
    problem_id: number;
    language: string;
    source_code: string;
    contest_id?: number;
  }) =>
    // Judging is synchronous and bounded by (tests x time limit), so this
    // needs far more headroom than a normal read.
    request<Submission>("/submissions", { method: "POST", body, timeoutMs: 120_000 }),
  run: (body: {
    language: string;
    source_code: string;
    stdin: string;
    problem_id?: number;
  }) => request<RunResult>("/submissions/run", { method: "POST", body, timeoutMs: 120_000 }),
  submissions: (params: {
    problem_id?: number;
    contest_id?: number;
    verdict?: string;
    language?: string;
    limit?: number;
    offset?: number;
  }) => request<Page<Submission>>(`/submissions${qs(params)}`),
  submission: (id: number) => request<Submission>(`/submissions/${id}`),
  languages: () =>
    request<{ id: string; name: string; compiled: boolean }[]>("/submissions/languages", {
      auth: false,
    }),

  // ---- contests --------------------------------------------------------
  contests: (params: { state?: string; limit?: number; offset?: number }) =>
    request<Page<Contest>>(`/contests${qs(params)}`),
  contest: (identifier: string | number) => request<Contest>(`/contests/${identifier}`),
  contestProblems: (contestId: number) =>
    request<ContestProblem[]>(`/contests/${contestId}/problems`),
  joinContest: (contestId: number) =>
    request<unknown>(`/contests/${contestId}/join`, { method: "POST" }),
  leaveContest: (contestId: number) =>
    request<unknown>(`/contests/${contestId}/join`, { method: "DELETE" }),
  leaderboard: (contestId: number) =>
    request<Leaderboard>(`/contests/${contestId}/leaderboard`),

  // ---- dashboard -------------------------------------------------------
  dashboard: () => request<Dashboard>("/dashboard"),
};
