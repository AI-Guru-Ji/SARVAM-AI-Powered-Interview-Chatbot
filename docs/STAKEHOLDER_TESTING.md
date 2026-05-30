# 📲 ShramSaathi AI — Stakeholder Testing Guide

**Send this to your two stakeholders along with the APK file.**

You are helping test a voice-first interview app for India's blue-collar
workforce — built on Sarvam AI's Indic language stack. The whole
interview happens by voice in your own language. Takes ~15 minutes.

## What you'll need

- An Android phone (Android 8.0 or newer)
- Microphone permission (the app will ask)
- A quiet room for ~15 minutes
- Wi-Fi or mobile data

## Step 1 — Install the APK

1. Open the WhatsApp / email link from Shivam
2. Tap the file `app-release.apk` to download
3. After download, tap **Open**
4. Android will warn: *"For your security, your phone is not allowed to install unknown apps from this source"* — this is normal because the app isn't on the Play Store yet
5. Tap **Settings** → enable **Allow from this source**
6. Go back, tap **Install**
7. Tap **Open** to launch the app

## Step 2 — Walk through the interview

The app guides you step-by-step. Here's what to expect:

| Screen | What happens | What you do |
|---|---|---|
| Splash | ShramSaathi logo + tagline | Just wait ~2 seconds |
| Setup | Brand header, the bot greets you in Hindi | Pick a **Role** (try **Security Guard**), pick a **Language** (try **Hindi**), enter your **name** + 10-digit **mobile number** + leave recruiter email blank |
| OTP | Phone verification | Type **`123456`** (demo OTP, shown on screen) → tap **Verify** |
| Voice loop · Profile | 9 questions about you — name, age, location, experience, etc. | Tap the big mic button, speak your answer, tap **Stop & submit**. For sensitive fields (name, mobile, age, location) the bot will read back what it heard and ask you to say **हाँ** (yes) or **नहीं** (no) |
| Resume Review | A colourful AI-generated CV of you | Read it. Tap **Download PDF** to save a copy. Tap **Continue to technical interview** when ready |
| Voice loop · Technical | 5 role-specific job questions | Speak naturally. The bot may ask follow-ups |
| Behavioral intro | Brief breather | Tap **Begin personality round** |
| Voice loop · Behavioral | 5 scenario questions about your character | Speak honestly — there are no right or wrong answers |
| Finalize | "Generate Final Report" button | Tap it. Wait ~30–60s while the AI scores everything |
| Submitted | Your scorecard + hire chip + radar chart | 🎉 Confetti! |

## Step 3 — Share your results with Shivam

On the **Submitted** screen, after seeing your score:

1. Tap **"Share results with recruiter"**
2. Pick **WhatsApp** (or Email)
3. Select **Shivam** as the recipient
4. The message is pre-filled with a link to your scorecard PDF — just send it

OR if you prefer:

1. Tap **"Download full scorecard PDF"** — opens in your PDF viewer
2. Take a screenshot of the radar chart
3. Send the screenshot to Shivam on WhatsApp

## Step 4 — Send Shivam your feedback

Please tell Shivam:

### 🟢 What worked well
- Did the voice play clearly? Could you hear the bot?
- Did the app understand your answers correctly?
- Did the scoring feel reasonable?
- What did you like about the experience?

### 🔴 What didn't work
- Anything confusing about the screens?
- Did the bot mishear you anywhere?
- Was anything in the wrong language or didn't make sense?
- Did the app freeze or crash anywhere?

### 💡 Suggestions
- Anything that would make this better for a blue-collar candidate?
- Would you trust this for hiring decisions? Why or why not?
- What's the "wow" moment for you?

## Tips for the best experience

- **Speak clearly** — the AI is good but not perfect at noisy environments
- **Use Hindi or your native language** — that's the whole point. English works too but the demo shines in Indic languages
- **For the read-back confirmation** — when the bot says "I heard 9876543210, is that correct?", say **हाँ** (or "yes" if in English) clearly
- **If the bot mishears you** — say **नहीं** to retry, or tap **Skip** to move on
- **For follow-up questions** — give specific examples, not generic answers. The bot will ask follow-ups when answers are vague
- **For the personality round** — be honest. There really are no right answers; the AI is looking for consistency and specifics

## What if something goes wrong?

| Problem | Try this |
|---|---|
| "Could not reach backend" on the Setup screen | Check your internet, force-close and reopen the app. The first request after the server has been idle ~15 min takes ~30 seconds. |
| Mic button does nothing | Settings → Apps → ShramSaathi → Permissions → enable Microphone |
| Bot played but I couldn't hear it | Turn up volume; check phone isn't in silent mode |
| App crashed | Force-close and reopen — your progress is saved on the server and the app will resume |
| Took longer than 60s on Generate Final Report | This is normal for Hindi interviews; let it run up to 4 minutes |

## Privacy note

- Your voice recordings are processed by Sarvam AI (an Indian AI company)
- Your transcript and scorecard live on a private server
- Only Shivam and the app's recruiter see them — they are NOT shared with anyone else
- Nothing is published online or used to train AI models

Thanks for testing! Your feedback shapes whether this product launches and how. 🙏
