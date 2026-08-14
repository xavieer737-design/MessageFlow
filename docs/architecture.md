# MessageFlow — Architecture

## High-level

MessageFlow is a desktop-first web application with a React SPA frontend,
a Python FastAPI backend backed by PostgreSQL, and (Phase 2) an Android
companion app that performs actual SMS sending through the phone's SIM.

```
Browser (React SPA, :5173)
   │  same-origin /api calls (Vite dev proxy → :8000)
   ▼
FastAPI (uvicorn, :8000) ── CORS for configured origins only
   │
   ├── app/api/routes        HTTP + WebSocket layer (incl. /devices/ws)
   ├── app/services          business logic (phone, SMS, templates,
   │                         campaigns, import, pairing, send engine)
   ├── app/services/connection_manager.py   in-memory WS registry
   ├── app/core/background.py               dispatch + offline sweep loops
   ├── app/repositories      user-scoped data access (isolation by construction)
   ├── app/models            SQLAlchemy 2.0 models
   └── app/db                engine + session (PostgreSQL in prod, SQLite in tests)

Android app (android/, Kotlin + Compose)
   │  WSS /api/devices/ws (device JWT + RSA challenge-response)
   ▼
SmsManager → SIM → recipient
```

The backend is the coordination layer: it owns the send queue (batches,
pacing, opt-out re-checks, idempotency) and only records results the device
reports. The Android app is a thin executor with an encrypted idempotency
store to guarantee no double-sending across reconnects.

## Frontend

- **Vite + React 18 + TypeScript** (strict mode).
- **Tailwind CSS** design system in `src/components/ui` — Button, Card, Modal,
  Table, Badge, EmptyState, Toast, Dropdown, Tabs, Pagination, etc. No
  third-party UI kit; consistent tokens (zinc neutrals + brand indigo).
- **TanStack Query** for all server state (`['contacts']`, `['campaigns']`,
  `['dashboard']`, …), invalidated after mutations.
- **React Router** with protected/guest route wrappers.
- **lib/smsCounter.ts** mirrors the backend SMS segment logic exactly, so the
  character counter shown to users matches what the backend computes.
- Dark/light theme via the `dark` class on `<html>` (localStorage + system pref).

## Backend

- **FastAPI** + **Pydantic v2** schemas; OpenAPI docs at `/api/docs`.
- **SQLAlchemy 2.0** (declarative, typed `Mapped` columns); **Alembic** migrations.
- **PostgreSQL** via `psycopg2`. Tests run on in-memory SQLite through the
  same models (JSON columns and plain-string statuses keep the schema portable).
- **Auth**: bcrypt hashing, JWT access (15 min) + refresh (7 days) in httpOnly
  cookies; refresh rotation; SameSite=Lax; optional Secure flag.
- **Rate limiting**: slowapi on `/auth/register`, `/auth/login`,
  `/contacts/import/upload` (configurable limits).
- **Import pipeline**: upload → pandas parse → column detection/alias mapping
  → per-row validation (phonenumbers lib, in-file + in-DB duplicates,
  opt-out check) → staged JSON on disk → confirm inserts only valid rows and
  returns full counts. XLSX handled by openpyxl through pandas.

## Key flows

### Device lifecycle (Phase 2)

```
pairing/start (QR, 5 min one-time token)
   → pairing/complete (device public key) → DISCONNECTED (paired)
   → WS auth (challenge + signature)      → CONNECTED
   → heartbeat timeout / WS close         → OFFLINE
   → user action                          → DISCONNECTED
```

### Campaign send lifecycle (Phase 2)

```
READY --send(device)--> RUNNING (SendJob ACTIVE)
  dispatch loop: next batch (≤ SEND_BATCH_SIZE) with pacing
  device → message_result(SEND_SUCCESS|SEND_FAILED)
  attempt/recipient/MessageLog updated; next batch; COMPLETED when done
PAUSED  = no new commands (in-flight completes, results still recorded)
CANCELLED = terminal, no new commands
```

Idempotency: every recipient has a stable `idempotency_key` and per-attempt
`message_id`. The device stores (message_id → result) encrypted; a repeated
command replays the stored result instead of re-sending. If a result is lost
in transit, the server re-issues the SAME message_id on reconnect.

### Campaign lifecycle (Phase 1)

```
DRAFT ──validate──▶ (report; recipients + message logs regenerated)
  │                     │ valid
  │                     ▼
  │                   READY ──pause──▶ PAUSED ──resume──▶ READY
  │                       │              │
  └──cancel──▶ CANCELLED ◀──cancel───────┘
  (COMPLETED / RUNNING / SCHEDULED exist for Phase 2)
```

- Validation personalizes every recipient message, flags invalid phones,
  duplicates, opted-out numbers, empty messages, unsupported variables and
  SMS length, and writes real `MessageLog` rows for SKIPPED/OPTED_OUT.
- `READY` is only reachable through a passing validation.

### User isolation

Every repository method takes `user_id`; all queries filter by it. Pydantic
schemas never expose other users' identifiers. Tests assert cross-user 404s
for contacts, groups, campaigns, opt-outs, devices, and staged uploads.

## Database

12 tables — see `docs/database.md`. Statuses are plain strings (with indexes);
JSON used for `custom_fields` and campaign contact-id lists.
