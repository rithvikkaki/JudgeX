# Development

Getting the project running locally, how it is laid out, and how to work on it.

- [Three ways to run it](#three-ways-to-run-it)
- [Project layout](#project-layout)
- [The frontend](#the-frontend)
- [Seed data](#seed-data)
- [Testing](#testing)
- [Regenerating screenshots](#regenerating-screenshots)
- [Common tasks](#common-tasks)
- [Conventions](#conventions)
- [Troubleshooting](#troubleshooting)

---

## Three ways to run it

| Mode | Database | Sandbox | Use when |
|---|---|---|---|
| **A — SQLite** | File | `local` | Fastest start. Everything works except real isolation |
| **B — Docker Compose** | Postgres container + Redis | **`docker`** | You need the real container sandbox, the worker, or all three languages |
| **C — Local Postgres** | Your own server + Redis | `local` or `docker` | You want Postgres without Compose |

### Prerequisites

- **Python 3.11+**
- **Node 18+** (for the frontend)
- **Docker Desktop** — only for mode B
- **Redis** — required whenever you run asynchronous submission judging outside Compose
- `g++` and a JDK on `PATH` if you want C++/Java under mode A or C

### Mode A — SQLite, zero setup

```bash
git clone https://github.com/dhanoliya-ji/ONLINE-CODING-JUDGE.git
cd ONLINE-CODING-JUDGE

python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
copy .env.example .env           # cp on macOS / Linux
```

Edit `.env` and set `ADMIN_EMAILS` to the address you will register with.
Everything else works as shipped.

```bash
python -m scripts.seed --reset
uvicorn app.main:app --reload
```

- API — <http://localhost:8000>
- Swagger — <http://localhost:8000/docs>
- Health — <http://localhost:8000/api/v1/health>

In another terminal, start Redis and the judge worker:

```bash
redis-server
celery -A app.celery_app.celery_app worker --loglevel=info --concurrency=1
```

`POST /submissions` writes a queued row and returns immediately. The Celery
worker performs the full judge run and updates the row; clients poll
`GET /submissions/{id}` or `GET /submissions`.

### Mode B — Docker Compose, real sandbox

```bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
export ADMIN_EMAILS=you@example.com

docker compose up --build
docker compose exec api python -m scripts.seed --reset
```

Pre-pull the language images once, or the first submission in each language
waits on a download:

```bash
docker pull python:3.11-slim
docker pull gcc:13
docker pull eclipse-temurin:21-jdk
```

Confirm the API, worker, Redis and container sandbox are active:

```bash
curl -s localhost:8000/api/v1/health | python -m json.tool
# -> "execution": { "active": "docker", "isolation": { ... } }
docker compose exec redis redis-cli ping
docker compose logs worker
```

> ⚠️ Compose mounts `/var/run/docker.sock` into the API container — that is
> root-equivalent access to your host. Fine locally; see
> [Security](SECURITY.md#deployment-hardening) before doing it anywhere else.

### Mode C — Local Postgres

```bash
createdb online_judge
```

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/online_judge
```

```bash
python -m scripts.seed --reset
uvicorn app.main:app --reload
celery -A app.celery_app.celery_app worker --loglevel=info --concurrency=1
```

---

## Project layout

```
ONLINE-CODING-JUDGE/
├── app/
│   ├── config.py                 Settings, validated at import; fails fast
│   ├── database.py               Engine + session factory (Postgres/SQLite)
│   ├── main.py                   App factory, middleware, error handlers, lifespan
│   │
│   ├── dependencies/
│   │   ├── auth.py               get_current_user / get_current_admin / optional
│   │   └── database.py           Request-scoped session with rollback
│   │
│   ├── execution/                ── the judge engine ──
│   │   ├── base.py               SandboxBackend interface, Outcome, results
│   │   ├── languages.py          Per-language compile/run recipes
│   │   ├── docker_backend.py     Container-per-run sandbox
│   │   ├── local_backend.py      rlimit subprocess fallback
│   │   ├── engine.py             Backend selection
│   │   └── judge.py              Pipeline: order → run → compare → verdict
│   │
│   ├── models/                   SQLAlchemy 2.0 typed models
│   ├── routes/                   7 resource domains + health
│   ├── schemas/                  Pydantic request/response models
│   ├── services/                 leaderboard.py · stats.py · submissions.py
│   ├── tasks/                    Celery task adapters
│   ├── celery_app.py             Celery app wired to Redis
│   └── utils/                    jwt.py · security.py · slug.py
│
├── frontend/                     React SPA — see below
├── scripts/
│   ├── seed.py                   6 problems, 1 contest, 2 accounts
│   ├── verify_seed.py            Judges a reference solution per problem
│   ├── set_password.py           Change a password without re-seeding
│   ├── capture_screenshots.mjs   Generates docs/screenshots/
│   └── optimise_screenshots.py   PNG → WebP
│
├── tests/                        88 tests
├── docs/                         This documentation
├── Dockerfile                    Ships Python + GCC + JDK
├── docker-compose.yml            Postgres + Redis + API + worker
├── render.yaml                   Both Render services
└── requirements.txt
```

---

## The frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

`frontend/.env.development` already points at `http://localhost:8000`, so no
configuration is needed when the API is running locally.

| Command | Does |
|---|---|
| `npm run dev` | Dev server with HMR |
| `npm run build` | Type-check (`tsc -b`) then build to `dist/` |
| `npm run preview` | Serve the production build |

📖 **[Design system and component structure →](../frontend/README.md)**

---

## Seed data

`python -m scripts.seed` creates:

| | |
|---|---|
| **Accounts** | `admin@example.com` (or the first entry in `ADMIN_EMAILS`) and `demo@example.com` |
| **Problems** | 6 — three Easy, two Medium, one Hard, with 31 test cases |
| **Contest** | "Practice Round #1" — already open, running for a year, four problems |

It is **idempotent**: re-running will not duplicate rows. `--reset` drops every
table first.

Override the passwords when seeding anything reachable from the internet:

```bash
SEED_ADMIN_PASSWORD='...' SEED_DEMO_PASSWORD='...' python -m scripts.seed --reset
```

Verify the bundled test data is self-consistent:

```bash
python scripts/verify_seed.py
```

This judges a known-correct solution against every seeded problem, so a wrong
expected output fails in CI rather than confusing the first user who tries it.

---

## Testing

```bash
pytest                              # all tests
pytest -v                           # verbose
pytest tests/test_judging.py        # one module
pytest -k leaderboard               # by name
pytest -x                           # stop at first failure
```

The suite runs on SQLite with the `local` backend, so it needs no Postgres and
no Docker daemon. `tests/conftest.py` sets the environment **before**
`app.config` is first imported, and each test gets a freshly created and dropped
schema.

### Fixtures

| Fixture | Provides |
|---|---|
| `client` | `TestClient` over the real app |
| `admin_headers` | Bearer token for an administrator |
| `user_headers` | Bearer token for `alice`, a normal user |
| `problem_id` | A published "a + b" problem with 1 sample and 2 hidden cases |

Reference solutions are exported from `conftest.py` as `SOLUTION_ACCEPTED`,
`SOLUTION_WRONG`, `SOLUTION_RUNTIME_ERROR`, `SOLUTION_SYNTAX_ERROR`,
`SOLUTION_INFINITE_LOOP`.

### What the modules pin

| Module | Guards |
|---|---|
| `test_auth.py` | Duplicates, weak passwords, case-insensitive email, enumeration resistance |
| `test_problems.py` | RBAC, filters, slug lookup, draft visibility, PATCH semantics |
| `test_test_cases.py` | **Hidden data redaction**, admin access, bulk upload, cascade |
| `test_judging.py` | Every verdict, scoring, redaction, source privacy, normalisation |
| `test_contests.py` | Windows, state, registration, **leaderboard scoring rules** |
| `test_dashboard.py` | Aggregates, division-by-zero, per-caller scoping |
| `test_execution_backend.py` | **A backend must never raise**, stream separation, limits, secret scrubbing |
| `test_packaging.py` | Encoding of files non-Python tooling reads |
| `test_health.py` | Health payload, OpenAPI, timing header |

### CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs the suite, then
seeds and verifies the bundled data, then builds the Docker image and checks the
container answers its health check.

---

## Regenerating screenshots

The images in `docs/screenshots/` are generated, so they never drift from the
UI, and every verdict shown is produced by really submitting that code.

```bash
# Terminal 1 — serve the build you want to document
cd frontend && npm run build && npx vite preview --port 4173

# Terminal 2 — from the repository root
npm --prefix scripts install playwright   # first run only
npx playwright install chromium           # first run only
node scripts/capture_screenshots.mjs
python scripts/optimise_screenshots.py    # 36 MB → 0.9 MB
```

Point it anywhere:

```bash
APP_URL=https://crucible-web.onrender.com \
API_URL=https://online-coding-judge-7w5q.onrender.com \
node scripts/capture_screenshots.mjs
```

📖 **[Details →](screenshots/README.md)**

---

## Common tasks

### Add a language

One `LanguageSpec` in `app/execution/languages.py` — neither backend contains
language-specific branching:

```python
Language.GO.value: LanguageSpec(
    id="go",
    display_name="Go 1.23",
    source_filename="main.go",
    compile_cmd=["go", "build", "-o", "solution", "main.go"],
    run_cmd=["./solution"],
    docker_image="golang:1.23",
    local_requirements=("go",),
    artifact="solution",
),
```

Then add the value to `Language` in `app/models/enums.py`, add the toolchain to
the `Dockerfile`, and add a CodeMirror mode plus a starter in
`frontend/src/components/CodeEditor.tsx`.

### Add an endpoint

1. Schema in `app/schemas/`
2. Handler in the relevant `app/routes/` module
3. Guard it with `get_current_user` or `get_current_admin`
4. Test it

New routers are registered in `app/routes/__init__.py`.

### Change the schema

`Base.metadata.create_all()` runs on startup and creates **missing tables only**.
It will not alter an existing table. In development, drop and re-seed:

```bash
python -m scripts.seed --reset
```

For production data you need Alembic — see
[Architecture](ARCHITECTURE.md#design-decisions).

### Promote a user to admin

```bash
python scripts/set_password.py them@example.com --make-admin
```

---

## Conventions

**Python** — 4 spaces, 88-column soft limit, double quotes, `from __future__ import annotations`, type hints everywhere. Comments explain *why*, not *what*.

**SQLAlchemy** — 2.0 typed style (`Mapped[...]`, `mapped_column`), `select()` over legacy `Query`, relationships declared on both sides with explicit `cascade`.

**FastAPI** — one router per resource; handlers stay thin; validation in schemas, not handlers; response models on every route.

**TypeScript** — strict mode; `frontend/src/lib/types.ts` mirrors the API exactly; no `any`.

**Tests** — one behaviour per test; names describe the guarantee (`test_hidden_test_data_never_leaves_the_server`); a comment above non-obvious assertions explaining the bug they prevent.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: app` | Run from the repository root, with the venv activated |
| `DATABASE_URL must not be empty` | `.env` is missing — copy `.env.example` |
| Tests fail with a locked database | A stale `uvicorn` still holds the SQLite file; stop it |
| Every submission is Internal Error | No toolchain. Check `/api/v1/health` → `execution.toolchains` |
| Docker backend not selected | Docker Desktop is not running. `/health` reports the reason |
| Frontend calls fail with CORS errors | API not running, or `CORS_ORIGINS` excludes `http://localhost:5173` |
| `/docs` renders blank | Swagger's assets come from `cdn.jsdelivr.net`; an ad-blocker may block it |
| C++/Java report "toolchain is not installed" | `g++`/`javac` are not on `PATH`. Use mode B, which ships both |
