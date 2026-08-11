# Streamr — Requirements Checklist (Phase 2)

Traceability matrix built from the GitHub issue set (#23–44) and verified
against the code. Updated after the completion pass — every requirement is now
implemented on both sides.

Legend: ✅ done · — n/a

## Foundation & core API

| # | Requirement | Backend | Frontend | Notes |
|---|---|---|---|---|
| 23 | Core Django models | ✅ | — | User, ArtistProfile, Album, Track, Playlist, Subscription(+Plan), Transaction, ArtistPayout, PayoutPolicy, Follow, Notification, UserPreferences, PlayEvent |
| 24 | JWT authentication | ✅ | ✅ | login/refresh/logout/me; FE auto-refresh + mock fallback |
| 25 | REST CRUD endpoints | ✅ | ✅ | album/track/playlist viewsets; FE catalog + playlists wired |
| 26 | Role-based access control | ✅ | ✅ | Is{Listener,Artist,SupportOrAdmin,Admin}; FE route guards |
| 27 | Frontend integration | — | ✅ | All user journeys wired to the API with mock fallback |

## Subscriptions, access control & payments

| # | Requirement | Backend | Frontend | Notes |
|---|---|---|---|---|
| 28 | Subscription tiers & limits | ✅ | ✅ | per-plan limits + feature flags; FE tier gating |
| 29 | Dynamic subscription pricing | ✅ | ✅ | admin `PATCH /subscriptions/plans/<id>/`; PriceControl wired |
| 30 | Subscription-based access control | ✅ | ✅ | tier permissions; FE early-access / download / avatar gating |
| 31 | Payment gateway integration | ✅ | ✅ | Zarinpal v4; FE /upgrade → StartPay → return + refreshMe |

## Media, preferences & reporting

| # | Requirement | Backend | Frontend | Notes |
|---|---|---|---|---|
| 33 | Audio file upload | ✅ | ✅ | PUT tracks/{id}/audio/; upload form creates track + PUTs audio |
| 34 | Image upload | ✅ | ✅ | avatar/album-cover/track-cover; upload form PUTs cover |
| 35 | Sync user preferences | ✅ | ✅ | auth/me/preferences/; FE hydrate + sync |
| 36 | Aggregated reporting endpoints | ✅ | ✅ | listening/artist/admin/payouts; dashboards wired |

## Docs, testing & quality

| # | Requirement | Backend | Frontend | Notes |
|---|---|---|---|---|
| 37 | Swagger / OpenAPI | ✅ | — | /api/schema, /api/docs, /api/redoc |
| 38 | Backend tests (min 15) | ✅ | — | **143** tests |
| 39 | Django/DRF best practices | ✅ | — | split settings, viewsets/serializers/permissions |
| 40 | Design patterns | ✅ | — | payment service layer, permission classes, custom managers |
| 41 | Clean code pass | ✅ | — | — |
| 42 | Maintainability review | ✅ | — | this checklist + INTEGRATION.md |

## Bonus & deliverables

| # | Requirement | Backend | Frontend | Notes |
|---|---|---|---|---|
| 32 | [Bonus] Group listening | ✅ | ✅ | ws/session/<id>/ consumer; FE WebSocket relays play/pause/seek |
| 43 | [Bonus] Dockerize both | ✅ | ✅ | Dockerfiles + compose; compose YAML-validated (not run e2e) |
| 44 | Final PDF report | ✅ | — | Streamr_Phase2_Final_Report.pdf |
| — | Notifications | ✅ | ✅ | GET/POST auth/me/notifications/; panel wired |
| — | Password reset | ✅ | ✅ | auth/password-reset[/confirm]; forgot + reset pages wired |

## Test totals

- Backend (pytest): **143 passing**
- Frontend (vitest): **256 passing**

## Branches added in this pass

Backend: `feat/dynamic-pricing`, `feat/notifications`.
Frontend (stacked): `feat/complete-reporting`, `feat/dynamic-pricing-ui`,
`feat/password-reset`, `feat/artist-uploads`, `feat/notifications-ui`,
`feat/group-session-realtime`.

## Remaining caveat

Docker Compose is YAML-validated but was not run end-to-end in the build
sandbox (no Docker daemon there). Everything else is implemented and tested on
both sides.
