# =========================================================================
#  Online Coding Judge - production image
#
#  The image ships the Python, C++ and Java toolchains so the local sandbox
#  can compile and execute all three languages even on hosts that do not
#  expose a Docker socket (free PaaS tiers, most notably).  Where a socket
#  *is* available the Docker backend takes over automatically and these
#  toolchains simply go unused.
#
#  Deliberately a single stage.  Every dependency in requirements.txt ships a
#  prebuilt manylinux wheel, so there is nothing to compile at install time
#  and a builder stage would only add failure modes (a `--no-index` install
#  breaks if the wheel set is incomplete for any reason).
# =========================================================================

# The Debian release is pinned to stable Debian 12 (bookworm).
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000

# ca-certificates is installed first and on its own: the Java packages run a
# post-install hook that needs it, and installing them together is a known
# source of dpkg failures on slim images.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Runtime dependencies:
#   libpq5                  - psycopg2 needs it to talk to Postgres
#   g++                     - compiles C++ submissions
#   openjdk-17-jdk-headless - compiles and runs Java submissions. 17 is the
#     LTS JDK Debian bookworm ships; `-headless` skips GUI libraries.
#
# The version checks at the end are load-bearing: without them a missing
# toolchain would surface as every C++/Java submission failing in production
# instead of as a failed build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        g++ \
        openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/* \
    && javac -version && g++ --version | head -1

WORKDIR /app

# Dependencies before source, so a code change does not invalidate this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user. This is defence in depth for the *API*; the
# sandbox applies its own, much stricter, per-submission isolation.
RUN useradd --create-home --uid 10001 judge \
    && mkdir -p /tmp/judge \
    && chown -R judge:judge /app /tmp/judge
USER judge

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/api/v1/ping" || exit 1

# Render and similar platforms inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --proxy-headers"]
