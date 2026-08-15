# MessageFlow — Android App Setup

> **Status: implemented, requires device testing.** The Android app is
> code-complete for Phase 2, but no physical-device SMS test has been run
> in the development sandbox. Follow this guide to build, install and test
> on a real phone. Do not assume SMS works until a device reports success.

## Requirements

- Android Studio (Hedgehog 2023.1.1 or newer)
- JDK 17
- A physical Android phone (Android 8.0 / API 26 or newer) with a SIM
- The MessageFlow backend reachable from the phone (see networking below)

## Chosen SDK versions

| Setting | Value | Reason |
| --- | --- | --- |
| `minSdk` | 26 (Android 8.0) | `SmsManager` stable; Keystore RSA (API 23+); foreground services (API 26+); `RECEIVE_SMS` broadcasts work for any app with the permission |
| `targetSdk` | 35 | Current Play requirements |
| `compileSdk` | 35 | Latest stable |

## Opening the project

1. In Android Studio: **File → Open** → select the `android/` directory.
2. Android Studio downloads Gradle 8.7 (per `gradle/wrapper/gradle-wrapper.properties`)
   and generates the wrapper scripts on first sync. If prompted, accept.
3. Wait for the Gradle sync to finish (it resolves AGP 8.5.2, Kotlin 2.0.20
   and all dependencies from google()/mavenCentral()).

> The `gradlew` scripts and `gradle-wrapper.jar` are intentionally not
> committed (binary artifact); Android Studio generates them automatically.
> To generate them manually: `gradle wrapper --gradle-version 8.7`.

## Backend configuration

The app never hardcodes a server address. The server URL travels inside the
pairing QR code (the backend injects its own base URL), so:

- **Production:** serve the backend over **HTTPS** (`wss://` is required for
  WebSockets on a real device; browsers/Android reject cleartext to non-local
  hosts by default). Use a reverse proxy (nginx/Caddy) with a real
  certificate in front of uvicorn.
- **Local development with a physical phone:**
  1. Find your computer's LAN IP: `ip addr` / `ipconfig`.
  2. Make sure the backend binds `0.0.0.0` (the default run command does).
  3. Open MessageFlow via `http://192.168.1.50:5173` (not `localhost`). The
     Vite dev proxy forwards that address to the backend, so the pairing QR
     carries `http://192.168.1.50:5173` and the phone reaches both the REST
     API and the WebSocket through the dev server on the same Wi-Fi.
     If you serve the dashboard some other way, set `PUBLIC_SERVER_URL`
     (e.g. `http://192.168.1.50:8000`) so the QR always holds an address the
     phone can resolve - `localhost`/`127.0.0.1` would point it at itself.
  4. Android blocks cleartext HTTP by default. Two options:
     - **Debug builds:** add `android:usesCleartextTraffic="true"` to the
       `<application>` tag or use a `network_security_config.xml` allowing
       cleartext for your LAN IP. (Debug manifest override is the cleanest.)
     - **Release builds:** use HTTPS.
  5. Ensure no firewall blocks ports 8000/5173 on the computer.

## WebSocket configuration

- Endpoint: `wss://SERVER/api/devices/ws` (the app converts `https://` →
  `wss://` automatically).
- The backend must be reachable on the same host/port as the REST API.
- Heartbeat: every 30 s over the WebSocket; the server marks devices
  OFFLINE after `DEVICE_OFFLINE_TIMEOUT_SECONDS` (default 60 s) without
  traffic. OkHttp also sends protocol-level pings every 20 s.

## QR pairing

1. Open MessageFlow → **Devices → Connect Android Device**.
2. A QR appears containing only `{"mf":1,"server":...,"token":...}` —
   a short-lived (5 min), single-use token. No passwords or keys.
3. In the app: **Connect to Dashboard → Open QR Scanner** (the app asks for
   camera permission here, for scanning only).
4. On success the app shows "✓ Device paired" with name/model/Android version.

## Android permissions

