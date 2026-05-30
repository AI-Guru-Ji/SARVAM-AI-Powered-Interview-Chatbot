# ShramSaathi AI — Android Candidate App

Flutter Android client for the ShramSaathi AI mobile MVP. Talks to the
FastAPI backend at `ui/fastapi/` over HTTPS+multipart, drives the
candidate through profile + technical + behavioral rounds entirely by
voice, and submits the result for the recruiter to review on the
existing Streamlit dashboard.

This directory was created in Week 2 of the mobile project. Backend is
in `ui/fastapi/` and is already production-ready for demo deployment.

## Quick start

### 1. Install Flutter (one-time)

```bash
# Ubuntu / Debian — snap is easiest:
sudo snap install flutter --classic

# Or via the official tarball:
curl -L https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_3.24.3-stable.tar.xz \
     -o flutter.tar.xz
sudo tar -xf flutter.tar.xz -C /opt
echo 'export PATH=/opt/flutter/bin:$PATH' >> ~/.bashrc
source ~/.bashrc

# Verify
flutter doctor
```

`flutter doctor` will tell you about missing pieces — install **Android
Studio** for the SDK + emulator, and accept the Android licences:

```bash
flutter doctor --android-licenses
```

### 2. Fetch dependencies

```bash
cd mobile
flutter pub get
```

### 3. Start the backend (in another terminal)

```bash
# From the repo root
DEMO_MODE=1 venv/bin/uvicorn ui.fastapi.app:app --reload --port 8000
```

### 4. Run the app

**Emulator:** `http://10.0.2.2:8000` is the default; just hit Play in
your IDE or:

```bash
flutter run
```

**Physical phone on same Wi-Fi:** find your laptop IP and override the
backend URL at build time:

```bash
flutter run --dart-define=BACKEND_URL=http://192.168.1.42:8000
```

**Demo with ngrok (recommended for live customer demos):**

```bash
# Laptop
ngrok http 8000
# Then on the phone build with the public URL:
flutter run --dart-define=BACKEND_URL=https://abcd-1234.ngrok-free.app
```

## Project structure

```
mobile/
├── pubspec.yaml                         dependencies + Flutter SDK pin
├── android/app/src/main/AndroidManifest.xml   mic permission
└── lib/
    ├── main.dart                        app entry + GoRouter routes
    ├── config.dart                      compile-time backend URL
    ├── theme.dart                       Material 3 theme
    ├── models/api_models.dart           Dart mirror of FastAPI response types
    ├── services/
    │   ├── api_client.dart              dio-based HTTP for all endpoints
    │   └── audio_service.dart           native mic record + WAV playback
    ├── state/providers.dart             Riverpod providers + session controller
    └── screens/
        ├── setup_screen.dart            role / language / name / phone
        ├── otp_screen.dart              phone OTP (demo-mode hint included)
        ├── voice_loop_screen.dart       the main interview loop (all 3 rounds)
        ├── finalize_screen.dart         "Generate Final Report" + 30-60s wait
        └── submitted_screen.dart        thank-you terminal screen
```

## Routes / FSM

```
/ (setup) → /otp → /loop → /finalize → /submitted
```

The `/loop` screen renders three different stages without itself
switching screens — the only thing that changes turn-to-turn is the
question text the backend returns. When the backend says
`stage == 'awaiting_finalize'`, the app navigates to `/finalize`.

## Watching results in real time (recruiter / admin)

After each candidate submits their interview, the backend keeps the
full scorecard. To watch results pour in live:

```
https://<your-backend>/admin
```

Self-refreshing HTML page. Each row shows candidate name, role,
overall score, hire chip, and links to the JSON + PDF scorecard. No
auth in DEMO_MODE — for production, set `SARVAM_BACKEND_API_KEY` and
pass it as a Bearer header.

Programmatic access:

```bash
curl https://<your-backend>/v1/admin/sessions | jq
```

## Stakeholder / customer sharing flow

After the candidate finishes the interview, the Submitted screen has
**two share affordances**:

1. **"Download full scorecard PDF"** — opens the dashboard PDF in the
   phone's PDF viewer (Drive / Acrobat / etc).
2. **"Share results with recruiter"** — opens the native Android
   share sheet pre-filled with a WhatsApp/Email-ready message
   containing the scorecard URL. The candidate picks the recipient
   (you), they get the link, you tap → see the PDF.

Both work whether the backend is on a local laptop (with adb reverse)
or deployed to a public URL (Render).

## Release distribution playbook

### One-time setup: generate a release keystore

Android won't accept an unsigned APK from outside the Play Store. Generate a keystore **once** (keep it safe — losing it means you can never push an update to the same app):

```bash
cd mobile/android
keytool -genkey -v \
  -keystore app/upload-keystore.jks \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias shramsaathi
```

