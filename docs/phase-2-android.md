# Phase 2 — Android Device Integration (Recommended Architecture)

> Status: **planned**. Nothing in this document is implemented yet. Phase 1
> deliberately stops at campaign preparation. Do not begin Phase 2 without
> explicit approval.

## Goals

1. Send prepared READY campaigns from a real Android phone using its SIM.
2. Report **true** delivery state only (SENT by the device, FAILED with the
   device-reported error, or still PENDING).
3. Stay fully compliant: consent-based lists, opt-outs enforced at send time,
   per-number throttling, no carrier/spam-filter bypass, no anonymous sending.

## Components

```
┌──────────────┐   HTTPS/WebSocket    ┌──────────────────┐
│  MessageFlow │ ◀──────────────────▶ │  Android app     │
│  web app     │   pairing, jobs,     │  (Kotlin)        │
│  (existing)  │   status callbacks   │  companion       │
└──────────────┘                      └────────┬─────────┘
                                               │ Android SMS Manager API
                                               │ (SmsManager.sendTextMessage /
                                               │  sendMultipartTextMessage)
                                               ▼
                                          Phone SIM
```

### Backend additions (this repo)

1. **Pairing flow**
   - `POST /api/devices/{id}/pair` — create a short-lived pairing token
     (random, 5-minute expiry, one-time).
   - `POST /api/devices/{id}/pair/confirm` — the Android app presents the
     token (entered or QR-scanned) plus its signing public key; the server
     marks the device `CONNECTED` and stores the key.
   - Extend `Device` with `public_key`, `paired_at` (nullable). Keep
     `connection_status` semantics honest: CONNECTED only after a confirmed
     pairing + live heartbeat.

2. **Transport**
   - WebSocket endpoint `/api/ws/devices/{device_id}` authenticated with a
     short-lived device JWT (separate token type `device`).
   - Heartbeat every 30 s already exists via `POST /devices/{id}/heartbeat`
     (keep for REST fallback); add `battery_level`, `sim_state`, `model`,
     `android_version` to the heartbeat payload and store only what devices
     actually report.

3. **Send jobs**
   - New `SendJob` concept or reuse `Campaign` + `CampaignRecipient`:
     - `POST /api/campaigns/{id}/start` — Phase 2 only, requires status READY,
       ≥1 CONNECTED device, and a fresh validation pass (opt-outs re-checked
       at send time — never trust a stale list).
     - The server chunks recipients into rate-limited batches (e.g. 1 SMS /
       5–15 s per SIM, configurable, never faster than the user configured).
     - Job state machine per recipient: PENDING → QUEUED → SENT/FAILED with
       device-reported error text. **No synthetic statuses** — SENT only when
       the device confirms `SmsManager` returned success.
   - `POST /api/campaigns/{id}/pause|resume|cancel` already exist and apply
     to in-flight jobs.

4. **Opt-out enforcement at send time**
   - Re-query `opt_outs` immediately before each batch; anything newly opted
     out is skipped and logged (`OPTED_OUT`).
   - Keyword processing: Android app forwards incoming SMS (with user grant)
     via WebSocket; server matches `STOP`/`UNSUBSCRIBE`/localized keywords,
     adds the sender to the opt-out list, optionally auto-replies once.
     (Requires `RECEIVE_SMS` permission — user-visible and optional.)

5. **Delivery reports**
   - Device reports `sent_at` + optional `message_id` per recipient; backend
     updates `MessageLog` (SENT/FAILED, `sent_at`, `device_id`) and campaign
     counters. Nothing is written that the device did not report.

### Android companion app (new repository: `android/`)

- Kotlin, Jetpack Compose, min SDK 26.
- Permissions (all declared and explained in-app, never hidden):
  `SEND_SMS`, `RECEIVE_SMS`, `READ_SMS` (optional, for STOP keyword
  handling), `POST_NOTIFICATIONS`.
- Screens: sign in (same JWT account), device registration (name + UUID),
  pairing (token entry / QR scan), home with connection status, battery,
  SIM state, queued message count, per-message send log.
- Foreground service with notification while a send job runs; handles
  Doze/background limits honestly (batches + wake locks only during active
  jobs).
- Sending engine: `SmsManager` (single-part and multipart for >1 segment),
  sequential per-recipient sending with configured delays, retry only on
  transient errors (`RESULT_ERROR_RADIO_OFF`, `NO_SERVICE`), permanent errors
  (`RESULT_ERROR_GENERIC_FAILURE`) reported as FAILED with the code.
- Security: WebSocket pinned with the pairing public key, device token stored
  in Android Keystore, no logging of message content.

### Data model changes

- `devices`: + `public_key text`, `paired_at timestamptz`, + reported
  telemetry columns (nullable).
- `campaign_recipients`: statuses already support QUEUED/SENT/FAILED.
- `message_logs`: already has `device_id`, `sent_at`, `error`.
- New table `pairing_tokens` (token_hash, device_id, user_id, expires_at,
  consumed_at).
- New table `send_batches` (campaign_id, device_id, started_at, finished_at,
  sent, failed, skipped) for auditability.

### Compliance guardrails (non-negotiable)

- No fake delivery reports; SENT requires device confirmation.
- No carrier/spam-filter bypass, no SIM cloning, no anonymity, no hiding the
  sender — messages are sent from the user's own phone and SIM.
- Rate limits per device and per campaign; default pacing conservative.
- Opt-out list enforced at send time; STOP keyword handling built-in.
- Full audit trail (`audit_logs`) for pairing, starts, pauses, cancels.

### Rollout order

1. Pairing tokens + device keys + WebSocket skeleton (server-side).
2. Android app: sign-in, registration, pairing, heartbeat telemetry.
3. Send job engine (server) + sending service (app) for single campaigns.
4. Delivery reporting + Message Log UI polish.
5. STOP keyword processing and auto opt-out.
6. Multi-device load balancing across campaigns (optional).
