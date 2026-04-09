# Sentinel Architecture

The world's first AI-native accountability app. Every feature is powered by or enhanced by an LLM.

**Design principles**: Minimal code (Python, fewer lines for more features). LLM-native (natural language in, structured behavior out). Text-first (CLI + browser extension now, GUI later). Local-first — your data stays on your machine.

**Current state**: 71 modules · 1387 tests (passing in ~2.3s) · 8227 lines of Python.

---

## System Overview

```
                          +------------------+
                          |   CLI (click)    |
                          +--------+---------+
                                   |
+---------------------+   +--------v---------+   +------------------+
| Browser Extension   +-->|   FastAPI server +-->| Block enforcer   |
| (Chrome MV3 / Arc)  |   |   localhost:9849 |   | /etc/hosts + kill|
+---------------------+   +--------+---------+   +------------------+
                                   |
                          +--------v---------+
                          |  LLM Classifier  |
                          |  (Gemini Flash)  |
                          +--------+---------+
                                   |
                          +--------v---------+      +-----------------+
                          |  SQLite (local)  +<---->+  Realtime SSE   |
                          +------------------+      +-----------------+
```

All inter-process communication is over `localhost` HTTP. The daemon is the enforcer; the CLI and extension are interfaces. Separation ensures blocking persists even if the user deletes the app directory.

---

## Module map (71 modules)

Every module lives at `sentinel/<name>.py`. Tests live at `tests/test_<name>.py`. The codebase is intentionally flat — one file per concept.

### Core engine (8)
| Module | Purpose |
|---|---|
| `server.py` | FastAPI app, request routing, lifecycle |
| `db.py` | SQLite schema, migrations, query helpers |
| `cli.py` | `click` CLI — 100+ commands across all features |
| `client.py` | LLM client (Gemini Flash) with caching and retries |
| `monitor.py` | Foreground app, window title, browser URL polling |
| `blocker.py` | Block enforcement: `/etc/hosts`, DNS flush, process kill |
| `classifier.py` | LLM classifier — verdicts on every activity change |
| `nlp.py` | Natural-language rule parsing |

### Blocking (5)
| Module | Purpose |
|---|---|
| `whitelist.py` | Whitelist mode — block everything except allowed |
| `lockdown.py` | Hard lockdown with password gate and timer |
| `skiplist.py` | 60+ utility domains never sent to the LLM |
| `limits.py` | Per-category time budgets (daily/weekly) |
| `triggers.py` | Event-driven rule activation |

### Scheduling (5)
| Module | Purpose |
|---|---|
| `scheduler.py` | Time-of-day, day-of-week rule activation |
| `focus_modes.py` | Locked and soft focus blocks |
| `mode.py` | Global modes: work, weekend, vacation, custom |
| `calendar.py` | iCal sync, in-meeting detection |
| `rituals.py` | Daily rituals and routines |

### Interventions (3)
| Module | Purpose |
|---|---|
| `interventions.py` | Countdown, breathing, typing, math, AI negotiation, photo proof |
| `coach.py` | Conversational nudges and unblock negotiation |
| `motivation.py` | Motivational content delivery |

### Gamification (5)
| Module | Purpose |
|---|---|
| `achievements.py` | Achievement definitions, unlock checks |
| `points.py` | XP and level math |
| `challenges.py` | User-created and system challenges |
| `leaderboard.py` | Local and shared leaderboards |
| `commitments.py` | Commitments with deadlines and stakes |

### Tracking (6)
| Module | Purpose |
|---|---|
| `habits.py` | Habit definitions, streaks, frequency |
| `journal.py` | Journal entries, mood, tags, AI search |
| `tracker.py` | Time tracking by project |
| `journeys.py` | Multi-step journeys with milestones |
| `checkins.py` | Daily and ad-hoc check-ins |
| `timeline.py` | Aggregated activity timeline |

### Intelligence (10)
| Module | Purpose |
|---|---|
| `profile.py` | User profile inferred from behavior |
| `forecasting.py` | Behavioral forecasting |
| `correlations.py` | Discovers correlations between tracked variables |
| `experiments.py` | Self-experiments with measurable hypotheses |
| `patterns.py` | Pattern detection across activity history |
| `reports.py` | Daily, weekly, peak-hours, triggers |
| `digest.py` | Daily and weekly summary digests |
| `query.py` | Structured queries against your data |
| `smart.py` | Rule duplicate / conflict / coverage analysis |
| `stats.py` | Productivity scoring, top apps, top domains |