It'll prompt for:
- A keystore password (remember this — write it down securely)
- Your name / organisation / city (just fill in something sensible — Play Store doesn't show this publicly)

Then create `mobile/android/key.properties`:

```properties
storePassword=<the password you just chose>
keyPassword=<same password unless you set a different one>
keyAlias=shramsaathi
storeFile=app/upload-keystore.jks
```

**Both files are gitignored.** Never commit either.

### Generate launcher icons (one-time, do once now)

```bash
cd mobile
flutter pub get
dart run flutter_launcher_icons
```

This reads `assets/logo.png` and writes platform-correct icons into
`android/app/src/main/res/mipmap-*/`. Now the home-screen icon is the
ShramSaathi logo instead of the default Flutter rocket.

### Build the signed release APK

```bash
cd mobile

# Demo / on-prem backend URL pointed at ngrok or LAN IP
flutter build apk --release \
  --dart-define=BACKEND_URL=https://your-backend.example.com

# Output: mobile/build/app/outputs/flutter-apk/app-release.apk
```

To enable crash reporting (optional), pass a Sentry DSN at build time:

```bash
flutter build apk --release \
  --dart-define=BACKEND_URL=https://your-backend.example.com \
  --dart-define=SENTRY_DSN=https://abc123@o12345.ingest.sentry.io/67890
```

Without `SENTRY_DSN`, Sentry initialisation is skipped entirely — no
network calls, no signup required.

### Distribute the APK — three options

#### Option A — Direct file share (simplest)

WhatsApp / Email / Drive the `app-release.apk` to the customer. On the
phone:
1. Open the link, download the APK
2. Tap the downloaded file
3. Android will warn "Install from unknown source" — tap **Settings**, enable installs from this source, return, tap **Install**

Works in 5 minutes. No Google account required on either side. Good for the customer demo.

#### Option B — Firebase App Distribution (free, recommended for demos)

You get a clickable install link that handles the "Allow unknown sources" flow gracefully:

1. Create a Firebase project at https://console.firebase.google.com (free)
2. Add an Android app — package name: `com.shramsaathi.shramsaathi`
3. Install the Firebase CLI:
   ```bash
   curl -sL https://firebase.tools | bash
   firebase login
   ```
4. Upload the APK:
   ```bash
   firebase appdistribution:distribute \
       mobile/build/app/outputs/flutter-apk/app-release.apk \
       --app <FIREBASE_APP_ID> \
       --release-notes "Demo build" \
       --groups "demo-testers"
   ```
5. Firebase sends an email + share link to anyone added to the group. They tap the link, install the APK, app opens.

#### Option C — Play Store Closed Beta (production-ready route)

1. Pay $25 one-time for a Play Console developer account: https://play.google.com/console
2. Create a new app, fill in the listing
3. Upload `app-release.apk` to the **Closed testing** track
4. Add tester emails — they get a Play Store link, tap Install
5. **Skips the full Play Store review process** (1-2 day approval, vs weeks for public release)

Required Play Store metadata you'll need:
- App icon (1024×1024 PNG)
- Feature graphic (1024×500 PNG)
- 2-8 screenshots (any resolution, 16:9 or 9:16)
- Short description (80 chars)
- Full description (4000 chars)
- Privacy policy URL (host on your website / GitHub Pages)
- Content rating questionnaire (5 minutes)

Defer to **after winning the deal** — APK direct-share or Firebase is plenty for the customer demo.

## Known limitations (MVP scope — defer to Phase 2)

- No background-resume of an in-progress interview after app kill.
- No retry UX on flaky network — failed uploads show an error toast,
  user re-taps the record button to try again.
- No silence-based auto-stop. The candidate explicitly taps "Stop &
  submit". A future revision can wire `record`'s amplitude stream into
  a simple VAD for hands-free flow.
- No localised UI chrome — buttons / titles are English. The
  *questions* are localised because they come from the backend. Add
  intl-based UI localisation once we lock the strings.
- Crashlytics / Sentry not wired yet — drop in once we hit real users.
- Only Android tested. iOS works in theory because Flutter is
  cross-platform, but mic permission strings + entitlements aren't
  set up.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Setup screen shows "Could not reach backend" | Backend not running OR wrong URL | Confirm `uvicorn ... --port 8000` is up; on physical device pass `--dart-define=BACKEND_URL=...` |
| Record button does nothing | Mic permission denied | Long-press app icon → App info → Permissions → enable Microphone |
| OTP screen says "Invalid OTP" | Backend not in DEMO_MODE | `DEMO_MODE=1 uvicorn ...` or use the real OTP from `/v1/auth/otp/request` response |
| "Could not play question audio" | Sarvam TTS network error OR low storage | Check backend logs; ensure `/v1/health` returns `sarvam_ok: true` |
| Finalize takes >2 minutes | Sarvam LLM slow or rate-limited | Watch backend logs; the call timeout is 90s — fail will show as a toast |
