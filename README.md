# 🎙 Blue Collar AI Interview Bot
**Powered by Sarvam AI — Built for India**

An AI-powered voice interview bot for hiring blue-collar workers (housekeeping, electrician, plumber, security guard) with support for **Hindi and English**.

---

## Features
- 🎤 Voice-to-voice interview (speak questions, listen to answers)
- 🗣️ Hindi + English support (auto-detects language)
- 🧠 LLM-based evaluation with scores for communication, domain knowledge, confidence
- 📊 JSON score report saved for every candidate
- 🔌 Roles: Housekeeping, Electrician, Plumber, Security Guard

---

## Tech Stack

| Component     | Sarvam API                          | Model         |
|--------------|-------------------------------------|---------------|
| Speech → Text | `/speech-to-text`                  | `saaras:v3`   |
| LLM Logic     | `/v1/chat/completions`             | `sarvam-2b-v0.5` |
| Text → Speech | `/text-to-speech`                  | `bulbul:v3`   |

---

## Setup

### Step 1 — Install dependencies
```bash
# On Ubuntu/Debian first:
sudo apt-get install portaudio19-dev python3-dev ffmpeg

# Then install Python packages:
pip install -r requirements.txt
```

### Step 2 — Set your API key
```bash
cp .env.example .env
# Edit .env and add your Sarvam API key:
# SARVAM_API_KEY=your_key_here
```
Get your key from: https://dashboard.sarvam.ai

### Step 3 — Test the APIs
```bash
python test_apis.py
```
This verifies TTS, LLM, and evaluation work before starting interviews.

### Step 4 — Run the interview bot
```bash
python interview_bot.py
```

---

## Project Structure
```
interview_bot/
├── interview_bot.py        ← Main entrypoint
├── test_apis.py            ← API connectivity test
├── requirements.txt
├── .env.example            ← Copy to .env
├── data/
│   └── question_bank.py    ← Questions in Hindi + English
├── utils/
│   ├── sarvam_api.py       ← STT / TTS / LLM wrappers
│   └── audio_utils.py      ← Microphone recording + playback
└── output/
    ├── temp/               ← Temporary audio files
    └── report_*.json       ← Candidate score reports
```

---

## How It Works

```
Candidate speaks  →  [Saaras v3 STT]  →  Transcript text
                                               ↓
Question text     →  [Bulbul v3 TTS]  ←  [Sarvam-2B LLM]
                                               ↓
                    After all Q&A  →  Score Report (JSON)
```

---

## Sample Score Report (output JSON)
```json
{
  "candidate": "Ramesh Kumar",
  "role": "electrician",
  "language": "hi-IN",
  "evaluation": {
    "overall_score": 7,
    "communication": 6,
    "domain_knowledge": 8,
    "confidence": 7,
    "summary": "Ramesh showed solid technical knowledge about MCBs and safety. Communication was clear.",
    "hire_recommendation": true,
    "strengths": ["Strong safety awareness", "Practical experience"],
    "improvements": ["Could improve Hindi fluency"]
  }
}
```

---

## Extending the Bot

- **Add a new role**: Add an entry to `data/question_bank.py`
- **Change voice**: Edit `speaker` in `utils/sarvam_api.py` (options: meera, pavithra, arvind, amol)
- **Add more languages**: Change `language_code` to `ta-IN`, `te-IN`, `bn-IN`, etc.
- **Web UI**: Wrap with Flask/FastAPI and use the Sarvam WebSocket streaming API for real-time

---

## Sarvam AI Supported Languages
`hi-IN` Hindi · `en-IN` English · `ta-IN` Tamil · `te-IN` Telugu · `bn-IN` Bengali  
`mr-IN` Marathi · `gu-IN` Gujarati · `kn-IN` Kannada · `ml-IN` Malayalam · and more
