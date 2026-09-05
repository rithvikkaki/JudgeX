# Screenshots

Every image in this folder is **generated, not hand-taken**, by
[`scripts/capture_screenshots.mjs`](../../scripts/capture_screenshots.mjs).

That matters for two reasons:

1. **They cannot drift from the UI.** A design change is one command away from
   an updated README.
2. **Every verdict is real.** The script signs in as the demo account and
   genuinely submits `print(a - b)` to get a Wrong Answer, `while True: pass`
   to get a Time Limit Exceeded, and `def broken(:` to get a Compilation Error.
   Nothing is mocked or staged.

## Regenerating

```bash
# 1. Serve the frontend build you want to document
cd frontend
npm run build
npx vite preview --port 4173

# 2. In a second terminal, from the repository root
npm --prefix scripts install playwright   # first run only
npx playwright install chromium           # first run only
node scripts/capture_screenshots.mjs
python scripts/optimise_screenshots.py    # PNG -> WebP, 36 MB -> 0.9 MB
```

Playwright can only write PNG, and 2x-scale PNGs of a dark gradient UI came to
**36 MB** for the set — far too much to carry in a repository.
`optimise_screenshots.py` downscales to 1600 px and converts to WebP, which
GitHub renders natively, bringing the set under **1 MB** with no visible loss
at README size.

Point it at any environment:

```bash
APP_URL=https://crucible-web.onrender.com \
API_URL=https://online-coding-judge-7w5q.onrender.com \
node scripts/capture_screenshots.mjs
```

| Variable | Default | Purpose |
|---|---|---|
| `APP_URL` | `http://localhost:4173` | Frontend to screenshot |
| `API_URL` | `http://localhost:8000` | API, used only for the Swagger shot |
| `DEMO_EMAIL` | `demo@example.com` | Account the script signs in as |
| `DEMO_PASSWORD` | `DemoPass123` | Its password |

## The images

| File | Shows |
|---|---|
| `01-landing-hero.webp` | Hero, live judge-status pill, editor mock |
| `02-landing-features.webp` | Feature grid and platform stats |
| `03-login.webp` | Sign-in with the demo-account shortcut |
| `04-problems.webp` | Catalogue with difficulty filters and solved markers |
| `05-solve-editor.webp` | Split statement / editor workspace |
| `06-verdict-accepted.webp` | **Accepted** — 6/6 tests, time and memory |
| `07-verdict-wrong-answer.webp` | **Wrong Answer** — failing index, sample diff |
| `08-verdict-tle.webp` | **Time Limit Exceeded** — the 2 s wall clock firing |
| `09-verdict-compile-error.webp` | **Compilation Error** — compiler diagnostics |
| `10-contests.webp` | Contest list with live countdown |
| `11-contest-leaderboard.webp` | Standings with ICPC penalties and per-problem cells |
| `12-submissions.webp` | Filterable submission history |
| `13-dashboard.webp` | Analytics: verdicts, difficulty, languages, activity |
| `14-mobile-landing.webp` | Responsive layout at 390 px |
| `15-api-docs.webp` | Generated OpenAPI documentation |

## Notes

- Captured at **2× device scale**, so they stay sharp on high-DPI displays.
- The aurora background animates, so backgrounds differ slightly between runs.
  This is cosmetic.
- Screenshots taken against a deployment running the **`local`** sandbox will
  show the fallback backend in the health pill. Run against a host with a
  Docker daemon to document the container sandbox instead.