| Permission | Why | When requested |
| --- | --- | --- |
| `INTERNET` / `ACCESS_NETWORK_STATE` | backend connection | install time (normal) |
| `CAMERA` | QR scanning during pairing | first scan |
| `SEND_SMS` | the app's core function: sending your campaigns via `SmsManager` | after pairing, gated behind an explanation screen |
| `RECEIVE_SMS` | optional STOP/UNSUBSCRIBE handling | only if the user enables the toggle in Settings |
| `POST_NOTIFICATIONS` | foreground service notification | app start (API 33+) |

No other permissions are requested. The app never asks for contacts,
microphone, location, accessibility or storage.

## Building & installing

```bash
cd android
# Android Studio: Run ▶ on the "app" configuration, or:
./gradlew :app:assembleDebug        # APK at app/build/outputs/apk/debug/
./gradlew :app:installDebug         # install on the connected device
./gradlew :app:testDebugUnitTest    # JVM unit tests
```

## Testing on a physical Android device

1. Install the debug APK on the phone (enable "Install unknown apps" for
   Android Studio if needed).
2. Phone and computer on the same Wi-Fi; backend running; open the web app
   via the computer's LAN IP.
3. Pair (see QR pairing). The device card shows **CONNECTED** and "Last seen
   X seconds ago" refreshes every few seconds.
4. **Send one real SMS (test):** Devices → card → **Test SMS** → enter your
   own or an explicitly consented number → confirm. The modal shows the
   REAL device-reported result (`SEND_SUCCESS` / `SEND_FAILED` + error).
5. **Campaign:** create → validate → READY → **Send Campaign** → choose the
   device. Watch progress on the campaign page (polling every 4 s).
6. Pause/resume/cancel while running; disconnect the phone and verify the
   campaign auto-pauses and resumes without duplicates on reconnect.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| App shows OFFLINE | phone can't reach backend | check LAN IP, firewall, `usesCleartextTraffic` for debug, `wss://` for release |
| Pairing fails with "details do not match" | device identifier differs between QR start and scan | restart pairing (new QR) |
| Token expired (410) | QR older than 5 minutes | generate a new QR |
| `SEND_FAILED: RESULT_ERROR_NO_SERVICE` | phone has no signal | check SIM/coverage |
| `SEND_FAILED: RESULT_ERROR_RADIO_OFF` | airplane mode | disable airplane mode |
| `SEND_FAILED: RESULT_ERROR_LIMIT_EXCEEDED` | carrier rate limit | lower `SEND_RATE_PER_MINUTE`, wait, retry |
| Test SMS disabled on card | device not currently connected | reconnect the app (foreground service restarts on boot/launch) |
| Campaign stuck in RUNNING | device offline mid-send | reconnect; the job resumes (idempotency prevents duplicates) |

## Security considerations

- Device identity: RSA-2048 keypair generated in the Android Keystore;
  the private key never leaves the phone and is never uploaded.
- WebSocket auth: short-lived device JWT + challenge-response signature
  verified by the backend against the stored public key.
- Device token and idempotency results are stored encrypted (AES-256-GCM
  with a Keystore-wrapped key) via `EncryptedStorage`.
- The QR contains only the one-time token + server URL.
- No SMS content is stored on the device beyond the bounded idempotency
  result store (encrypted, capped at 500 entries).
- Foreground service + notification keep the connection alive while the
  user can see it; nothing runs secretly.

## Platform restrictions encountered

- **Google Play policy:** apps whose core purpose isn't SMS cannot get
  `RECEIVE_SMS`/`SEND_SMS` on Play; sideloaded builds are unaffected.
- **Default SMS app:** on Android 4.4+ only the default SMS app may write
  to the SMS provider, but any app with `RECEIVE_SMS` still receives the
  `SMS_RECEIVED` broadcast (used for STOP handling).
- **Cleartext:** Android 9+ blocks plain HTTP by default for non-localhost
  hosts; release builds must use HTTPS/WSS.
- **Carrier limits:** `RESULT_ERROR_LIMIT_EXCEEDED` etc. are reported
  verbatim to the dashboard; pacing defaults are conservative
  (20 msg/min, batch of 5) and configurable via env vars.
