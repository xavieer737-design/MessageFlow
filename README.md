# MessageFlow

**Prepare consent-based bulk SMS campaigns — desktop-first web app.**
Import contacts, organize groups, personalize templates, validate campaigns,
maintain opt-out lists — and later send through a real Android phone's SIM.

> **Phase 1 status:** Everything up to *sending* is implemented. Campaigns can be
> prepared, validated and marked READY, but **no SMS is ever sent and no delivery
> status is ever fabricated**. Android pairing arrives in Phase 2.

---

## Features

- 🔐 Secure authentication (bcrypt password hashing, JWT in httpOnly cookies,
  per-user data isolation, rate limiting)
- 👥 Contact management — add / edit / delete / search / filter / sort /
  paginate / multi-select / bulk delete / export (CSV & XLSX)
- 📥 Real CSV & XLSX import — column detection, smart `name → first_name`
  mapping, row-by-row validation, duplicate & opt-out detection, full
  error preview before importing
- 📞 Phone validation & normalization to E.164 (`9876543210` → `+919876543210`)
  via Google libphonenumber
- 🗂 Contact groups (Customers, Leads, VIP, …) with membership management
- ✍️ Message templates with `{{variables}}` + variable picker + preview
- 📏 Real SMS character/segment counter (GSM-7 160/153, UCS-2 70/67)
- 📣 Campaign wizard: details → recipients → message → personalized preview →
  validation → save (DRAFT / READY)
- 🚫 Opt-out list with import/export; campaigns automatically exclude opted-out
  numbers (`"X recipients will be skipped because they are opted out."`)
- 📊 Dashboard with real statistics, recent campaigns, audit activity, device status
- 📱 Devices page prepared for the future Android companion app (honest
  empty states — nothing simulated)
- 📜 Message logs with status filters (only real application records)
- 🌗 Light/dark theme, responsive layout (1920 → tablet), premium SaaS UI

## Architecture

```
┌────────────────────────┐        ┌─────────────────────────┐
│  frontend/ (React SPA) │  /api  │  backend/ (FastAPI)     │
│  Vite · React · TS     │ ─────▶ │  SQLAlchemy · Pydantic  │
│  Tailwind · TanStack   │ proxy  │  Alembic · PostgreSQL   │
│  Query · React Router  │        │  pandas · openpyxl      │
└────────────────────────┘        └───────────┬─────────────┘
                                              │
                                    ┌─────────▼─────────┐
                                    │  PostgreSQL        │
                                    │  (12 tables)       │
                                    └───────────────────┘
```

Layering inside the backend keeps business logic out of the API routes:

```
app/api/routes/      → HTTP layer (validation, status codes)
app/services/        → business logic (phone, SMS, templates, campaigns, import)
app/repositories/    → user-scoped data access
app/models/          → SQLAlchemy models
app/schemas/         → Pydantic schemas
app/core/            → config, security, rate limiting
app/db/              → engine/session
```

## Repository layout

```
├── frontend/          React + TypeScript + Vite + Tailwind SPA
│   └── src/
│       ├── components/ui/   design-system kit (Button, Card, Modal, Table, …)
│       ├── components/layout/  Sidebar, Topbar
│       ├── pages/         all screens (Contacts, Campaigns, Wizard, …)
│       ├── services/      typed API client functions
│       ├── lib/           api client, SMS counter, template vars, formatting
│       └── hooks/         useAuth, useTheme, …
├── backend/
│   ├── app/              FastAPI application (api, services, repositories, …)
│   ├── alembic/          migrations (initial schema included)
│   ├── tests/            93 pytest tests
│   └── scripts/seed.py   optional demo data
├── docs/                 architecture, API reference, testing, Phase 2 plan
└── .env.example
```

## Requirements

| Tool    | Version            | Notes                                   |
| ------- | ------------------ | --------------------------------------- |
| Python  | ≥ 3.11             |                                         |
| Node.js | ≥ 20               |                                         |
| PostgreSQL | ≥ 14           | Any recent version works                |

## Installation

```bash
# 1. Clone & enter the repository
git clone <repo-url> msgapk && cd msgapk

# 2. Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 3. Frontend
cd frontend
npm install
cd ..
```

## Environment setup

```bash
cp .env.example .env
# edit .env — at minimum DATABASE_URL and JWT_SECRET
```

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | `postgresql+psycopg2://user:pass@host:port/dbname` |
| `JWT_SECRET` | long random string — generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `CORS_ORIGINS` | comma-separated browser origins |
| `DEFAULT_REGION` | region used for numbers without `+` prefix (default `IN`) |
| `MAX_UPLOAD_MB` / `UPLOAD_DIR` | import upload limits / staging dir |
| `RATE_LIMIT_AUTH` / `RATE_LIMIT_IMPORT` | slowapi limits |

Never commit real secrets — only `.env.example` lives in the repository.

## Database setup

```bash
# Create the role and database (adjust to your PostgreSQL install)
sudo -u postgres psql <<'SQL'
CREATE ROLE messageflow LOGIN PASSWORD 'messageflow';
CREATE DATABASE messageflow OWNER messageflow;
SQL
```

## Migration commands

```bash
cd backend
export DATABASE_URL="postgresql+psycopg2://messageflow:messageflow@localhost:5432/messageflow"

../.venv/bin/alembic upgrade head     # apply migrations
../.venv/bin/alembic revision --autogenerate -m "describe change"   # new migration
../.venv/bin/alembic downgrade -1     # roll back one step
../.venv/bin/alembic current          # show current revision
```

## Backend startup

