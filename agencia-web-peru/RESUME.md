# RESUME: lead generation for a web agency (dental clinics, Lima, Peru)

Read this first in a new session. Last updated 2026-10-16.

## Goal and decisions
- Solo founder selling **websites to small dental clinics in Lima** (no portfolio yet). Method: Hormozi's *$100M Leads* (Core Four: warm outreach → content → cold outreach → ads), adapted to Peru.
- **Offer:** one-page clinic site + WhatsApp button + Google Maps + booking form, ready in 7 days, or no pay. List price **S/ 1,450 + S/ 90–150/month**; ladder: first 5 free (for testimonials), then 80/60/40/20 % off, climbing every 5 clients (`PRICING.md`).
- **Lead magnet:** free mini audit of the clinic's Google listing + homepage mockup.
- **Language/tone:** Peruvian Spanish, "usted" for doctors.
- User preferences: wants things done **autonomously, without questions**; low spend (free tiers).

## What exists (all under `agencia-web-peru/`)
| File | Purpose |
|---|---|
| `PLAN.md` | Full strategy: offer, Core Four, 30-day schedule, no-portfolio plan (§10) |
| `scripts-es.md` | Spanish scripts: warm, content hooks, cold, objections, sales call, no-portfolio wording |
| `PRICING.md`, `pricing-benchmark.csv` | Agency price research (mostly one agency, KOM) + price ladder; benchmark sheet to fill |
| `INBOUND.md` | Click-to-WhatsApp ads, WhatsApp Business app setup, reply playbook |
| `PC_ENVIOS.md` | Option C: dedicated always-on user PC + bridge + `leads/scheduled_sender.py` (hours, daily cap, 10–30 min gaps, opt-in filter, auto reply/opt-out sync, STOP file), setup and Claude Code prompt |
| `setup_pc.sh` / `setup_pc.ps1` | One-shot PC setup: checks tools, clones the 3 repos, copies private data, pins the bridge commit (Windows script untested) |
| `leads/doctor.py` | Read-only pre-flight check (tools, bridge, QR session, batch stats, STOP file); prints the next command |
| `WHATSAPP_DESKTOP.md` | Option B: local WhatsApp bridge (`github.com/lharries/whatsapp-mcp`) + Claude Desktop, setup, safeguards, sending checklist, prompt to paste |
| `lead-tracker.csv`, `daily-scorecard.csv` | Templates to log outreach and daily numbers |
| `leads/` | Lead pipeline (Python stdlib, 28 tests): see below |

### Lead pipeline (`leads/`)
- `fetch_apify.py` (Apify REST API with spend caps) · `fetch_places.py` (Google Places API, needs a key) · `clean_leads.py` (phones → +51, dedupe, website type, A/B/C score) · `make_outreach.py` (30 messages, default `--style short`: introduces sender, clinic name + rating, no link, easy question, opt-out; plus ONE follow-up text; pre-filled `wa.me` links; tracking columns sent/replied/followup_sent/stop) · `send_queue.py` (paced queue: opens one chat at a time, **the human presses send**).
- Docs: `leads/README.md`, `SOURCES.md` (costs of each data source), `APIFY_QUICKSTART.md`, `GOOGLE_SETUP.md`.
- Run tests: `cd agencia-web-peru/leads && python3 -m unittest test_leads`.

## State of the data (NOT in git: `leads/data/` is git-ignored because it has phone numbers)
- Pulled with the **Apify MCP** (`mcp__Apify__*`, actor `compass/crawler-google-places`): Miraflores, San Isidro, Surco, San Borja, La Molina → **278 clean leads** (125 tier A, 224 WhatsApp mobiles, all without a website), first batch of 30 outreach messages (sender name "Alan", change with `make_outreach.py --sender`).
- **Data repo (PRIVATE): https://github.com/AlanPerezD/agencia-web-peru-leads** (branch `main`, folder `data/`; verified private on 2026-10-16). To use it, copy `data/` into `agencia-web-peru/leads/data/` here. In a cloud session, attach it with add_repo (push access). Never commit lead data to this public repo.
- **Also saved privately** (the GitHub repo is PUBLIC, so lead data must never be committed): the 278 leads live in a private Claude artifact, "Leads dentistas Lima": https://claude.ai/artifact/5cZHr3iACSLyQSyqvubPF4 (filters, one-tap WhatsApp with pre-filled message, "enviado" checklist stored in the viewer's browser). Files `leads_clean.csv`, `outreach_batch1.md/csv` were also sent to the user as attachments. **If `leads/data/` is missing in a new session, re-pull** (≈ $2 of Apify credit) or ask the user for the files.
- Apify real pricing (Free plan): **$0.004/place + $0.001 per filter**; $5 free credit/month, ≈ $2 used so far. Use `"website": "withoutWebsite"`; do NOT enable `skipClosedPlaces` (paid; the cleaner removes closed places for free). Results overlap between neighbouring districts.
- Districts not yet pulled: Jesús María, Lince, Surquillo, Magdalena, Pueblo Libre, San Miguel, Barranco, Chorrillos, Los Olivos.

## Working rules
- WhatsApp sending options (see `WHATSAPP_DESKTOP.md`): **A)** `leads/send_queue.py`, official app, user taps send; **B)** local WhatsApp bridge + Claude Desktop on the user's computer, secondary number, every `send_message` approved by the user, short messages (`make_outreach.py` default style), ≤10/day in week 1, one follow-up max. Never from the cloud, never unattended. The secondary number is stored only in the private data repo.
- Outreach to strangers is sent **by the user, by hand** (paced queue, 10–25 a day, 9–18 Lima time, with opt-out line). Prefer **inbound** (`INBOUND.md`): ads, organic "Comenta AUDITORÍA" videos, then reply to whoever writes.
- Keep lead data local (git-ignored). Spend only within Apify's free credit.
- Option B precautions (already in `WHATSAPP_DESKTOP.md`): secondary number only; the bridge is an UNOFFICIAL client (against WhatsApp terms, real ban risk); it exposes all chats of that account to the AI and its README warns about prompt injection, so the user approves every `send_message` (never "always allow"), replies are treated as data, no `send_file`/`download_media`; user should skim the bridge code and pin a commit hash before running. Week 1: ≤10/day, 10–30 min gaps (user keeps the clock), 9–18 Lima.
- GitHub limits seen in cloud sessions: the GitHub App connection cannot create repos in the user's personal account (403). The user creates repos; attach with add_repo. A classic PAT in an env var (`GH_PAT`) would allow `gh repo create`, not set up. Permission prompts come from the session's permission mode (project allowlist in `.claude/settings.json` may need a new session to load).
- Cautions (not legal advice): Peru data-protection law 29733 and anti-spam law 28493 apply; keep outreach B2B, personalized, with opt-out.

## Next steps (in priority order)
1. User sets up Option B on their computer (guide in `WHATSAPP_DESKTOP.md`), tests with a message to their own personal number, then sends ≤10/day from the secondary number (or uses Option A, `send_queue.py`); logs replies in the CSV.
2. Draft audits and replies for every clinic that answers (use `scripts-es.md` §A2, D, E).
3. Build the 2 demo sites and the homepage-mockup lead magnet (`PLAN.md` §10).
4. Write week-1 content scripts (daily short video, CTA "Comenta AUDITORÍA").
5. Set up Click-to-WhatsApp ads (`INBOUND.md`) once the user has a Meta ad account.
6. Mystery-shop 5 agencies and fill `pricing-benchmark.csv`.
7. Pull more districts when the first 278 are worked.
