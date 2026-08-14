# Phase 2 — Android Device Integration (Implemented)

> **Status: implemented (backend + frontend + Android app code).**
> **Android SMS sending has NOT been tested on a physical device in the
> development sandbox — it requires device testing.**
> Nothing in the system claims an SMS was sent unless the Android device
> reports `SEND_SUCCESS` from Android's `SmsManager`.

## Architecture

```
MessageFlow Web Dashboard (React)
        |
        | HTTPS + WebSocket (JSON protocol)
        |
MessageFlow FastAPI Backend  (coordination layer)
        |
        | WSS  /api/devices/ws  (device JWT + RSA challenge-response)
        |
Android Companion App  (Kotlin/Compose, foreground service)
        |
        | Android SmsManager (official API)
        |
User's SIM  →  Recipient
```

The web dashboard never touches the phone's SMS stack directly. The backend
owns the send queue; the phone executes commands and reports real results.

## What was built

### Backend

- **Pairing** (`/api/devices/pairing/start|complete`, `GET /api/devices/pairing/{id}`)
  - One-time, TTL-limited (5 min) tokens; only the SHA-256 hash is stored.
  - QR payload: `{"mf":1,"server":<url>,"token":<token>}` — no secrets.
  - Completing stores the device's RSA public key and returns a device JWT.
- **Device identity & WS auth**
  - `POST /api/devices/ws` WebSocket with challenge → `{token, signature}`
    → welcome. The signature is verified against the stored public key
    (cryptography lib), so a leaked token alone cannot impersonate a device.
  - Devices are marked CONNECTED only after successful authentication;
    heartbeats refresh `last_seen`; an offline sweep marks stale devices
    OFFLINE and auto-pauses their send jobs.
- **Send engine** (`send_service.py`)
  - `POST /api/campaigns/{id}/send` — requires READY + paired device;
    **opt-outs re-checked right now** (never stale); creates `SendJob` +
    `MessageAttempt` rows with unique `message_id` and stable
    `idempotency_key` (`c{campaign}:r{recipient}`).
  - Batching (`SEND_BATCH_SIZE`, default 5) + pacing (`SEND_RATE_PER_MINUTE`,
    default 20) — configurable, conservative.
  - `GET /api/campaigns/{id}/progress` — per-status counts + fraction.
  - Results (`message_result`): only the device's `SEND_SUCCESS`/`SEND_FAILED`
    updates attempts, recipients, `MessageLog` and job completion.
  - Pause/resume/cancel stop/resume issuing new commands; cancel is terminal.
  - Idempotency: results are terminal and replay-proof; after a reconnect,
    PROCESSING recipients are re-issued with the SAME message_id so the
    device replays its stored result instead of re-sending.
  - Test messages: `POST /api/devices/{id}/test-message` → real result via
    `GET /api/devices/{id}/test-message/{message_id}` (202 + poll).
  - STOP keywords: `incoming_sms` from the device → normalized sender added
    to `opt_outs` (auto-reply off by default; config flag exists).
- **Background loops** (`core/background.py`): batch dispatcher (2 s) and
  offline sweep (10 s); disabled via `SEND_DISPATCH_ENABLED=false` in tests.

### Android app (`/android`)

- Kotlin 2.0, Jetpack Compose, Material 3, minSdk 26 / targetSdk 35.
- Screens: Welcome → Pairing (QR scan, zxing) → Dashboard (status,
  telemetry, SIM, permission gate) → Settings (reconnect, STOP toggle,
  disconnect, device identifier).
- `KeystoreIdentity` — RSA-2048 in Android Keystore; private key never
  leaves the device; challenge signing for WS auth.
- `DeviceConnectionService` — foreground service owning OkHttp WebSocket
  with exponential-backoff reconnect, 30 s heartbeats, sequential command
  execution (server-controlled queueing), real `SmsManager` results
  (single/multipart), optional incoming-SMS forwarding.
- `SendCommandProcessor` — idempotency store (encrypted, bounded) +
  local pacing floor (3 s) + pause/resume/cancel handling.
