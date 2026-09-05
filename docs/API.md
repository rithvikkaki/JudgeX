# API reference

**Base URL** — `https://online-coding-judge-7w5q.onrender.com/api/v1`
**Interactive** — [Swagger UI](https://online-coding-judge-7w5q.onrender.com/docs) ·
[ReDoc](https://online-coding-judge-7w5q.onrender.com/redoc) ·
[OpenAPI JSON](https://online-coding-judge-7w5q.onrender.com/openapi.json)

Locally the base is `http://localhost:8000/api/v1`.

- [Conventions](#conventions)
- [Authentication](#authentication)
- [Problems](#problems)
- [Test cases](#test-cases)
- [Submissions](#submissions)
- [Contests](#contests)
- [Contest problems](#contest-problems)
- [Dashboard](#dashboard)
- [System](#system)
- [Worked examples](#worked-examples)

---

## Conventions

### Access levels

| Symbol | Meaning |
|---|---|
| 🌐 | Public — no token required |
| 🔑 | Any authenticated user |
| 👑 | Administrator only |

### Authentication

Send the bearer token issued by `/auth/register` or `/auth/login`:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

Tokens are HS256 JWTs. The subject is the **user id**, not the email, so a token
stays valid if the address changes. Default lifetime is 24 hours
(`ACCESS_TOKEN_EXPIRE_MINUTES`).

### Status codes

| Code | Meaning |
|---|---|
| `200` | Success |
| `201` | Created — registration, problems and contests |
| `202` | Accepted — submission queued for asynchronous judging |
| `400` | Malformed request (e.g. problem not in that contest) |
| `401` | Missing, invalid or expired token |
| `403` | Authenticated but not permitted — non-admin write, another user's source |
| `404` | Not found, **or** deliberately hidden (unpublished problems) |
| `409` | Conflict — duplicate, already joined, contest closed, no test cases |
| `422` | Validation failed |
| `500` | Judge failure |
| `503` | Database unreachable |

### Error shape

A plain error:

```json
{ "detail": "Invalid email or password" }
```

A validation failure is flattened so a client can render each message beside its
input:

```json
{
  "detail": "Validation failed",
  "errors": [
    { "field": "password", "message": "Password must mix letters with digits or symbols" },
    { "field": "email",    "message": "value is not a valid email address" }
  ]
}
```

### Pagination

List endpoints take `limit` (1–100, default 20) and `offset`, and return:

```json
{ "items": [ ... ], "total": 42, "limit": 20, "offset": 0 }
```

`total` is the count matching the filter, not the page size.

### Response headers

`X-Process-Time-Ms` — server-side handling time, on every response.

---

## Authentication

### `POST /auth/register` 🌐

Create an account and receive a token immediately.

```json
{ "username": "ada_lovelace", "email": "ada@example.com", "password": "str0ng-passw0rd" }
```

| Field | Rules |
|---|---|
| `username` | 3–50 chars; letters, digits, `_`, `.`, `-` |
| `email` | Valid address; compared case-insensitively. Reserved TLDs such as `.local` are rejected |
| `password` | 8–128 chars, must mix letters with digits or symbols, ≤ 72 bytes UTF-8 |

**`201`**

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": 2, "username": "ada_lovelace", "email": "ada@example.com",
    "is_admin": false, "created_at": "2026-08-12T09:14:22Z"
  }
}
```

`409` if the username or email is taken. An email listed in `ADMIN_EMAILS`
receives `is_admin: true` — that is how a fresh deployment gets its first
administrator.

> The 72-byte cap is not arbitrary: bcrypt silently ignores input beyond 72
> bytes, which would make two different long passwords interchangeable.
> Registration rejects them rather than mislead.

### `POST /auth/login` 🌐

```json
{ "email": "ada@example.com", "password": "str0ng-passw0rd" }
```

Returns the same shape as register. `401` on bad credentials.

> An unknown email is verified against a dummy hash so a wrong email and a wrong
> password take the same time and return an identical message. Neither confirms
> whether an account exists.

### `GET /auth/me` 🔑

The current account.

---

## Problems

### `GET /problems` 🌐

| Query | Type | Notes |
|---|---|---|
| `search` | string | Case-insensitive title match |
| `difficulty` | `Easy` \| `Medium` \| `Hard` | |
| `solved` | bool | Filter by your own solve status; needs a token |
| `limit` / `offset` | int | Pagination |

```json
{
  "items": [{
    "id": 1, "slug": "sum-of-two-numbers", "title": "Sum of Two Numbers",
    "difficulty": "Easy", "time_limit_ms": 2000, "memory_limit_mb": 128,
    "created_at": "2026-08-11T10:22:00Z",
    "solved_by_me": true, "attempted_by_me": true,
    "total_submissions": 18, "accepted_submissions": 8
  }],
  "total": 6, "limit": 20, "offset": 0
}
```

`solved_by_me` and `attempted_by_me` are `null` for anonymous callers. The
aggregate counts are computed in two grouped queries for the whole page, not one
query per row.

### `GET /problems/{id|slug}` 🌐

Accepts a numeric id or a slug. Adds the statement plus
`sample_test_case_count` and `total_test_case_count`.

Unpublished problems return **`404` to non-admins** — not `403`, so their
existence is not leaked.

### `POST /problems` 👑

```json
{
  "title": "Two Sum", "description": "Given two integers...",
  "difficulty": "Easy",
  "input_format": "...", "output_format": "...", "constraints": "...",
  "sample_input": "2 3", "sample_output": "5",
  "time_limit_ms": 2000, "memory_limit_mb": 128, "is_public": true
}
```

The slug is derived from the title, with a `-2`, `-3`… suffix on collision.
`409` if the title exists.

### `PATCH /problems/{id}` 👑

A genuine PATCH — every field optional, only supplied fields change. Changing
the title regenerates the slug.

### `DELETE /problems/{id}` 👑

Cascades to test cases, submissions and contest links.

---

## Test cases

> **The security-relevant endpoints.** Hidden test data is never returned to a
> non-admin — not blanked client-side, simply never serialised.

### `GET /testcases/problem/{problem_id}` 🌐

Samples in full; hidden cases carry `input_data: null` and
`expected_output: null`.

```json
[
  { "id": 1, "problem_id": 1, "is_sample": true,  "order_index": 0,
    "input_data": "2 3", "expected_output": "5" },
  { "id": 3, "problem_id": 1, "is_sample": false, "order_index": 2,
    "input_data": null,  "expected_output": null }
]
```

### `GET /testcases/problem/{problem_id}/admin` 👑

The full suite including hidden data.

### `POST /testcases/problem/{problem_id}` 👑

```json
{ "input_data": "10 20", "expected_output": "30", "is_sample": false, "order_index": 1 }
```

### `POST /testcases/problem/{problem_id}/bulk` 👑

Upload a whole suite; `replace_existing` deletes the current one first.

```json
{
  "test_cases": [
    { "input_data": "2 3",   "expected_output": "5",  "is_sample": true },
    { "input_data": "10 20", "expected_output": "30" }
  ],
  "replace_existing": true
}
```

### `PATCH /testcases/{id}` 👑 · `DELETE /testcases/{id}` 👑

---

## Submissions

### `GET /submissions/languages` 🌐

```json
[
  { "id": "python", "name": "Python 3.11", "compiled": true,  "docker_image": "python:3.11-slim" },
  { "id": "cpp",    "name": "C++17 (GCC)", "compiled": true,  "docker_image": "gcc:13" },
  { "id": "java",   "name": "Java 21",     "compiled": true,  "docker_image": "eclipse-temurin:21-jdk" }
]
```

### `POST /submissions` 🔑

Creates a submission, queues it for judging, and returns immediately. Poll
`GET /submissions/{id}` or `GET /submissions` for status changes.

```json
{
  "problem_id": 1,
  "language": "python",
  "source_code": "a, b = map(int, input().split())\nprint(a + b)",
  "contest_id": null
}
```

**`202`**

```jsonc
{
  "id": 42, "user_id": 2, "problem_id": 1, "contest_id": null,
  "language": "python", "status": "Queued",
  "verdict": "Pending", "score": 0,
  "passed_tests": 0, "total_tests": 6,
  "execution_time_ms": 0.0, "memory_kb": 0,
  "execution_time_display": "0.00 ms", "memory_display": "0 KB",
  "failed_test_index": null, "error_message": null,
  "created_at": "2026-08-12T09:20:11Z",
  "source_code": "a, b = map(int, input().split())\nprint(a + b)"
}
```

After the worker finishes, the same submission reads as `status: "Completed"`
with a final verdict such as `Accepted`, `Wrong Answer`, `Runtime Error` or
`Compilation Error`. If the queue or worker infrastructure fails before a
reliable verdict exists, the row is marked `Failed` with `Internal Error`.

Errors:

| Code | Cause |
|---|---|
| `404` | Problem not found, or unpublished and you are not an admin |
| `409` | Problem has no test cases; or contest not started / already ended |
| `403` | Contest submission without an active registration |
| `400` | That problem is not part of that contest |
| `503` | Submission was created but could not be queued; the row is marked failed |

Contest submissions are validated on three counts — **registered**, **window
open**, **problem belongs to the contest** — before anything executes.

### `POST /submissions/run` 🔑

Run against custom input. Nothing is persisted, no verdict is produced.

```json
{ "language": "python", "source_code": "print(input())", "stdin": "hello", "problem_id": 1 }
```

```json
{
  "outcome": "ok", "stdout": "hello", "stderr": "", "exit_code": 0,
  "execution_time_ms": 41.2, "memory_kb": 8900,
  "compile_output": null, "backend": "local"
}
```

`outcome` is one of `ok`, `compile_error`, `timeout`, `memory_exceeded`,
`output_exceeded`, `runtime_error`, `internal_error`. Passing `problem_id`
inherits that problem's limits.

### `GET /submissions` 🔑

Your history. Filters: `problem_id`, `contest_id`, `verdict`, `language`, plus
pagination. Newest first. Does **not** include source code.

### `GET /submissions/problem/{problem_id}` 🔑

Fastest accepted solutions for a problem, ordered by execution time. Source code
is withheld.

### `GET /submissions/{id}` 🔑

One submission **including its source code**. `403` unless you are its author or
an admin.

---

## Contests

### `GET /contests` 🌐

`state` filters by `Upcoming` / `Running` / `Ended` — derived from the window in
SQL, not by fetching everything and filtering in Python.

```json
{
  "items": [{
    "id": 1, "slug": "practice-round-1", "title": "Practice Round #1",
    "description": "...",
    "start_time": "2026-08-11T09:00:00Z", "end_time": "2027-08-11T09:00:00Z",
    "duration_minutes": 525600, "penalty_minutes_per_wrong": 20,
    "state": "Running", "problem_count": 4, "participant_count": 2,
    "is_registered": true, "created_at": "2026-08-11T09:00:00Z"
  }],
  "total": 1, "limit": 20, "offset": 0
}
```

### `GET /contests/{id|slug}` 🌐 · `POST /contests` 👑 · `PATCH /contests/{id}` 👑 · `DELETE /contests/{id}` 👑

```json
{
  "title": "Weekly Round #1", "description": "...",
  "start_time": "2026-09-01T14:00:00Z",
  "end_time":   "2026-09-01T17:00:00Z",
  "penalty_minutes_per_wrong": 20
}
```

`422` if `end_time <= start_time`. Naive timestamps are assumed UTC.

### `POST /contests/{id}/join` 🔑

`409` if already registered, or if the contest has ended. The unique constraint
is the arbiter, so concurrent joins cannot both succeed.

### `DELETE /contests/{id}/join` 🔑

Withdraw.

### `GET /contests/{id}/participants` 🌐

### `GET /contests/{id}/leaderboard` 🌐

```json
{
  "contest_id": 1, "contest_title": "Practice Round #1",
  "state": "Running", "total_participants": 2,
  "entries": [{
    "rank": 1, "user_id": 3, "username": "rival",
    "solved": 1, "score": 100, "penalty": 30,
    "problems": [
      { "problem_id": 1, "label": "A", "solved": true,
        "attempts": 1, "points": 100, "solved_at_minutes": 30 }
    ]
  }]
}
```

📖 **[Exact scoring rules →](ARCHITECTURE.md#contest-scoring)**

---

## Contest problems

### `GET /contests/{id}/problems` 🌐

**`409` while the contest is `Upcoming`** for non-admins — the problem set is
sealed until the clock starts.

```json
[{
  "id": 1, "contest_id": 1, "problem_id": 1,
  "label": "A", "points": 100, "order_index": 0,
  "problem": { "id": 1, "slug": "sum-of-two-numbers", "title": "Sum of Two Numbers", "difficulty": "Easy" }
}]
```

### `POST /contests/{id}/problems` 👑

```json
{ "problem_id": 1, "label": "A", "points": 100, "order_index": 0 }
```

`label` auto-assigns A, B, C… (and AA, AB… beyond 26). `409` on duplicates.

### `PATCH /contests/{id}/problems/{problem_id}` 👑 · `DELETE /contests/{id}/problems/{problem_id}` 👑

---

## Dashboard

### `GET /dashboard` 🔑

Every figure is a grouped SQL aggregate, so cost stays flat as history grows.

```json
{
  "username": "demo", "email": "demo@example.com",
  "total_submissions": 20, "accepted_submissions": 8,
  "acceptance_rate": 40.0,
  "problems_solved": 6, "problems_attempted": 6,
  "contests_participated": 1, "best_contest_rank": null,
  "verdict_breakdown": [
    { "verdict": "Accepted", "count": 8 },
    { "verdict": "Wrong Answer", "count": 2 }
  ],
  "difficulty_progress": [
    { "difficulty": "Easy", "solved": 3, "total_available": 3 }
  ],
  "language_usage": [
    { "language": "python", "submissions": 18, "accepted": 8 }
  ],
  "recent_submissions": [ /* last 10 */ ]
}
```

`problems_solved` counts **distinct problems**, not accepted submissions.

---

## System

### `GET /health` 🌐

What this instance is really running.

```json
{
  "status": "ok", "version": "1.0.0", "environment": "production",
  "database": { "connected": true, "dialect": "postgresql", "latency_ms": 190.04 },
  "execution": {
    "configured": "local", "active": "local", "available": true,
    "rlimits_enforced": true,
    "toolchains": { "python": true, "cpp": true, "java": false },
    "warning": "Subprocess isolation only - no network or filesystem namespace."
  },
  "languages": ["python", "cpp", "java"]
}
```

Returns `503` when the database is unreachable. `toolchains` reports which
compilers actually exist on the running host — which is how you can tell that
Java is unavailable on the hosted demo.

### `GET /ping` 🌐

`{"status": "ok"}` — the platform health check.

---

## Worked examples

### Register, submit, read the verdict

```bash
BASE=https://online-coding-judge-7w5q.onrender.com/api/v1

TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"DemoPass123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST $BASE/submissions \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
        "problem_id": 1,
        "language": "python",
        "source_code": "a,b=map(int,input().split())\nprint(a+b)"
      }' | python -m json.tool
```

### Author a problem end to end (admin)

```bash
PROBLEM=$(curl -s -X POST $BASE/problems \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{
        "title":"Double It","description":"Print 2n for the given n.",
        "difficulty":"Easy","input_format":"One integer n","output_format":"2n",
        "constraints":"1 <= n <= 10^9","sample_input":"4","sample_output":"8"
      }' | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST $BASE/testcases/problem/$PROBLEM/bulk \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"test_cases":[
        {"input_data":"4","expected_output":"8","is_sample":true},
        {"input_data":"1000000000","expected_output":"2000000000"}
      ]}'
```

### Run a contest

```bash
CONTEST=$(curl -s -X POST $BASE/contests \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Weekly #1","description":"Three hours.",
       "start_time":"2026-09-01T14:00:00Z","end_time":"2026-09-01T17:00:00Z"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST $BASE/contests/$CONTEST/problems \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"problem_id":1,"points":100}'

curl -s -X POST $BASE/contests/$CONTEST/join -H "Authorization: Bearer $TOKEN"

curl -s -X POST $BASE/submissions \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"problem_id\":1,\"language\":\"python\",
       \"source_code\":\"a,b=map(int,input().split())\\nprint(a+b)\",
       \"contest_id\":$CONTEST}"

curl -s $BASE/contests/$CONTEST/leaderboard | python -m json.tool
```

### Confirm hidden test data is not exposed

```bash
# Anonymous: hidden cases come back with null input and expected output
curl -s $BASE/testcases/problem/1 | python -m json.tool
```