```bash
cd backend
../.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs (Swagger): <http://localhost:8000/api/docs>
- Health check: <http://localhost:8000/api/health>

Optional demo data:

```bash
cd backend && ../.venv/bin/python scripts/seed.py
# logs in with demo@messageflow.dev / demo1234
```

## Frontend startup

```bash
cd frontend
npm run dev          # http://localhost:5173  (proxies /api → :8000)
npm run build        # production build
npm run test         # vitest unit tests
```

## Testing

```bash
# Backend (93 tests — runs against in-memory SQLite, no services needed)
cd backend && ../.venv/bin/python -m pytest tests/ -q

# Frontend
cd frontend && npm run test
```

Covered: registration, login, logout, refresh, password rules, protected
routes, user isolation, contact CRUD + normalization + duplicates, CSV & XLSX
import (mapping, duplicates, opt-outs, bad files), phone validation, template
variables, SMS segment counting, campaign creation/validation/transitions,
opt-out filtering, message-log records, devices, dashboard stats.

## CSV import format

A header row with columns like:

```csv
phone,name,company,email
9876543210,Rahul,ABC Ltd,rahul@example.com
9876543211,Amit,XYZ Ltd,amit@example.com
```

- Recognized column aliases: `phone`/`mobile`/`mobile number`/`cell`…,
  `first name`/`fname`, `last name`/`lname`, `email`, `company`/`organization`,
  `notes`.
- A combined `name` column is auto-mapped to **first name** when values look
  like names — you can change the mapping in the UI.
- XLSX files go through the exact same flow (openpyxl, no Excel needed).
- Invalid phones, duplicates (in-file or already in contacts) and opted-out
  numbers are shown with per-row reasons — **never silently dropped**.
- Numbers are normalized and stored in E.164.

## API overview

All endpoints under `/api` (auth-protected except register/login/health).

| Area | Endpoints |
| --- | --- |
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`, `PUT /auth/me`, `PUT /auth/me/password` |
| Contacts | `GET/POST /contacts`, `GET/PUT/DELETE /contacts/{id}`, `POST /contacts/import/upload`, `POST /contacts/import/validate`, `POST /contacts/import/confirm`, `GET /contacts/export`, `POST /contacts/bulk-delete` |
| Groups | `GET/POST /groups`, `GET/PUT/DELETE /groups/{id}`, `POST /groups/{id}/contacts`, `POST /groups/{id}/contacts/remove` |
| Templates | `GET/POST /templates`, `GET/PUT/DELETE /templates/{id}`, `POST /templates/{id}/duplicate`, `POST /templates/preview` |
| Campaigns | `GET/POST /campaigns`, `GET/PUT/DELETE /campaigns/{id}`, `POST /campaigns/{id}/validate`, `POST /campaigns/{id}/ready`, `POST /campaigns/{id}/duplicate`, `POST /campaigns/{id}/pause|resume|cancel` |
| Devices | `GET /devices`, `POST /devices/register`, `POST /devices/{id}/heartbeat`, `DELETE /devices/{id}` |
| Messages | `GET /messages?status=&campaign_id=&page=` |
| Opt-outs | `GET/POST /optouts`, `POST /optouts/bulk`, `POST /optouts/import`, `GET /optouts/export`, `DELETE /optouts/{id}` |
| Dashboard | `GET /dashboard/stats` |
| Misc | `GET /health` |

Full request/response reference: [`docs/api.md`](docs/api.md).

## Database tables

`users`, `contacts`, `contact_groups`, `contact_group_members`,
`message_templates`, `campaigns`, `campaign_recipients`, `devices`,
`message_logs`, `opt_outs`, `audit_logs`, `alembic_version`.

Phone numbers are unique per user (`uq_contact_user_phone`); opt-outs are
unique per user+phone; every table is indexed on `user_id`.

## Security notes

- Passwords hashed with bcrypt (12 rounds); no plaintext storage.
- JWTs signed with HS256 in **httpOnly cookies** (SameSite=Lax, optional
  Secure), access 15 min + refresh 7 days with rotation.
- Every repository query is scoped by `user_id` — changing an ID in a request
  can never reach another user's data (verified by tests).
- SQL injection safe via SQLAlchemy bound parameters.
- CORS restricted to configured origins; credentials allowed.
- Rate limits on auth and import endpoints; upload type/size limits.
- Secrets come only from environment variables.

## Compliance / anti-spam design

Built for legitimate, consent-based messaging:

- opt-out list (excluded automatically at validation & import),
- duplicate prevention,
- recipient phone validation,
- campaign cancellation / pause,
- rate limits,
- audit log of every meaningful action,
- no anonymous sending, no carrier/spam-filter bypass, no fake delivery
  reports — the future Android app will use official Android SMS APIs with
  the user's consent and granted permissions.

## Current limitations (Phase 1)

- No SMS sending — campaigns stop at READY.
- No device connectivity, battery/SIM info, or delivery reports (nothing fabricated).
- No scheduled sending execution (`scheduled_at` is stored only).
- No STOP/UNSUBSCRIBE reply processing yet (opt-out import/manual add ready).
- Email is a contact field, not an identity.
- Upload staging files are cleaned after confirm; orphaned uploads expire on server restart.

## Future Android integration (Phase 2)

See [`docs/phase-2-android.md`](docs/phase-2-android.md) for the full plan:
companion Android app using the official SMS Manager API, WebSocket
pairing with QR code, heartbeat, per-campaign send queues, delivery status
callbacks, and per-number rate limiting. The API surface (`devices`,
`heartbeat`, `MessageLog`, campaign states) is already prepared for it.