- `EncryptedStorage` — AES-256-GCM vault (Keystore key) for the device
  token and result store.
- Unit tests: processor idempotency/pacing/failure, protocol field names,
  QR payload parsing.

### Frontend

- Devices page: QR pairing modal (qrcode lib) with session polling,
  device cards (model, battery, SIM, network, queued/sent/failed,
  last seen), Test SMS modal with real result polling, Disconnect/Remove.
- Campaign detail: **Send Campaign** with device selection, live progress
  bar + per-status counters (polling, 4 s), pause/resume/cancel.

## WebSocket protocol (JSON)

```
Server→Device:  challenge {nonce}
Device→Server:  auth {device_id, token, signature(SHA256withRSA over nonce)}
Server→Device:  welcome {device_id}            | error {message}
Server→Device:  send_message {command_id, message_id, idempotency_key,
                              phone, message, send_at, test?}
Server→Device:  pause | resume | cancel | disconnect | ping
Device→Server:  heartbeat {battery_level, sim_state, network_state, app_version}
Device→Server:  message_result {message_id, status: SEND_SUCCESS|SEND_FAILED,
                                error?, timestamp?}
Device→Server:  incoming_sms {sender, body, received_at?}  (opt-in only)
Device→Server:  pong
```

## Message state machine

```
CampaignRecipient: PENDING → QUEUED → PROCESSING → SENT | FAILED
                          ↘ SKIPPED | OPTED_OUT (at validation or send time)

MessageAttempt:    PENDING → SEND_REQUESTED → SEND_SUCCESS | SEND_FAILED
                  (terminal; replay-proof via idempotency_key + message_id)
```

Terminology is precise: `SEND_REQUESTED` = command delivered to the device;
`SEND_SUCCESS` = device confirmed `SmsManager` accepted the message;
`SEND_FAILED` = device-reported error (carrier delivery is not claimed —
no "delivered" status exists without carrier delivery receipts).

## API changes (all Phase 1 endpoints untouched)

```
POST /api/devices/pairing/start
POST /api/devices/pairing/complete
GET  /api/devices/pairing/{session_id}
POST /api/devices/{id}/heartbeat            (extended telemetry)
POST /api/devices/{id}/disconnect
POST /api/devices/{id}/test-message
GET  /api/devices/{id}/test-message/{message_id}
WS   /api/devices/ws
POST /api/campaigns/{id}/send
GET  /api/campaigns/{id}/progress
(pause/resume/cancel extended to send jobs)
```

## Database migration

`9bfd64b68082_phase2_devices_pairing_send_jobs` adds:

- `devices`: `public_key`, `paired_at`, `phone_model`, `android_version`,
  `app_version`, `battery_level`, `sim_state`, `network_state`
- new tables: `pairing_sessions`, `send_jobs`, `message_attempts`
- `campaign_recipients`: `message_id`, `queued_at`, `sent_at`,
  `attempt_count`; statuses extended with `PROCESSING`

Non-destructive: existing data is preserved (`alembic upgrade head`).

## Required device testing (final checklist)

1. Pair on a real phone; device shows CONNECTED with live "last seen".
2. Grant SMS permission; Test SMS to a consented number → real result.
3. Campaign → validate → send → watch progress → disconnect mid-send →
   reconnect → verify no duplicate SMS (idempotency) and campaign resumes.
4. Pause/resume/cancel behavior on the phone.
5. Opt-out a recipient after validation but before send → skipped at send.
6. STOP keyword from another phone → sender added to opt-outs.

## Security

- HTTPS/WSS required outside localhost; cleartext blocked on Android 9+.
- Short-lived one-time pairing tokens; hashes only in the DB.
- Keystore device identity; server-side signature verification.
- Per-user device isolation (all device queries scoped by `user_id`;
  token/session endpoints verify ownership; verified by tests).
- No private keys, passwords or JWT secrets in QR codes or on the device
  (token encrypted at rest).
- Server-side authorization on every send/progress/test endpoint.
