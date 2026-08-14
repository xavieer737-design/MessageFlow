# MessageFlow — Database

PostgreSQL ≥ 14. Migrations managed with Alembic (`backend/alembic/`).
Initial migration: `c86a3a9d1076_initial_schema`.

## Migrations

- `c86a3a9d1076_initial_schema` — Phase 1
- `9bfd64b68082_phase2_devices_pairing_send_jobs` — Phase 2 (non-destructive:
  adds columns/tables only)

## Tables

### users
| Column | Type | Notes |
| --- | --- | --- |
| id | int PK | |
| name | varchar(120) | |
| email | varchar(255) | unique, indexed |
| password_hash | varchar(255) | bcrypt |
| created_at / updated_at | timestamptz | |

### contacts
| Column | Type | Notes |
| --- | --- | --- |
| id | int PK | |
| user_id | FK users.id | indexed, CASCADE |
| phone | varchar(32) | normalized E.164; **unique per user** (`uq_contact_user_phone`) |
| first_name / last_name | varchar(120) | nullable |
| email | varchar(255) | nullable |
| company | varchar(255) | nullable |
| notes | varchar(2000) | nullable |
| custom_fields | JSON | free-form extras |
| created_at / updated_at | timestamptz | |

### contact_groups
| Column | Type | Notes |
| --- | --- | --- |
| id | int PK | |
| user_id | FK users.id | indexed, CASCADE |
| name | varchar(120) | unique per user |
| description | varchar(500) | nullable |
| created_at | timestamptz | |

### contact_group_members
Many-to-many join: `(contact_id, group_id)` composite PK, both FKs with
CASCADE.

### message_templates
`id`, `user_id` (FK, CASCADE), `name` varchar(120), `message` text,
`created_at`/`updated_at`.

### campaigns
| Column | Type | Notes |
| --- | --- | --- |
| id | int PK | |
| user_id | FK users.id | indexed, CASCADE |
| name | varchar(160) | |
| message_template | text | raw text with {{variables}} |
| status | varchar(20) | DRAFT \| READY \| SCHEDULED \| RUNNING \| PAUSED \| COMPLETED \| CANCELLED (indexed) |
| recipient_scope | varchar(20) | all \| group \| contacts |
| recipient_group_id | FK contact_groups.id | nullable |
| recipient_contact_ids | JSON | list of ids for scope=contacts |
| scheduled_at | timestamptz | nullable (stored, not executed in Phase 1) |
| created_at / updated_at | timestamptz | |

### campaign_recipients
Phase 2 additions: `message_id` (uuid when queued), `queued_at`, `sent_at`,
`attempt_count`; statuses include `PROCESSING` (command dispatched, awaiting
the device's result).
`id`, `campaign_id` FK (CASCADE, indexed), `contact_id` FK (SET NULL,
indexed), `personalized_message` text, `status` varchar(20) (PENDING \| QUEUED
\| SENT \| FAILED \| SKIPPED \| OPTED_OUT, indexed), `error` varchar(500),
timestamps.

### devices
`id`, `user_id` FK (CASCADE), `device_name`, `device_identifier`
(unique per user), `platform` (default `android`), `connection_status`
(DISCONNECTED \| CONNECTING \| CONNECTED \| OFFLINE \| ERROR), `public_key`
(text, device's Keystore public key), `paired_at`, `last_seen`,
telemetry (`phone_model`, `android_version`, `app_version`, `battery_level`,
`sim_state`, `network_state`), timestamps. CONNECTED only after
authenticated WebSocket communication.

### pairing_sessions
`id`, `user_id` FK, `token_hash` (SHA-256, unique), `device_name`,
`device_identifier`, `expires_at`, `consumed_at` (one-time use),
`device_id` FK (SET NULL), `created_at`.

### send_jobs
`id`, `user_id` FK, `campaign_id` FK (unique — one job per campaign),
`device_id` FK, `status` (ACTIVE \| PAUSED \| COMPLETED \| CANCELLED \| ERROR),
`batch_size`, `rate_per_minute`, `total_recipients`, `started_at`,
`completed_at`, timestamps.

### message_attempts
`id`, `user_id` FK, `campaign_id` FK (nullable — test messages), `recipient_id`
FK (SET NULL), `contact_id` FK, `device_id` FK, `phone`, `message`,
`message_id` (uuid, unique), `idempotency_key` (unique — `c{campaign}:r{recipient}`
or `test:{message_id}`), `status` (PENDING \| SEND_REQUESTED \| SEND_SUCCESS \|
SEND_FAILED \| SKIPPED \| OPTED_OUT), `error`, `attempt_number`, `sent_at`,
`device_timestamp`, timestamps.

### message_logs
`id`, `user_id` FK (CASCADE, indexed), `campaign_id` FK (SET NULL), `contact_id`
FK (SET NULL), `device_id` FK (SET NULL), `message` text, `status`
(indexed), `error` varchar(500), `sent_at` (nullable), `created_at`.
Only real records exist — Phase 1 produces SKIPPED/OPTED_OUT entries from
campaign validation; nothing is fabricated.

### opt_outs
`id`, `user_id` FK (CASCADE), `phone` varchar(32) normalized E.164 (unique per
user), `reason` varchar(500), `created_at`.

### audit_logs
`id`, `user_id` FK (CASCADE), `action` varchar(80) (indexed), `resource_type`,
`resource_id`, `details` JSON, `created_at`. Append-only trail powering the
dashboard activity feed and compliance.

## Indexes

- `uq_contact_user_phone (user_id, phone)` — phone unique per user
- `ix_contact_user_name (user_id, first_name, last_name)`
- `uq_group_user_name (user_id, name)`
- `uq_device_user_identifier (user_id, device_identifier)`
- `uq_optout_user_phone (user_id, phone)`
- `ix_audit_user_created (user_id, created_at)`
- `user_id` index on every user-owned table; status indexes on campaigns,
  campaign_recipients, message_logs.

## Local sandbox note

The development sandbox runs PostgreSQL 18 from embedded binaries with the
cluster in `.pgdata/` (git-ignored). On a normal machine, install PostgreSQL
with your package manager and create the role/database shown in the README.
