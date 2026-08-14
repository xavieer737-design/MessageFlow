# MessageFlow — Testing

## Backend (pytest)

```bash
cd backend
../.venv/bin/python -m pytest tests/ -q
```

132 tests across:

| File | Covers |
| --- | --- |
| `test_auth.py` | registration, duplicate email, password rules, login, refresh, logout, me, password change, profile update |
| `test_contacts.py` | CRUD, E.164 normalization, duplicates (409), invalid phones (422), search, pagination, bulk delete, CSV export, **user isolation** |
| `test_import.py` | CSV upload (column detection, `name → first_name` suggestion), full confirm counts, in-file + existing duplicates, invalid rows, opt-out exclusion, XLSX import, bad file type, staged-upload isolation |
| `test_phone.py` | national/international/leading-00 normalization, consistent storage, explicit region, empty/malformed/impossible/unknown numbers |
| `test_templates.py` | variable extraction, unsupported variable rejection, personalization, missing fields, template preview endpoint, SMS segment counting (GSM-7 160/153, UCS-2 70/67, extension chars) |
| `test_campaigns.py` | wizard creation (all/group/contacts), personalized validation report, opt-out filtering, invalid-phone defense, unsupported variables, SMS length, mark-ready gating, status transitions, edit-only-draft, duplication, real message-log records, isolation |
| `test_optouts.py` | add/normalize/duplicate/search/delete, bulk add, CSV import, export, isolation |
| `test_groups_dashboard.py` | group CRUD, name conflicts, membership add/remove, group-filtered contact list, dashboard stats from real data, activity feed |
| `test_devices.py` | registration (never claims connected), identifier conflicts, heartbeat, mismatch 403, delete, isolation |
| `test_phase2_pairing.py` | token generation, QR payload contents (no secrets), hash-only storage, expiry (410), single-use replay (409), detail mismatch, status polling, session isolation, key update on re-pair |
| `test_phase2_ws_auth.py` | full challenge/response auth, wrong token/signature/device_id rejection, impersonation block (leaked token + wrong key), CONNECTED only after auth, OFFLINE on close, WS heartbeat telemetry, REST heartbeat (no connectivity claim), STOP keyword opt-out, non-STOP ignored |
| `test_phase2_send_engine.py` | start-send queueing (message ids, idempotency keys), READY-only + paired-device-only gating, opt-out recheck at send time, batching + pacing, offline no-dispatch, next-batch flow, SEND_SUCCESS/SEND_FAILED handling + MessageLog entries, duplicate-result idempotency, no redispatch after success, lost-result redispatch with same message_id, completion, pause/resume/cancel, offline sweep + auto-pause, test message + result polling, multi-user isolation |

Tests run against an in-memory SQLite database (same SQLAlchemy models) —
no services required. To run against PostgreSQL instead:

```bash
DATABASE_URL="postgresql+psycopg2://…" ../.venv/bin/python -m pytest tests/ -q
```

(create the schema first with `alembic upgrade head`).

## Frontend (vitest)

```bash
cd frontend
npm run test
```

- `lib/smsCounter.test.ts` — segment counting matches the backend exactly.
- `lib/templateVars.test.ts` — variables, personalization, missing fields.
- `components/ui/Button.test.tsx` — interaction, loading state, variants.

## Manual acceptance checklist

1. `alembic upgrade head` on a fresh database succeeds.
2. Register → dashboard loads with zero states.
3. Create a contact with a national number → stored as `+91…`.
4. Import `backend/tests/samples/contacts.csv`-style file → mapping step →
   preview shows per-row statuses → confirm imports only valid rows.
5. Create a group, assign contacts, build a campaign targeting it.
6. Template with `{{first_name}}`/`{{company}}` → wizard preview shows
   “Hi Rahul, your order from ABC Ltd is ready.”
7. Add a recipient's number to opt-outs → validation reports it will be
   skipped; the message log gains an OPTED_OUT entry; dashboard counts update.
8. `messages_sent` stays 0, no device ever shows CONNECTED, no fake history.
9. Second user can't see any of the first user's data.
10. Dark mode, sidebar collapse, tablet width, empty/loading/error states.