### Integrations (8)
| Module | Purpose |
|---|---|
| `notifications.py` | Notification fan-out (Slack, Discord, etc.) |
| `email_notif.py` | Email notifications |
| `sms.py` | SMS via Twilio |
| `webhooks.py` | Outbound webhooks |
| `ical_export.py` | iCal feed export |
| `voice.py` | Voice command parsing |
| `sharing.py` | Sharing rule packs and templates |
| `partners.py` | Accountability partners (notified on bypass) |

### Privacy and security (5)
| Module | Purpose |
|---|---|
| `privacy.py` | Three privacy levels (open / private / paranoid) |
| `encryption.py` | Local encryption at rest |
| `sensitivity.py` | PII redaction before LLM calls |
| `audit.py` | Append-only audit log |
| `penalties.py` | Financial penalties on bypass |

### Persistence and lifecycle (6)
| Module | Purpose |
|---|---|
| `persistence.py` | Daemon lifecycle helpers |
| `backup.py` | Encrypted backup |
| `sync.py` | Multi-device sync |
| `undo.py` | Undo for destructive actions |
| `importer.py` | Import rules and data |
| `export_formats.py` | CSV, Markdown, HTML exports |

### Dashboard and UX (6)
| Module | Purpose |
|---|---|
| `dashboard.py` | Web dashboard routes |
| `realtime.py` | Server-Sent Events stream |
| `health.py` | Health check endpoint |
| `onboarding.py` | First-run setup, persona presets |
| `templates.py` | Rule pack templates (deep-work, etc.) |
| `tags.py` | Tagging across rules and entries |

### Context and observability (4)
| Module | Purpose |
|---|---|
| `context.py` | Active context the LLM sees |
| `environment.py` | Environment detection (network, location, device) |
| `screenshots.py` | Optional screenshot capture (privacy-gated) |
| `alerts.py` | Threshold alerts and warnings |

---

## Component details

### LLM classifier (`classifier.py` + `client.py`)

On every activity change, Sentinel sends the activity plus the active rule set to Gemini Flash and gets a verdict back: `allow`, `warn`, or `block`. Multiple rules are batched into a single call. Verdicts are cached for 60 seconds per `(activity, rule_set)` tuple. Domain categories are cached permanently.

Estimated cost: under $0.10/day for typical use.

### Natural-language rules (`nlp.py`)

```
User input:  "Don't let me watch YouTube during work hours"

LLM output:  {
  "target": {"domains": ["youtube.com"], "apps": ["YouTube"]},
  "schedule": {"days": ["mon-fri"], "start": "09:00", "end": "17:00"},
  "action": "block",
  "context": "entertainment"
}
```

Parsed rules are stored in SQLite. The classifier evaluates them in real time and is context-aware — `reddit.com/r/programming` and `reddit.com/r/funny` get different verdicts under the same rule.

### Activity monitor (`monitor.py`)

Polls every 1 second:
- **Foreground app** via `NSWorkspace.sharedWorkspace().frontmostApplication()`
- **Window title** via the Accessibility API (`AXUIElementCopyAttributeValue`)
- **Browser URL** received from the browser extension over HTTP

Activity is logged to SQLite. Only the last 30 days are retained.

### Block enforcer (`blocker.py`)

Three layers, hardest to bypass:
1. **Process killing** — `kill -9` on blocked app PIDs, re-killed on respawn
2. **DNS blocking** — `/etc/hosts` rewrites pointing to `127.0.0.1`, plus DNS cache flush
3. **Firewall blocking** — `pf` rules for IPs of blocked domains

Requires `sudo`, granted once during install via the LaunchDaemon.

### Interventions (`interventions.py`)

Friction before hard-blocking:

| Intervention | Description |
|---|---|
| Countdown | 5-second warning overlay |
| Breathing | Guided breathing exercise (10–30s) |
| Typing | Type a phrase like "I am choosing distraction over my goals" |
| Math | Solve a problem proportional to your block-bypass history |
| AI negotiation | Chat with the LLM to earn 5–15 minutes |
| Photo proof | Upload a photo proving task completion |

