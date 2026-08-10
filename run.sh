#!/usr/bin/env bash
#
# run.sh — bring the whole Streamr stack up locally and run both test suites.
#
#   1. Backend  : venv + deps -> .env -> Postgres db -> migrate -> seed
#                 -> pytest -> start API (http://localhost:8000)
#   2. Frontend : npm deps -> .env (pointed at the API) -> vitest
#                 -> start Next.js (http://localhost:3000)
#
# Then it leaves both servers running so you can open the app in a browser.
# Ctrl-C stops both.
#
# Requirements: Python 3.11+, Node 18+, and a running PostgreSQL you can
# connect to (the catalog uses a Postgres ArrayField, so SQLite won't do).
#
# Usage:
#   ./run.sh                 # up + tests + serve
#   SKIP_TESTS=1 ./run.sh    # skip both test suites
#   NO_SERVE=1 ./run.sh      # set up + test only, don't start servers
#
# Override paths / ports / db with env vars (see the CONFIG block).

set -euo pipefail

# ---------------------------------------------------------------- CONFIG ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Locate the two repos whether run.sh sits beside them or inside either one.
find_dir() {
  for c in "$@"; do [ -e "$c" ] && { (cd "$(dirname "$c")" && pwd); return; }; done
}
BE_DIR="${BE_DIR:-$(find_dir "$SCRIPT_DIR/Spotify-BE/manage.py" "$SCRIPT_DIR/manage.py" "$SCRIPT_DIR/../Spotify-BE/manage.py")}"
FE_DIR="${FE_DIR:-$(find_dir "$SCRIPT_DIR/Spotify-FE/package.json" "$SCRIPT_DIR/../Spotify-FE/package.json")}"

BE_PORT="${BE_PORT:-8000}"
FE_PORT="${FE_PORT:-3000}"
API_URL="http://localhost:${BE_PORT}/api"

# Database: honour an existing DATABASE_URL, else default to local Postgres.
DB_NAME="${DB_NAME:-spotify_be}"
DATABASE_URL="${DATABASE_URL:-postgres://localhost:5432/${DB_NAME}}"

# Zarinpal sandbox (any UUID works as a sandbox merchant_id).
ZARINPAL_MERCHANT_ID="${ZARINPAL_MERCHANT_ID:-c8d2f8b6-07c1-496c-9f4c-f8e8afae1955}"

SKIP_TESTS="${SKIP_TESTS:-0}"
NO_SERVE="${NO_SERVE:-0}"

# ---------------------------------------------------------------- HELPERS ---
c() { printf '\033[1;36m%s\033[0m\n' "$*"; }        # cyan heading
ok() { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
die() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[ -n "${BE_DIR:-}" ] || die "Could not find Spotify-BE (set BE_DIR=/path/to/Spotify-BE)"
[ -n "${FE_DIR:-}" ] || die "Could not find Spotify-FE (set FE_DIR=/path/to/Spotify-FE)"

PIDS=()
cleanup() { c "Shutting down…"; for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------- POSTGRES --
c "Checking PostgreSQL…"
command -v psql >/dev/null 2>&1 || die "psql not found. Install PostgreSQL and ensure it's running."
# Derive a server URL (strip the db name) to create the db if it's missing.
SERVER_URL="${DATABASE_URL%/*}/postgres"
if ! psql "$DATABASE_URL" -c '\q' >/dev/null 2>&1; then
  c "Database '${DB_NAME}' not reachable — attempting to create it…"
  psql "$SERVER_URL" -c "CREATE DATABASE ${DB_NAME};" >/dev/null 2>&1 \
    && ok "Created database ${DB_NAME}" \
    || die "Cannot connect to Postgres at ${SERVER_URL}. Start Postgres or set DATABASE_URL."
fi
ok "PostgreSQL ready (${DATABASE_URL})"

# ---------------------------------------------------------------- BACKEND ---
c "=== BACKEND (${BE_DIR}) ==="
cd "$BE_DIR"

if [ ! -d .venv ]; then python3 -m venv .venv; fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements/dev.txt
ok "Backend dependencies installed"

if [ ! -f .env ]; then
  cat > .env <<EOF
DJANGO_SETTINGS_MODULE=config.settings.dev
DJANGO_SECRET_KEY=dev-secret-change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
DATABASE_URL=${DATABASE_URL}
CORS_ALLOWED_ORIGINS=http://localhost:${FE_PORT},http://127.0.0.1:${FE_PORT}
FRONTEND_URL=http://localhost:${FE_PORT}
ZARINPAL_MERCHANT_ID=${ZARINPAL_MERCHANT_ID}
ZARINPAL_BASE_URL=https://sandbox.zarinpal.com/pg
EOF
  ok "Wrote Spotify-BE/.env"
fi

python manage.py migrate
python manage.py seed_demo || true
ok "Migrated + seeded demo data"

if [ "$SKIP_TESTS" != "1" ]; then
  c "Running backend tests…"
  python -m pytest -q
  ok "Backend tests passed"
fi

# ---------------------------------------------------------------- FRONTEND --
c "=== FRONTEND (${FE_DIR}) ==="
cd "$FE_DIR"

if [ -f package-lock.json ]; then npm ci; else npm install; fi
ok "Frontend dependencies installed"

# Point the frontend at the running backend (this flips it from mock mode to
# real API calls). Written to .env.local so it wins over any committed .env.
echo "NEXT_PUBLIC_API_URL=${API_URL}" > .env.local
ok "Wrote Spotify-FE/.env.local (NEXT_PUBLIC_API_URL=${API_URL})"

if [ "$SKIP_TESTS" != "1" ]; then
  c "Running frontend tests…"
  npm test
  ok "Frontend tests passed"
fi

if [ "$NO_SERVE" = "1" ]; then
  c "NO_SERVE=1 — setup and tests complete, not starting servers."
  trap - EXIT INT TERM
  exit 0
fi

# ---------------------------------------------------------------- SERVE -----
c "=== STARTING SERVERS ==="
cd "$BE_DIR"; source .venv/bin/activate
python manage.py runserver "0.0.0.0:${BE_PORT}" >/tmp/streamr-be.log 2>&1 &
PIDS+=($!)
ok "Backend  → http://localhost:${BE_PORT}  (API ${API_URL}, docs ${API_URL%/api}/api/docs/)"

cd "$FE_DIR"
npm run dev -- -p "${FE_PORT}" >/tmp/streamr-fe.log 2>&1 &
PIDS+=($!)
ok "Frontend → http://localhost:${FE_PORT}"

cat <<EOF

$(c "Streamr is up. Open  http://localhost:${FE_PORT}  in your browser.")

  Demo accounts (password: password123)
    listener@demo.com   basic listener
    silver@demo.com     silver listener
    gold@demo.com       gold listener (early access)
    nova@demo.com       approved artist
    support@demo.com    support staff
    admin@demo.com      admin

  Payments: log in as a listener → Settings → Upgrade → pick a plan →
  you'll be sent to the Zarinpal sandbox, then redirected back.

  Logs: /tmp/streamr-be.log  and  /tmp/streamr-fe.log
  Press Ctrl-C to stop both servers.
EOF

wait
