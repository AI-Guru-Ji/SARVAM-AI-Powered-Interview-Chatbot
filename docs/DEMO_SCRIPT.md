# 🎬 ShramSaathi AI — Customer Demo Cheat Sheet

A 7-minute walkthrough you can rehearse before showing the customer.

## Before the demo (24 hours out)

- [ ] Open Render dashboard → verify backend shows **Live**, no crashes overnight
- [ ] On the demo phone: open the app → verify Setup screen loads (warms up Render's free tier so the customer doesn't see the cold-start)
- [ ] Charge the demo phone to 100%
- [ ] Test the speaker volume — Sarvam TTS needs to be audible across a meeting room
- [ ] Bookmark the admin dashboard: `https://shramsaathi-backend.onrender.com/admin`
- [ ] Have a **backup screen-recording** of a perfect interview run, in case live demo fails
- [ ] Print/PDF a saved scorecard sample to hand the customer if they ask

## The 30-second elevator pitch

> *"ShramSaathi AI is a voice-first interview platform for India's
> 700 million blue-collar workers. A candidate speaks in their own
> language — Hindi, Tamil, Bengali, any of 11 — and our AI runs the
> entire interview: profile-building, technical assessment, and a
> personality trust profile. The recruiter gets an ATS-ready resume,
> a hire recommendation, and a Trust Profile radar chart in English —
> in under 15 minutes per candidate. Built entirely on Sarvam AI's
> Indic stack."*

## The 7-minute walkthrough

### Minute 0–1 — Setup the context

> "Imagine you are a hiring manager looking for 50 security guards. Today you'd interview each candidate by phone in 30 minutes. With this app, the candidate does it themselves in 15 minutes, in their own language, and you get a structured scorecard at the end. Let me show you."

Show the **home screen** of the phone — the ShramSaathi logo icon. Open the app.

🎯 **Wow moment 1**: Splash plays. Branded gradient, animated logo, voice greeting in Hindi auto-plays:
> *"नमस्ते! मैं श्रमसाथी AI हूँ..."*

### Minute 1–2 — Setup + OTP

- Pick **Security Guard** + **Hindi** + enter a candidate name (use a real-sounding one like "Rakesh Kumar")
- Enter any 10-digit phone number
- Skip recruiter email
- Tap **Continue**
- Show the OTP screen, type `123456`, tap **Verify**

> "In production this is a real Firebase phone OTP — for the demo we're in demo mode so any 6-digit code works."

### Minute 2–4 — Profile builder

The bot greets the candidate by name in Hindi.

Walk through 4–5 profile questions. Make sure to demo:

🎯 **Wow moment 2 — Voice confirmation for high-risk fields**:

- When the bot asks for your name → answer "मेरा नाम राकेश कुमार है"
- The bot reads back: *"आपने अपना नाम राकेश कुमार बताया। क्या यह सही है?"*
- Say **"हाँ"** → bot accepts and moves on

> "Notice — for sensitive fields like name and mobile, the AI extracts the value, reads it back to confirm, and only saves it on yes. This is critical for blue-collar candidates who may speak with strong dialects."

Continue through 3-4 more profile questions, speaking naturally in Hindi.

### Minute 4–5 — Resume review

After the last profile question (you can fast-forward if rehearsing), the app transitions to the Resume Review screen.

🎯 **Wow moment 3 — Auto-generated resume**:

> "The AI has just generated an ATS-ready resume from voice answers alone. No typing. No paperwork. Colour-coded sections, skill chips, work history."

Scroll through the resume. Tap **Download PDF** to show the system PDF viewer opening.

Tap **Continue to technical interview**.

### Minute 5–6 — Technical + behavioral round (skim)

> "We won't run the full technical interview — it's 5 role-specific questions with dynamic follow-ups powered by sarvam-30b LLM. Then 5 personality scenarios about honesty, reliability, customer focus..."

Skip ahead — answer 1–2 technical Qs to show the follow-up behavior, then tap through to behavioral intro.

> "When the candidate finishes both rounds, the LLM scores everything..."

### Minute 6–7 — The scorecard reveal

On the Submitted screen:

🎯 **Wow moment 4 — Trust Profile**:

