# Streamr — Integration Guide (Phase 2)

This explains how to run the full stack, what was integrated, how the backend
tickets map to branches, and what's left to finish.

## TL;DR — run everything

Put both repos side by side and run the orchestrator (needs Python 3.11+,
Node 18+, and a reachable PostgreSQL):

```
your-folder/
  Spotify-BE/
  Spotify-FE/
./run.sh          # from either repo, or from the parent folder
```

`run.sh` will: install deps, write `.env` files, create/migrate/seed the DB,
run **both** test suites, then start the backend (`:8000`) and frontend
(`:3000`) and print demo logins. Open <http://localhost:3000>.

Flags: `SKIP_TESTS=1` (skip suites), `NO_SERVE=1` (set up + test only),
`BE_DIR=/path FE_DIR=/path` (override locations).

### Or with Docker (ticket #43)

```
cd Spotify-BE          # with Spotify-FE as a sibling
docker compose up --build
```

Postgres + backend + frontend come up together. Open <http://localhost:3000>.

## Demo accounts

Password for all: `password123`

| Email | Role / tier |
| --- | --- |
| listener@demo.com | basic listener |
| silver@demo.com | silver listener |
| gold@demo.com | gold listener (early access) |
| nova@demo.com | approved artist |
| support@demo.com | support staff |
| admin@demo.com | admin |

## How the integration works (mock ↔ real API)

The frontend keeps its localStorage mock layer and gains a thin **resource
layer** in `utils/resources/`. Every loader uses the real API when
`NEXT_PUBLIC_API_URL` is set and **falls back to the mock** when it isn't — so
the app runs with or without a backend, and all existing tests stay green.

- `http.ts` — DRF pagination walker + media-URL resolver
- `catalog.ts` — albums / tracks / artists → the mock `Song`/`Album` shapes
- `playlists.ts` — list / create / delete / detail / add-remove track
- `subscriptions.ts` — plans + start payment (+ mock upgrade)
- `reports.ts` — artist summary / track stats / payouts / admin overview
- `uploads.ts` — multipart PUT for avatar / cover / audio

Auth (login), preferences, registration, catalog browse, playlists, and the
subscription/payment flow are wired end-to-end. To point the app at the API
manually: `echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api" > Spotify-FE/.env.local`.

## Payments (Zarinpal, ticket for subscriptions)

The backend was migrated from the dead WebGate v1 API to **Zarinpal v4**
(`/pg/v4/payment/request.json` + `verify.json`). Flow:

1. Settings → **Upgrade** → pick a plan.
2. FE `POST /api/subscriptions/pay/start/ {planId}` → gets a StartPay URL →
   browser goes to the Zarinpal sandbox.
3. After paying, Zarinpal calls `/api/subscriptions/pay/callback/`, which
   verifies, activates the subscription, and **redirects the browser back** to
   `/upgrade?payment=success`. The FE then re-fetches `/auth/me` so the new
   tier shows immediately.

`merchant_id` and the gateway base URL are env-configurable
(`ZARINPAL_MERCHANT_ID`, `ZARINPAL_BASE_URL`); the sandbox default merchant is
already set. `user.tier` is a computed property off the active subscription,
so no manual tier bookkeeping is needed.

## Backend tickets → branches

The backend was already complete on feature branches (origin). This session
added two more and left the rest as documentation:

| Ticket | Branch |
| --- | --- |
| JWT auth | `feat/jwt-auth` (origin) |
| Catalog CRUD | `feat/catalog-crud` (origin) |
| Playlists CRUD | `feat/playlists-crud` (origin) |
| Media uploads | `feat/media-uploads` (origin) |
| Preferences sync | `feat/preferences-sync` (origin) |
| Reporting endpoints | `feat/reporting-endpoints` (origin) |
| Swagger / OpenAPI (#37) | `feat/api-docs` (origin) |
| Backend tests ≥15 (#38) | covered across the above (137 tests total) |
| Clean code / maintainability (#41/#42) | covered across the above |
| **Zarinpal v4 payments** | `fix/zarinpal-v4-payments` (new) |
| **Dockerize (#43)** | `feat/dockerize` (new) |

## Frontend integration branches (stacked on real `main`)

Built as a reviewable stack, each on top of the previous:

1. `feat/api-resource-layer` — the resource modules + `api.ts` exports + tests
2. `feat/integrate-catalog` — browse / home / album / early-access wiring
3. `feat/integrate-playlists` — playlist manager, add-to-playlist, detail
4. `feat/integrate-registration` — listener/artist register via API, `refreshMe()`
5. `feat/integrate-subscriptions` — `/upgrade` page, settings button, i18n
6. `feat/dockerize` — Dockerfile, run.sh, .env.example (tip = full tested state)

The tip branch equals the fully tested working tree (FE: 248 tests, BE: 137).

## Pushing this to your real repos

These repos carry your real git history; the branches above sit on top of it.
Rebase/cherry-pick the branch tips onto your canonical `main` and push — **do
not force-push**. The frontend stack is linear, so
`git rebase --onto origin/main main feat/dockerize` (or merging each in order)
brings it across cleanly.

## Completion status

The follow-up completion pass wired every remaining item on both sides:

- Reporting dashboards (artist stats, revenue chart, recent playlists) -> `reports.*`
- Artist profile page -> `catalog.loadArtist()` (`/artists/{id}/`)
- Artist upload form -> `catalog.createTrack()` + `uploads.*` (multipart)
- Dynamic pricing (#29) -> admin `PATCH /subscriptions/plans/<id>/` + PriceControl
- Password reset -> `auth/password-reset[/confirm]` + `/forgot-password` and `/reset-password/[uid]/[token]`
- Notifications -> `GET/POST /auth/me/notifications/` + NotificationPanel
- Group listening (bonus #32) -> WebSocket client on `ws/session/<id>/`

Test totals: backend **143**, frontend **256**.

New branches this pass — backend: `feat/dynamic-pricing`, `feat/notifications`;
frontend (stacked): `feat/complete-reporting`, `feat/dynamic-pricing-ui`,
`feat/password-reset`, `feat/artist-uploads`, `feat/notifications-ui`,
`feat/group-session-realtime`.

Only remaining caveat: Docker Compose is YAML-validated but was not run
end-to-end in the build sandbox (no Docker daemon there).
