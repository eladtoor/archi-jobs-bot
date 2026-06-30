# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository.

## What this is

A single-user **Hebrew Telegram bot** that scans Israeli job boards for **architecture
(אדריכלות) jobs in the Beer Sheva commuter area** and alerts **Karin** (a Hebrew-speaking
architect). It runs autonomously and fully hands-off; all alerts are in Hebrew.

- **End user:** Karin — architect in Beer Sheva. Wide role net: licensed architect +
  drafting/BIM + interior design + urban/landscape planning. Beer Sheva commuter ring only.
- **Maintainer:** Elad (`eladto@ac.sce.ac.il`).
- **Guiding rule:** recall-first ("never miss a real job"), now **precision-tuned** for
  role + location (see *Filtering philosophy*).

## Architecture / pipeline

```
fetch (per source)
  → classify       relevance: judged on the ROLE (title + clean description)
  → passes_geo     location:  judged on the job's STATED location field
  → derive_subfield label
  → dedup          grow-only SQLite, alert-then-commit (record only after a successful send)
  → Telegram       Hebrew alert (Karin); ops/health → admin chat (Elad)
```

Entry point: `run.py` (adds `src/` to path) → `arch_job_bot.main:main`. Equivalent:
`python -m arch_job_bot.main`. The scheduler (APScheduler) polls every ~12 min, sends a
daily 09:00 heartbeat and a Sunday 09:05 weekly digest.

## Layout

```
src/arch_job_bot/
  main.py              Pipeline: fetch → match → geo → dedup → alert; CLI modes
  models.py            JobPosting dataclass (full_text / match_text / dedup_key)
  config.py            loads config/*.yaml (override dir: ARCH_BOT_CONFIG_DIR)
  fetch/
    http_client.py     curl_cffi chrome impersonation, backoff, challenge-page guard
    base.py            BaseSource, clean(), normalize_posted_date()
    sources/           alljobs, jobmaster, drushim, jobkarov, beersheva_muni, maavarim
  matching/
    classifier.py      recall-first relevance gate (reject gates before acceptance)
    geo.py             commuter-ring location gate
    subfield.py        derive תחום label (default "אדריכלות כללית")
    normalize.py       shared Hebrew normalization (niqqud, final letters, slash, ws)
  dedup/store.py       grow-only SQLite + conservative cross-source suppression
  alert/               sender (dispatcher), telegram, email, formatter, digest
  health/monitor.py    per-source liveness (distinguishes "quiet" from "broken")
config/                keywords.yaml, geo.yaml, sources.yaml
data/                  seen_jobs.sqlite3, health.json (git-ignored; committed by CI)
tests/                 pytest + saved board HTML in tests/fixtures/
```

## Configuration (no code changes needed)

- **`config/keywords.yaml`** — relevance terms (`arch_word_forms`, `role_titles`,
  `permit_jargon`, `adjacent_positive`, `english_titles`) and reject gates
  (`reject_software_titles`, `structural_terms`, `sales_terms`, `non_arch_drafting_domains`,
  `procurement_terms`, ambiguous-architect handling).
- **`config/geo.yaml`** — `commuter_towns` (allowed, with spelling variants), `region_words`
  (`דרום/נגב`), `remote_terms`, `exclude_cities` (denylist).
- **`config/sources.yaml`** — per-source `enabled`, query URLs, `arch_only`/`geo_trusted`
  flags, poll cadence.
- **`.env`** (git-ignored; template `.env.example`) — `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID` (Karin → jobs+digest), `TELEGRAM_ADMIN_CHAT_ID` (Elad → ops; falls
  back to Karin's chat), optional `ALERT_EMAIL_TO`/`SMTP_*`.

## Filtering philosophy (important)

Matching is **substring on normalized text** (`matching/normalize.normalize()`), applied to
the **right field** — not the whole card blob:

- **Relevance** is judged on `JobPosting.match_text()` = **title + clean description**
  (company name deliberately excluded, so an architecture firm name can't rescue a non-arch
  role). The classifier runs reject gates (software-architect, sales, structural, non-arch
  drafting, procurement) **before** acceptance; passing the posting's `title` enables a
  title-scoped reject (a clearly-sales TITLE is dropped even if an arch word appears in the
  body). Acceptance stays recall-first.
- **Location** is judged on the job's **own parsed location field** (`passes_geo(...,
  location=...)`). On general boards: keep the commuter ring, explicit remote, or a bare
  `דרום/נגב` region; **drop any other named city** (incl. ones not on the denylist, e.g.
  Lod). Sources with no per-card location (Drushim/Maavarim) fall back to a hardened blob
  scan where an explicitly excluded city beats a stray remote/region token.

`full_text()` (title + company + whole-card `raw_text`) is kept **only** as the stable
dedup content-hash basis and the geo blob fallback — do not reintroduce it as the relevance
input.

## Run / test

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q          # tests (must stay green)
python run.py --dry-run --once                          # fetch + classify + print; no sends/writes
python run.py --seed                                    # mark current jobs seen, no alerts
python run.py --once                                    # one real cycle (auto-seeds if DB empty)
python run.py                                            # run forever (poll + heartbeat + digest)
python -m arch_job_bot.alert.telegram <BOT_TOKEN>        # print chat ids during setup
```

Pure Python 3.12; deps in `requirements.txt` (`curl_cffi`, `selectolax`, `PyYAML`,
`APScheduler`, `python-dotenv`, `pytest`). Telegram/email use stdlib only.

## Deploy

- **Active:** GitHub Actions cron — `.github/workflows/scan.yml` (`*/15`), runs
  `python run.py --once` and **commits `data/seen_jobs.sqlite3` + `data/health.json` back**
  for dedup persistence (the recurring `chore: dedup state [skip ci]` commits).
- **Recommended long-lived:** `deploy/systemd/arch-job-bot.service` on an Oracle Always-Free
  VM or a Raspberry Pi (residential/clean IP).

## Gotchas

- **Cloud-disabled sources:** `jobkarov` (datacenter IPs blocked) and `beersheva_muni`
  (F5 BIG-IP blocks the GitHub ASN) are `enabled: false`; they work from a residential IP —
  re-enable on a Pi/home host. `drushim` intermittently 403s from the GitHub ASN (kept on;
  redundant with alljobs/jobmaster).
- **Secret on disk:** a live `TELEGRAM_BOT_TOKEN` sits in `.env` (git-ignored). Never commit
  it; never echo it in logs/output.
- **AllJobs promoted cards:** the results page injects promoted "hot-board" cards outside the
  `region=7` filter — now handled by the stated-location geo gate.
- **Chat routing:** `TELEGRAM_CHAT_ID` and `TELEGRAM_ADMIN_CHAT_ID` currently point at the
  same chat; split once Karin's chat id is known.
- When changing the parsers, keep `tests/test_parsers.py` green — it pins DOM selectors
  against saved fixtures (the offline analogue of the per-source health check).
