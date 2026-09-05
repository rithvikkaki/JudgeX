# Security

Running a stranger's code on your server is the entire problem this project
exists to solve. This document states exactly what is defended, how, and — just
as importantly — **what is not**.

- [Threat model](#threat-model)
- [The Docker sandbox](#the-docker-sandbox)
- [The local sandbox, stated plainly](#the-local-sandbox-stated-plainly)
- [What the hosted demo does not protect](#what-the-hosted-demo-does-not-protect)
- [Application security](#application-security)
- [Data protection](#data-protection)
- [Deployment hardening](#deployment-hardening)
- [Reporting an issue](#reporting-an-issue)

---

## Threat model

**The adversary** is any user who can submit source code — which, since
registration is open, is anyone on the internet.

**What they control:** arbitrary source in Python, C++ or Java, executed on our
infrastructure, with the compiler and interpreter of their choice.

**What we are protecting:**

| Asset | Why it matters |
|---|---|
| The host | A sandbox escape is a full compromise |
| Other submissions | One user must not read or influence another's run |
| Hidden test data | It is the answer key for every problem |
| Database credentials | They grant full read/write to all user data |
| Availability | A fork bomb or infinite loop must not take the service down |
| Other users' source code | Private to its author |

**Explicit non-goals:** this is not a multi-tenant SaaS. There is no audit log,
no secrets rotation policy, and no DDoS protection beyond what the host provides.

---

## The Docker sandbox

The real one. Each execution creates a throw-away container:

| Control | Setting | What it stops |
|---|---|---|
| Network | `network_disabled=True` | Exfiltration, callbacks, using your host as a proxy |
| Memory | `mem_limit=128m`, `memswap_limit=128m` | Exhaustion. Swap is pinned to the same value, so the cap cannot be escaped by swapping |
| CPU | `cpu_quota=50000` / `cpu_period=100000` | One submission monopolising a core |
| Processes | `pids_limit=64` | Fork bombs |
| Filesystem | `read_only=True` + `tmpfs /tmp` (`noexec`, `nosuid`) | Tampering with the image; writing and executing new binaries |
| Privileges | `cap_drop=["ALL"]`, `no-new-privileges:true` | Capability abuse and setuid escalation |
| Identity | `user=65534:65534` (`nobody`) | Anything requiring root inside the container |
| Wall clock | Host-side `wait(timeout)`, then `kill` | Programs that ignore or outlive an internal timer |
| Output | 64 KB cap → Output Limit Exceeded | Filling disk or memory with a print loop |
| Source mount | `ro` during execution | The program rewriting its own inputs |

### Two-container split

Compilation and execution run in **separate containers**. The compile step gets
a writable mount; the run step gets a read-only one. That split is what makes
Compilation Error a distinguishable verdict rather than a confusing runtime
failure — and it means a compiler exploit cannot persist into the run phase.

### Measurement

Peak memory is sampled from the live Docker stats stream by a monitor thread.
OOM kills are detected via the container's `State.OOMKilled` flag rather than
inferred from an exit code.

### Java

Java skips `RLIMIT_AS` deliberately: the JVM reserves a large virtual address
space at startup and would be killed instantly. It is capped with `-Xmx` plus
the container's own `mem_limit`, which is the real ceiling regardless.

---

## The local sandbox, stated plainly

Where no Docker daemon is reachable — most notably on free PaaS tiers —
`LocalBackend` applies POSIX `rlimit` ceilings in the child before `exec`:

| Limit | Purpose |
|---|---|
| `RLIMIT_AS` | Virtual address space — the memory cap |
| `RLIMIT_CPU` | CPU seconds, a backstop for the wall clock |
| `RLIMIT_NPROC` | Process count — defeats fork bombs |
| `RLIMIT_FSIZE` | Maximum file size the program may write |
| `RLIMIT_CORE = 0` | No core dumps |

The child also gets its own process group, so a timeout kills the whole tree,
and a deliberately minimal environment.

### ⚠️ This is meaningfully weaker than the container sandbox

**There is no network namespace and no filesystem namespace.** Submitted code
can:

- open sockets and reach the internet
- read any file the API process can read
- read `/proc`, including other processes owned by the same user

It exists so the project is demonstrable on free hosting. **Do not run it on a
public deployment with real users or real data.**
`GET /api/v1/health` always reports which backend is live.

---

## What the hosted demo does not protect

The live demo runs the local backend, and this is the concrete consequence.

Submitted code runs as the **same OS user** as the API process. Since `/proc` is
readable, a user can submit:

```python
print(open("/proc/1/environ").read())
```

and recover the API's environment — **including `DATABASE_URL` and
`SECRET_KEY`**.

### What is mitigated

The child process gets a **scrubbed environment**: `os.environ` in submitted
code contains only `PATH`, `HOME`, `LANG` and two Python settings. No secret is
inherited. `tests/test_execution_backend.py::test_child_environment_excludes_secrets`
pins this.

### What is not

`/proc` remains readable. Closing it requires a PID namespace, which Render's
free tier will not grant. **This cannot be fixed on that host** — only by moving
to the Docker backend on infrastructure you control.

### Why the demo ships anyway

The blast radius is one throwaway Neon database containing nothing but seed
data. That is an accepted, documented risk for a portfolio demo — not an
oversight.

**If you deploy this yourself:** use a dedicated database whose credentials
grant access to nothing else, never reuse that password, and treat the data as
public.

---

## Application security

### Passwords

bcrypt at cost factor 12 (~250 ms per hash), called **directly** rather than
through passlib. passlib 1.7.4 reads `bcrypt.__about__.__version__`, which
modern bcrypt removed — that pairing warns today and breaks outright on bcrypt
5. Calling bcrypt straight through is fewer moving parts and stable.

Input over 72 bytes is **rejected**, not truncated. bcrypt silently ignores
everything beyond 72 bytes, which would make two different long passwords
interchangeable.

### Tokens

HS256 JWTs with `algorithms=[...]` passed explicitly on decode — that is
precisely what prevents `alg: none` and HMAC-vs-RSA confusion attacks. The
subject is the immutable user id. A `type` claim is verified, so a token minted
for another purpose cannot be replayed as an access token.

`SECRET_KEY` is **mandatory in production**; startup fails without it.
Development generates an ephemeral per-process key, so tokens do not survive a
restart — safe by default.

### Authorisation

Every write to problems, test cases and contests sits behind
`get_current_admin`. Submission source code is readable only by its author or an
admin. Unpublished problems return **404**, not 403, so their existence is not
leaked.

### User enumeration

Login verifies an unknown email against a dummy bcrypt hash, so wrong-email and
wrong-password take the same time and return an identical message.

### Race conditions

Uniqueness is enforced by **database constraints** — `uq_contest_problem`,
`uq_contest_registration`, unique email/username/title/slug — with
`IntegrityError` translated to `409`. Application-level pre-checks are only a
friendlier fast path; two concurrent requests cannot both slip through.

### Error handling

Database errors are logged in full and returned as a generic message, because
driver errors routinely echo table and column names. Validation errors are
flattened to field/message pairs with no internal detail.

---

## Data protection

### Hidden test cases

The single most security-relevant behaviour in the project.

- `GET /testcases/problem/{id}` returns samples in full and hidden cases with
  `input_data: null`, `expected_output: null`
- Hidden data is **never serialised** — not blanked client-side
- Judge results for hidden cases carry only an index and metrics
- `GET /testcases/problem/{id}/admin` is the only way to read them, and requires
  an administrator

Four tests in `tests/test_test_cases.py` and two in `tests/test_judging.py` pin
this, including an assertion that a hidden expected value appears **nowhere** in
a submission response.

> The original implementation served every hidden input and expected output from
> an unauthenticated endpoint — the answer key for every problem was public.

### Source code

Private to its author. `GET /submissions/{id}` returns `403` to anyone else;
list endpoints omit source entirely.

### Secrets in the repository

- `.env` is git-ignored
- `render.yaml` marks `DATABASE_URL` and `ADMIN_EMAILS` as `sync: false`, so
  credentials are entered in the dashboard, never committed
- `SECRET_KEY` is generated by the platform
- `frontend/.env.production` **is** committed, deliberately: Vite inlines
  `VITE_*` into client JavaScript, so those values are public by definition and
  cannot hold a secret. A public API URL is configuration

---

## Deployment hardening

If you take this beyond a demo:

1. **Use the Docker backend.** `EXECUTION_BACKEND=docker` on a host where you
   control the daemon.
2. **Judge on a separate worker host.** A sandbox escape then lands somewhere
   holding no database credentials. This is the single highest-value change.
3. **Keep Docker socket access off the public API container.** The public `api`
   container has no access to `/var/run/docker.sock`. Only the background Celery `worker`
   retains Docker socket access to create execution sandboxes.
4. **Isolated execution architecture.** `POST /submissions` is asynchronously judged via Celery, and `POST /submissions/run` delegates scratch execution to the Celery worker while preserving its synchronous HTTP response contract.
5. **No socket in sandboxes.** Individual code execution containers never receive access to the host Docker socket.
6. **Narrow CORS.** `CORS_ORIGINS=*` is the default for demo convenience. Set it
   to your frontend's origin.
7. **Rate limiting enabled.** Rate limiting is configured via `slowapi` (`RATE_LIMIT_SUBMIT`, `RATE_LIMIT_RUN`, `RATE_LIMIT_AUTH`).
8. **Restrict the database role.** The application needs DML, not `SUPERUSER`.
9. **Close registration** or add email verification if the judge is not meant to
   be public.
10. **Rotate `SECRET_KEY`** on any suspected compromise; it invalidates every
    issued token.

---

## Reporting an issue

Please open a GitHub issue for anything non-sensitive. For a vulnerability that
would affect a live deployment, contact
[@rithvikkaki](https://github.com/rithvikkaki) directly rather than filing
publicly.
