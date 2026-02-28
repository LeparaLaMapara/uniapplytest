# 🎓 UniApply + JobApply
### AI Agent for South African Students — via WhatsApp

> One WhatsApp number. Students apply to universities and find jobs automatically.

---

## What This Is

A **true AI agent** (not a bot) that:
- Reads matric certificates and CVs using Claude Vision
- Finds universities and jobs that match the student's profile
- Applies on their behalf automatically
- Communicates entirely via WhatsApp

No app to download. No website to visit. Just a WhatsApp number.

---

## Stack

```
WhatsApp (Twilio)  →  FastAPI  →  Claude Agent  →  Supabase
                                       ↓
                              Tools: scrape jobs,
                              process docs, apply
```

| Layer | Technology |
|-------|-----------|
| Messaging | Twilio WhatsApp Business API |
| Agent Brain | Anthropic Claude Opus |
| Web Server | FastAPI (Python) |
| Database + Storage | Supabase (PostgreSQL + Storage) |
| Job Scraping | BeautifulSoup + httpx |
| Form Submission | Playwright |

---

## Setup Guide

### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) → New Project
2. **Region: South Africa (Cape Town)** ← Important for POPIA
3. Once created, go to **SQL Editor** → paste contents of `supabase/migrations/001_schema.sql` → Run
4. Go to **Storage** → Create bucket named `documents` → Set to **Private**
5. Go to **Settings → API** → copy your URL, anon key, and service role key

### 2. Get API Keys

**Twilio**
1. [twilio.com](https://twilio.com) → Sign up free
2. Messaging → Try it out → Send a WhatsApp message
3. Follow sandbox setup
4. Copy Account SID and Auth Token from Console dashboard

**Anthropic**
1. [console.anthropic.com](https://console.anthropic.com) → Sign up
2. Create API key → add billing card

### 3. Configure Environment

```bash
cp .env.example .env
# Fill in all values in .env
```

### 4. Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

# Start server
uvicorn app.main:app --reload --port 8000
```

### 5. Expose to Internet (for Twilio)

```bash
# Download ngrok from ngrok.com
ngrok http 8000
# Copy the https URL e.g. https://abc123.ngrok.io
```

### 6. Connect Twilio

1. Twilio Console → Messaging → Settings → WhatsApp Sandbox Settings
2. "When a message comes in": `https://abc123.ngrok.io/webhook/whatsapp`
3. Method: POST → Save

### 7. Test It

On your phone, send the Twilio sandbox join code (e.g. "join silver-elephant") to the sandbox number.

Then send "Hi" — your agent will respond! 🎉

---

## Project Structure

```
uniapply/
├── app/
│   ├── main.py                    # FastAPI entry point
│   ├── api/
│   │   └── webhook.py             # Twilio webhook receiver
│   ├── agent/
│   │   └── agent.py               # Claude AI agent + tools
│   ├── core/
│   │   ├── config.py              # Settings from .env
│   │   └── supabase.py            # All Supabase operations
│   └── services/
│       ├── whatsapp.py            # Twilio send/receive
│       ├── documents.py           # OCR with Claude Vision
│       └── scraper.py             # Job scraping
├── supabase/
│   └── migrations/
│       └── 001_schema.sql         # All tables + seed data
├── .env.example
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## Supabase Dashboard

One of the best things about Supabase — you can see everything visually:

**Students table** — every student, their state, APS score, applications
**University applications** — all applications with reference numbers
**Job applications** — all job applications with status
**Jobs table** — all scraped job listings
**Storage** — all uploaded CVs, matric certs, ID documents

No code needed to see your data. Just open the Supabase dashboard.

---

## Deploying to Railway

```bash
# 1. Push to GitHub (private repo!)
git init && git add . && git commit -m "UniApply v2"
git remote add origin https://github.com/YOU/uniapply.git
git push -u origin main

# 2. Go to railway.app
# → New Project → Deploy from GitHub → Select repo
# → Add environment variables from your .env
# → Add Redis plugin (for future use)
# → Deploy!

# 3. Copy Railway URL into Twilio webhook settings
```

---

## Adding More Universities

Edit the SQL file and run in Supabase SQL Editor:

```sql
INSERT INTO universities (id, name, short_name, location, province, application_url, closing_date)
VALUES ('dut', 'Durban University of Technology', 'DUT', 'Durban', 'KwaZulu-Natal', 'https://www.dut.ac.za/apply', '30 September');

INSERT INTO university_programs (university_id, name, faculty, duration, min_aps, required_subjects)
VALUES ('dut', 'Diploma in Information Technology', 'IT', '3 years', 22, '[{"name":"Mathematics","min_level":"D"},{"name":"English","min_level":"D"}]');
```

---

## POPIA Compliance Checklist

- [ ] Privacy policy page published
- [ ] Consent collected before any data
- [ ] Supabase region set to South Africa (Cape Town)
- [ ] Sensitive fields (ID number) encrypted
- [ ] Data deletion process in place
- [ ] Information Officer appointed

---

## Commands Students Can Use

| Command | Action |
|---------|--------|
| `Hi` / any message | Start the process |
| `STATUS` | Check application status |
| `RESTART` | Start over |
| `HELP` | Show help |
| `JOBS` | Switch to job applications |
| `UNIVERSITY` | Switch to university applications |

---

## Cost Estimate (Testing Phase)

| Service | Cost |
|---------|------|
| Supabase Free tier | $0 |
| Twilio (100 messages) | ~$0.50 |
| Claude API (10 students) | ~$0.50 |
| Railway (hobby) | $5/month |
| **Total to start** | **~$6/month** |