> "Here's the candidate scorecard. Overall score, hire recommendation,
> and this — the Trust Profile radar chart — scoring 5 personality
> traits we identified as critical for blue-collar roles."

Tap **Download full scorecard PDF** — show the rendered PDF with the radar.

Switch to your **laptop's admin dashboard** (`/admin`):

> "On the recruiter side, you see every candidate as they submit in
> real time. Click any row to see their full scorecard."

## 🎯 The 5 "wow moments" — your highlight reel

1. **Voice greeting in Hindi auto-plays on app launch** — voice-first product
2. **Read-back confirmation for name/mobile** — solves a real STT pain
3. **Auto-generated colourful resume from voice** — no typing
4. **Dynamic LLM follow-up questions** — feels like a real interviewer
5. **Trust Profile radar chart in the scorecard PDF** — unique differentiator

## Questions the customer will likely ask

| Q | Best answer |
|---|---|
| **What if the candidate has a thick accent / dialect?** | Sarvam STT was trained on Indian speech specifically — handles dialects far better than English-focused alternatives. The voice confirmation flow catches the edge cases. |
| **What about candidates who can't read?** | They never have to read anything. Whole flow is voice. Splash + welcome announcement + questions all spoken. |
| **What's the cost per interview?** | ~₹2 per interview in Sarvam API usage. Plus a ~₹600/month backend hosting cost at scale. |
| **What if the AI scores wrong?** | The recruiter sees the full transcript + the per-trait reasoning + the audio response times. They make the final hire call — the AI is a *triage* layer that 10x's their throughput. |
| **Can we use our own questions?** | Yes — the question bank lives in a Python file, takes 5 minutes to swap per role. We support 4 roles today; adding a fifth takes ~1 hour. |
| **Can it be branded with our logo?** | Yes. Splash, brand header, app icon, even the PDF dashboard — all swappable in the code. |
| **What languages?** | English, Hindi, Bengali, Telugu, Punjabi, Gujarati, Marathi, Tamil, Kannada, Malayalam, Odia. Adding a new language is 1 day of work. |
| **Is candidate data secure?** | All data on private servers in India. No data goes to OpenAI/Anthropic — only Sarvam (Indian company). GDPR-compliant if needed. |
| **What happens after the interview?** | Recruiter gets an email (in production), opens the scorecard PDF, decides. Or filters across 100 candidates by overall score in the admin dashboard. |

## What to do if something breaks live

| Symptom | Recovery |
|---|---|
| App says "Could not reach backend" | "One sec — let me reconnect" → swipe app away, reopen. Render cold-start. |
| Audio doesn't play | "Let me show you on my backup phone" — have a second phone ready with the app installed |
| STT mishears badly | "Let me try in English — this language is the harder test case anyway" |
| Everything is broken | "I have a recorded run of a perfect interview" → play the backup video |
| Generate Final Report hangs | "Hindi interviews can take up to 2 minutes — let me show you the scorecard from yesterday's test on the admin dashboard instead" |

## What NOT to say in the demo

❌ **Don't say:** "It's a prototype" / "It's still in beta" / "We're working on it"
✅ **Say:** "This is our v1. We're now scaling to more languages / roles."

❌ **Don't say:** "It's powered by ChatGPT / OpenAI"
✅ **Say:** "Built entirely on Sarvam AI's Indic stack — same Indian LLM that powers the country's leading vernacular products."

❌ **Don't say:** "It might fail if..."
✅ **Say:** "It handles all 11 Indic languages, even thick accents."

## Closing the demo

> "Three questions for you before we wrap up:
> 1. Which of your hiring use cases would this fit best?
> 2. What languages and roles do you need on day one?
> 3. What would make this a no-brainer to pilot with you?"

Then **shut up** and let them answer. The customer talking = the customer buying.

## Backup assets to have on you

- [ ] Recorded screen video of a perfect interview (15 min)
- [ ] PDF of a sample scorecard (the one you generated yesterday during stakeholder testing)
- [ ] PDF of a sample resume
- [ ] One-pager about the product (Sarvam stack, languages, roles, pricing)
- [ ] A list of 3-5 reference companies you're talking to (even if early)
- [ ] Pricing pitch ready: "Pilot at ₹X per 100 interviews, paid quarterly"
