# MessageFlow — API Reference

Base path: `/api`. Interactive docs: `/api/docs` (Swagger UI).

## Authentication

JWT access + refresh tokens are set as httpOnly cookies
(`mf_access` 15 min, `mf_refresh` 7 days, SameSite=Lax). All endpoints
except `register`, `login`, `refresh` and `health` require a valid session
(cookie or `Authorization: Bearer <access>`).

| Method | Path | Body / Params | Response |
| --- | --- | --- | --- |
| POST | `/auth/register` | `{name, email, password}` | `201 User` (sets cookies) |
| POST | `/auth/login` | `{email, password}` | `200 User` (sets cookies) |
| POST | `/auth/refresh` | — | `200 User` (rotates cookies) |
| POST | `/auth/logout` | — | `200 {message}` (clears cookies) |
| GET | `/auth/me` | — | `200 User` |
| PUT | `/auth/me` | `{name}` | `200 User` |
| PUT | `/auth/me/password` | `{current_password, new_password}` | `200 {message}` |

`User`: `{id, name, email, created_at}`.

## Contacts

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/contacts?search=&group_id=&sort_by=&sort_dir=&page=&page_size=` | paginated list; `sort_by`: created_at\|name\|phone\|email\|company |
| POST | `/contacts` | `201`; body `{phone, first_name?, last_name?, email?, company?, notes?, custom_fields?, group_ids?}` — phone normalized to E.164; 409 on duplicate; 422 on invalid phone |
| GET | `/contacts/{id}` | `200 Contact` / 404 |
| PUT | `/contacts/{id}` | update (same rules as create) |
| DELETE | `/contacts/{id}` | `204` |
| POST | `/contacts/bulk-delete` | body: `[ids]` → `204` |
| GET | `/contacts/export?format=csv\|xlsx` | file download |
| POST | `/contacts/import/upload` | multipart `file` → `{file_id, columns, suggested_mapping, total_rows, summary{valid,invalid,duplicates,opted_out}, sample_rows}` |
| POST | `/contacts/import/validate` | form `file_id`, `mapping` (JSON `{source_col: target}`) → summary + per-row results |
| POST | `/contacts/import/confirm` | form `file_id`, `mapping` → `{total, valid, invalid, duplicates, opted_out, imported}` |

`Contact`: `{id, user_id, phone, first_name, last_name, email, company, notes,
custom_fields, groups[{id,name}], opted_out, created_at, updated_at}`.

## Groups

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/groups` | `[Group]` with `contact_count` |
| POST | `/groups` | `{name, description?}` → 201 (409 on duplicate name) |
| GET | `/groups/{id}` | `GroupDetail` (+`contact_ids`) |
| PUT | `/groups/{id}` | rename |
| DELETE | `/groups/{id}` | `204` |
| POST | `/groups/{id}/contacts` | `{contact_ids}` → detail |
| POST | `/groups/{id}/contacts/remove` | `{contact_ids}` → detail |

## Templates

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/templates` | list |
| POST | `/templates` | `{name, message}` — 422 on unsupported variables |
| GET | `/templates/{id}` | one |
| PUT | `/templates/{id}` | update |
| POST | `/templates/{id}/duplicate` | 201 copy |
| POST | `/templates/preview` | `{message, first_name?, …}` → `{preview, variables_found, variables_missing}` |
| DELETE | `/templates/{id}` | `204` |

Supported variables: `first_name`, `last_name`, `phone`, `email`, `company`, `notes`.

## Campaigns

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/campaigns?status=&search=&page=&page_size=` | paginated with per-status counts |
| POST | `/campaigns` | `{name, message_template, recipients:{scope: all\|group\|contacts, group_id?, contact_ids?}, status?: DRAFT\|READY}` → 201 |
| GET | `/campaigns/{id}` | detail incl. recipients + counts |
| PUT | `/campaigns/{id}` | edit DRAFT only; status changes via dedicated endpoints |
| DELETE | `/campaigns/{id}` | `204` |
| POST | `/campaigns/{id}/validate` | regenerates recipients + message logs; returns `ValidationReport` |
| POST | `/campaigns/{id}/ready` | validate & mark READY (422 if validation fails) |
| POST | `/campaigns/{id}/duplicate` | 201 copy as DRAFT |
| POST | `/campaigns/{id}/pause` | READY/SCHEDULED/RUNNING → PAUSED |
| POST | `/campaigns/{id}/resume` | PAUSED → READY |
| POST | `/campaigns/{id}/cancel` | any non-terminal → CANCELLED |

`ValidationReport`: `{campaign_id, valid, total_recipients, pending,
skipped_invalid_phone, skipped_duplicate, skipped_opted_out,
skipped_empty_message, skipped_missing_fields, errors[], warnings[],
infos[], previews[{contact_id, name, phone, preview, status, error}]}`.

## Devices

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/devices` | list (real registrations only) |
| POST | `/devices/register` | `{device_name, device_identifier, platform}` → 201 DISCONNECTED |
| POST | `/devices/{id}/heartbeat` | `{device_identifier}` updates `last_seen` (mismatch → 403) |
| DELETE | `/devices/{id}` | `204` |

## Messages

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/messages?status=&campaign_id=&page=&page_size=` | log list with joined campaign/contact/device names |

## Opt-outs

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/optouts?search=&page=` | list |
| POST | `/optouts` | `{phone, reason?}` → 201 (409 duplicate, 422 invalid) |
| POST | `/optouts/bulk` | `{phones[]}` → `{imported, duplicates, skipped_invalid}` |
| POST | `/optouts/import` | multipart CSV/XLSX (first column = phone) |
| GET | `/optouts/export` | CSV download |
| DELETE | `/optouts/{id}` | `204` |

## Dashboard

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/dashboard/stats` | `{stats{total_contacts, active_campaigns, messages_sent, failed_messages, opt_outs, connected_devices, total_campaigns, total_templates}, recent_campaigns[], recent_activity[], devices[]}` |

All dashboard numbers come from real database records.

## Error format

Errors use `{"detail": "message"}` (FastAPI standard; 422 validation errors
use the standard `detail[]` shape). HTTP status codes: 400 bad request,
401 unauthenticated, 403 forbidden, 404 not found, 409 conflict,
422 validation, 429 rate limited.