Each rule specifies which interventions to apply and in what order.

### Intelligence layer (`forecasting.py`, `correlations.py`, `experiments.py`, `patterns.py`, `profile.py`, `reports.py`)

The LLM doesn't just classify — it reasons over your history. The intelligence modules turn weeks of activity into:
- A behavioral profile
- Tomorrow's forecast
- Discovered correlations (sleep vs focus, mood vs distraction)
- Running self-experiments
- Daily and weekly narratives

`sentinel ask "..."` is a thin wrapper that hands the LLM a summarized, PII-redacted view of these and lets you ask anything in plain English.

### Privacy (`privacy.py`, `encryption.py`, `sensitivity.py`, `audit.py`)

Three levels:
- **open** — full activity logged, anything in prompts
- **private** — PII redacted before any LLM call (emails, names, secrets)
- **paranoid** — local LLM only, no outbound traffic, encrypted at rest

Every privileged action is appended to `audit.py`'s log so you can see exactly what happened and when.

### Dashboard and realtime (`dashboard.py`, `realtime.py`)

The FastAPI server serves a small web dashboard at `/dashboard` and a Server-Sent Events stream at `/events`. The browser extension and the dashboard both subscribe to the stream for live updates without polling.

### Browser extension (`extension/`)

Chrome Manifest V3 (compatible with Arc):
- Content script reports current URL and page title every second
- Receives verdicts and injects a full-page blocking overlay with countdown
- Sends a content sample for context-aware rules

---

## Data model (SQLite)

Sentinel uses a single SQLite database at `~/.config/sentinel/sentinel.db`. Tables track rules, activity, stats, habits, journal, commitments, journeys, achievements, points, partners, penalties, audit log, and more — one logical concept per module, one set of tables per module.

Migrations are applied automatically on startup by `db.py`.

---

## LLM usage

**Provider**: Google Gemini Flash (cheapest per-token, fast enough for real-time classification). The client is pluggable.

**API key**: User-provided, stored locally in the config directory.

**Where the LLM is used**:
1. Rule parsing — natural language to structured JSON
2. Activity classification — verdict per activity change (cached)
3. Context classification — productive vs distracting on ambiguous pages
4. Domain categorization — once per new domain (cached forever)
5. AI negotiation — conversational unblocking
6. Photo proof verification
7. Productivity scoring and daily narrative
8. `sentinel ask` — open-ended Q&A over your local data
9. Forecasting, correlation discovery, pattern detection
10. Coach nudges and motivational content

---

## Security model

Blocking is designed to be hard, not impossible, to bypass:
1. LaunchDaemon runs as root and survives reboot and app deletion
2. `pf` rules require root to modify
3. `/etc/hosts` is monitored and re-applied every 5s
4. Locked rules require completing an intervention chain to remove
5. Lockdown mode is password-gated and time-boxed with no exit
6. Financial penalties charge immediately on bypass
7. Accountability partners are notified on bypass
8. Audit log records every privileged action

The user can always fully uninstall via `sentinel uninstall` — but this requires completing all active interventions and notifies partners. The goal is friction, not a prison.

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| CLI | click |
| HTTP server | FastAPI + uvicorn |
| Database | SQLite (stdlib `sqlite3`) |
| macOS APIs | pyobjc (NSWorkspace, Accessibility) |
| LLM | Google Gemini Flash (pluggable) |
| Browser ext | Chrome MV3 (vanilla JS) |
| Daemon | launchd (macOS native) |
| Tests | pytest, pytest-asyncio |
| Packaging | pyproject.toml |

---

## Stats

```
modules            71
tests              1387 passing (~2.3s)
lines of python    8227
features per LoC   roughly 1 per 100
external services  0 required (LLM provider is pluggable, data is local)
```

```
$ python -m pytest tests/
1387 passed, 2 warnings in 2.30s

$ find sentinel -name "*.py" -not -path "*/__pycache__/*" | xargs wc -l | tail -1
8227 total

$ ls sentinel/ | grep -v __ | grep ".py$" | wc -l
71
```
