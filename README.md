# בוט משרות אדריכלות — באר שבע והדרום · Architecture Job-Alert Bot

Autonomously scans Israeli job boards for **new architecture (אדריכלות) openings in the
Beer Sheva commuter area** and pushes a Hebrew summary to Telegram in near-real-time.
Built for one Hebrew-speaking architect; tuned for **high recall — never miss a job**.

## What it does

```
poll boards (every ~12 min)  →  classify (recall-first Hebrew matcher)  →
geo-filter (Beer Sheva commuter towns)  →  dedup (grow-only SQLite)  →
format Hebrew message  →  send to Telegram  →  (mark seen only after delivery)
```

* **Sources (Tier-0 / MVP):** AllJobs, Drushim, JobMaster, JobKarov.
* **Match:** accepts אדריכל*/role-titles/permit-jargon/adjacent fields (interior, landscape,
  urban planning, drafting/BIM); hard-rejects software "architect", pure structural
  engineering, and real-estate sales. See `config/keywords.yaml`.
* **Geo:** Beer Sheva + Omer, Lehavim, Meitar, Rahat, Bnei Shimon, Sderot, Ofakim,
  Netivot, Kiryat Gat, Dimona, Arad (+ remote/hybrid). See `config/geo.yaml`.
* **Never-miss safeguards:** redundant sources, recall-first matcher, grow-only
  alert-then-commit dedup, silent first-run seed (no day-1 flood), and per-source
  health checks that alert if a normally-busy scraper suddenly returns nothing.

## Setup

```bash
# 1. deps (Python 3.12)
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt    # Windows
# .venv/bin/pip install -r requirements.txt                # Linux/Mac

# 2. Telegram bot
#    - message @BotFather → /newbot → copy the token
#    - have Karin open the new bot and tap Start
#    - print her chat_id:
.venv\Scripts\python -m arch_job_bot.alert.telegram <BOT_TOKEN>

# 3. secrets
copy .env.example .env          # then fill TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
```

## Run

```bash
python run.py --dry-run --once   # fetch + classify + print matches; no sends, no writes
python run.py --seed             # mark everything currently open as seen (no alerts)
python run.py --once             # one real cycle (auto-seeds first if the DB is empty)
python run.py                     # run forever: polls every ~12 min + daily 09:00 heartbeat
```

The first real run on an empty DB performs a **silent seed** automatically, so she only
gets alerts for jobs posted *after* the bot starts.

## Deploy (free, 24/7)

* **Recommended — Oracle Cloud Always-Free ARM VM** (or an always-on Pi):
  `deploy/systemd/arch-job-bot.service` runs the bot as a long-lived service.
* **Fallback — GitHub Actions:** `deploy/github-actions/scan.yml` (`*/15` cron, commits the
  dedup DB back for persistence + keepalive). Note GitHub's cron delay/skip and 60-day
  auto-disable caveats documented in that file.

## Tests

```bash
.venv\Scripts\python -m pytest tests -q
```

Covers the classifier (accept/reject incl. tricky software-"architect"/structural/sales
cases, `בודק היתרים`, English titles), geo gazetteer, dedup invariants, date normalization,
formatting, and the four parsers against saved board HTML in `tests/fixtures/`.

## Configuration (no code changes needed)

* `config/keywords.yaml` — positive terms, role titles, permit jargon, adjacent fields,
  and the tech/structural/sales reject gates.
* `config/geo.yaml` — commuter towns (+ variants), region/remote terms, excluded cities.
* `config/sources.yaml` — query URLs and cadence per source.

## Roadmap (see `.claude/plans/`)

* **v2:** Archijob (Playwright), Maavarim Negev, Beer Sheva municipality, Isra-Arch,
  GOVO Jobs; per-source health already wired; WhatsApp delivery (Green API) if wanted;
  optional email-alert ingestion as an anti-bot-proof redundant backbone.
* **v3:** Jobnet, south regional councils, Sapir/TCB, omriron, LinkedIn guest API;
  weekly recall audit.

## Known limitations

* **Facebook/WhatsApp groups are out of scope** (can't be automated safely without a
  logged-in account; we chose hands-off). This is the one real coverage gap — the cheap
  mitigation is for Karin to join 2–3 key architecture groups and enable notifications.
* JobMaster/Drushim region codes are unreliable, so the client-side geo gate is the real
  filter; their recall is supplemented by the redundancy of the other boards.
* Recall-first means occasional false positives (she'd rather see an extra than miss one).
* Scraping public job-board pages is a ToS grey-zone — kept tiny, non-commercial,
  single-user, storing only job metadata (no recruiter-contact database).
