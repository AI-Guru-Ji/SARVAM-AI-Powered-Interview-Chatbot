# Deploy the ShramSaathi AI backend to Render (one-time, ~30 minutes)

This guide gets your FastAPI backend running on a **public HTTPS URL**
so your stakeholders can test the Android app from their own phones —
no laptop tether required.

We use **Render.com's free Docker service**. Free tier costs ₹0/month
but sleeps after 15 min of no traffic (cold-starts ~30–60s).

## Prerequisites

- A GitHub account (free): https://github.com/join
- Your project pushed to a GitHub repo

If you haven't pushed yet, do this first:

```bash
cd /home/shivam/Documents/1.ETO/8.SarvamAI/interview_bot_sarvam/interview_bot
git status                                   # confirm everything is committed
git remote -v                                # if no remote, see step "Push to GitHub" below
git push                                      # push to your repo
```

### Push to GitHub (if you haven't yet)

1. Visit https://github.com/new
2. Repository name: `shramsaathi-ai` (or whatever you want)
3. Set to **Private** (recommended — contains your code)
4. Click **Create repository**
5. Copy the commands GitHub shows you. Typically:
   ```bash
   git remote add origin git@github.com:YOUR_USERNAME/shramsaathi-ai.git
   git branch -M main
   git push -u origin main
   ```

# Step-by-step Render deployment

## Step 1 — Create a Render account

1. Visit https://render.com
2. Click **Get Started for Free**
3. Sign up with GitHub (easiest — auto-links your repos)
4. Confirm email if prompted

## Step 2 — Create a new Blueprint

A "Blueprint" in Render = read `render.yaml` from your repo, create
services automatically.

1. From the Render dashboard, click **New +** (top right) → **Blueprint**
2. Click **Connect a repository** → authorize Render to read your GitHub
3. Pick the **shramsaathi-ai** repo (or whatever you named it)
4. Render reads `render.yaml` and shows: *"1 service will be created: shramsaathi-backend"*
5. Click **Apply**

## Step 3 — Set the SARVAM_API_KEY (secret env var)

Render won't deploy until secret env vars are set.

1. After clicking Apply, Render opens the new service page
2. Go to **Environment** in the left sidebar
3. Find `SARVAM_API_KEY` → click **Add Value**
4. Paste your Sarvam API key (same one in your local `.env`)
5. Click **Save Changes**

Render will now build the Docker image and deploy it. Watch the **Logs**
tab — first build takes 4–8 minutes because it's downloading WeasyPrint's
cairo/pango libraries.

✅ When you see `Application startup complete.` in the logs, deployment is live.

## Step 4 — Copy the public URL

At the top of the service page, Render shows the URL like:

```
https://shramsaathi-backend.onrender.com
```

**Save this URL.** You'll use it everywhere from now on.

## Step 5 — Verify it works

Open the URL in your browser:

```
https://shramsaathi-backend.onrender.com/v1/health
```

You should see JSON:
```json
{"ok":true,"sarvam_ok":true,"db_ok":true,"demo_mode":true}
```

The admin dashboard is at:

```
https://shramsaathi-backend.onrender.com/admin
```

This is the page you bookmark to watch your stakeholders' test results
arrive in real time.

# Building the signed Android APK against the Render backend

## Step A — Generate the release keystore (one-time, ~3 minutes)

```bash
cd /home/shivam/Documents/1.ETO/8.SarvamAI/interview_bot_sarvam/interview_bot/mobile/android
keytool -genkey -v \
        -keystore app/upload-keystore.jks \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -alias shramsaathi
```

It will prompt you for:
- **Keystore password** — make one up, **write it down** (you cannot reset this)
- **First and last name** — your name
- **Organisational unit / Organisation** — your company name (or "ShramSaathi")
- **City / State / Country code** — wherever you are (e.g. Lucknow / UP / IN)
- Confirm: type `yes`
- **Key password for shramsaathi** — press Enter to use the same as keystore password

## Step B — Create `key.properties`

```bash
cd /home/shivam/Documents/1.ETO/8.SarvamAI/interview_bot_sarvam/interview_bot/mobile/android
nano key.properties
```

Paste this — replace `YOUR_PASSWORD` with the keystore password you just chose:

```properties
storePassword=YOUR_PASSWORD
keyPassword=YOUR_PASSWORD
keyAlias=shramsaathi
storeFile=app/upload-keystore.jks
```

Save: `Ctrl+O`, Enter, `Ctrl+X`.

**Note:** Both `key.properties` and `upload-keystore.jks` are already
in `.gitignore`. Never commit them.

## Step C — Build the signed APK

```bash
cd /home/shivam/Documents/1.ETO/8.SarvamAI/interview_bot_sarvam/interview_bot/mobile

flutter build apk --release \
    --dart-define=BACKEND_URL=https://shramsaathi-backend.onrender.com
```

(Substitute the actual URL from Step 4.)

First build: ~3–5 minutes. Output at:

```
mobile/build/app/outputs/flutter-apk/app-release.apk
```

Size: ~25 MB.

# Verify the APK before sharing

Plug your phone in via USB, then:

```bash
adb install -r mobile/build/app/outputs/flutter-apk/app-release.apk
```

Unplug the cable. Open the app on your phone. **It should still work**
— it's now hitting the Render backend over the internet, not your
laptop. Run a quick test interview to verify.

✅ If the test works, you're ready to share with stakeholders. See
[STAKEHOLDER_TESTING.md](STAKEHOLDER_TESTING.md) next.

# Subsequent updates

After this one-time setup, future updates are just:

```bash
git push                                          # backend redeploys auto
cd mobile && flutter build apk --release \
    --dart-define=BACKEND_URL=https://shramsaathi-backend.onrender.com
# Share the new APK with stakeholders
```

# Troubleshooting

| Symptom | Diagnosis | Fix |
|---|---|---|
| Render build fails: "ImportError: cairo" | WeasyPrint native libs missing | Dockerfile is correct — re-trigger build; Render's cache may have been stale |
| First request after 15 min idle hangs ~60s | Free-tier cold-start | Normal. Upgrade to Starter ($7/mo) for always-on |
| `/v1/health` returns 502 | Backend crashed | Check Render Logs tab for the Python traceback |
| Phone says "Could not reach backend" | DNS / network blip | Wait 30s and retry; Render's TLS sometimes lags first time |
| APK install: "App not installed" | Old version with different signing key on the phone | `adb uninstall com.shramsaathi.shramsaathi` then install again |

# Cost summary

| Item | Cost |
|---|---|
| Render free-tier web service | ₹0/mo (sleeps when idle) |
| GitHub private repo | ₹0/mo |
| Render Starter plan (no sleep) | $7/mo ≈ ₹600/mo — only if you go to production |
| Sarvam API usage | ~₹2 per interview (you already pay this) |

**Total for the stakeholder testing phase: ₹0.**
