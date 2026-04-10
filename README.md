# Sentinel

A lean, AI-native accountability app for macOS.

You interact through a native macOS GUI. Your external AI agents (your personal Claude, etc.) interact through a local REST API. The app keeps a small, sharp core of features that can't be done by an AI; everything else is a generic store the AI can use freely.

```
18 Python modules · 477 tests · 3,240 LoC · native macOS app
```

## What it does

- **Blocks distractions** with natural-language rules ("Block YouTube during work hours") parsed by an LLM into structured conditions, enforced via `/etc/hosts` and process killing.
- **Monitors activity** — foreground app, window title, browser URL — and classifies new domains automatically with Gemini Flash.
- **Common productivity** — pomodoro and locked focus sessions. That's it. No kanban, no journal, no habit tracker — your AI can build those on top.
- **AI Q&A** — ask questions about your data in plain English.
- **AI-Authored Triggers** — describe a feature in plain English, the internal Gemini agent writes a trigger recipe, Sentinel runs it on a schedule. No code, no shipped module.
- **Locks (commitment primitive)** — the Cold Turkey "I genuinely can't disable this" feature, but as a generic primitive. Lock any operation (`no_unblock_domain`, `no_delete_trigger`, or any custom kind the agent invents) for a duration. Optional friction gate for early release: wait N seconds, or type N random characters. Locks outlive the trigger that created them.
- **Generic AI Store** — a key/value + document store the AI can use to track anything (habits, notes, custom metrics) without you having to ship a feature for it.
- **macOS GUI** — a native menu-bar app with a WKWebView dashboard.
- **REST API** — everything the GUI does, your external agents can do too.

## What it doesn't do

Earlier versions had 200+ feature modules (life-OS, wellness, knowledge management, etc.). Those were cut. The principle: **if a feature can be reproduced by an AI agent writing to a generic store, it should not be a hardcoded feature.**

## Install

```bash
git clone https://github.com/Bankminer78/sentinel.git ~/git/sentinel
cd ~/git/sentinel
pip install -e .
./macos/build.sh
open ./build/Sentinel.app
```

Then click the 🛡 in your menu bar.

## API surface (for external agents)

The server runs at `http://127.0.0.1:9849`. Key endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /status` | Current foreground app, active rules, blocks |
| `GET /activities?limit=N&since=TS` | Raw activity log for analysis |
| `GET /stats` | Today's score, breakdown, top distractions |
| `GET /stats/week` · `/stats/month` | Time-windowed summaries |
| `POST /rules` `{text}` | Add a natural-language rule |
| `POST /block/{domain}` · `DELETE /block/{domain}` | Manual block/unblock |
| `POST /pomodoro/start` · `POST /focus/start` | Productivity sessions |
| `POST /triggers/author` `{request}` | Plain English → trigger recipe (internal Gemini authors it) |
| `POST /triggers` · `GET /triggers` · `POST /triggers/{name}/run` | CRUD + manual execution of triggers |
| `GET /triggers/calls` | The operations a recipe can call (for the LLM author) |
| `POST /ask` `{question}` | Natural-language query over user's data |
| `POST /ai/kv` `{namespace, key, value}` | Generic K/V store for the AI |
| `GET /ai/kv/{namespace}/{key}` | Read |
| `POST /ai/docs` `{namespace, doc, tags}` | Append-only document store |
| `GET /ai/docs?namespace=X&since=TS` | Read documents |
| `GET /ai/search?q=X` | Full-text across the AI store |
| `GET /ai/summary` | What the AI has stored (overview) |
| `POST /chat/sessions` · `POST /chat/messages` | Persistent chat memory |
| `POST /vision/snapshot` | Take a screenshot, classify with vision LLM |
| `GET /audit` · `POST /backup` | Audit trail and SQLite backup |

The full list lives in `sentinel/server.py`.

### How an external agent uses this

```python
import httpx
SENTINEL = "http://127.0.0.1:9849"

# Read what the user has been doing
acts = httpx.get(f"{SENTINEL}/activities?limit=200").json()

# Ask Sentinel's own AI a question
ans = httpx.post(f"{SENTINEL}/ask", json={"question": "How much time on YouTube this week?"}).json()

# Track something the user wanted (no specialized module needed)
httpx.post(f"{SENTINEL}/ai/docs", json={
    "namespace": "habits",
    "doc": {"name": "meditate", "completed": True, "duration_min": 10},
    "tags": ["wellness"],
})

# Read it back later
docs = httpx.get(f"{SENTINEL}/ai/docs?namespace=habits").json()
```

## Architecture

```
+----------------------------+
|   Sentinel.app (Swift)     |
|   ┌──────────────────┐     |
|   │ Menu bar 🛡      │     |    <-- you click here
|   │ WKWebView window │     |
|   └────────┬─────────┘     |
|            │ HTTP           |
+------------┼----------------+
             │
             v
+----------------------------+         +---------------------+
|   Python FastAPI server    | <-----> | External agent      |
|   (sentinel.cli serve)     |  HTTP   | (your Claude, etc.) |
|                            |         +---------------------+
|   - Rules + LLM parsing    |
|   - Activity monitor       |
|   - /etc/hosts blocking    |
|   - AI K/V + doc store     |
|   - AI-authored triggers   |
|   - Q&A                    |
|                            |
|   SQLite (~/.config/...)   |
+----------------------------+
```

16 Python modules, grouped by the abstraction they fill:

**The box** (storage + persistence + backup):
| Module | Purpose |
|---|---|
| `db` | SQLite — only 4 tables: rules, activity_log, seen_domains, config |
| `persistence` | LaunchDaemon tamper detection |
| `backup` | SQLite native `.backup` snapshots |

**Sensors** (what the system can see):
| Module | Purpose |
|---|---|
| `monitor` | macOS foreground app + browser URL polling |
| `screenshots` | `screencapture` + Gemini vision analysis |

**Effectors** (what the system can do):
| Module | Purpose |
|---|---|
| `blocker` | `/etc/hosts` block + app kill via osascript |
| `skiplist` | Static set of domains never classified (hot path) |

**LLM** (text + vision Gemini calls):
| Module | Purpose |
|---|---|
| `classifier` | Domain classification, rule parsing, rule evaluation |

**Composition** (where the agent lives):
| Module | Purpose |
|---|---|
| `ai_store` | **Generic K/V + document store** — namespaced, the agent's scratchpad |
| `triggers` | **AI-authored features** — DSL recipes the internal Gemini writes from English, runs on a schedule, with run history + revise-on-failure feedback |
| `locks` | **Commitment primitive** — write-once locks with optional friction gates. Built-in kinds (`no_unblock_domain`, `no_unblock_app`, `no_delete_trigger`, `no_disable_trigger`) are enforced by the runtime; custom kinds are enforced by the agent via `is_locked()` checks |

**Views & utilities**:
| Module | Purpose |
|---|---|
| `stats` | Score, breakdown, top distractions (one parameterized range function) |
| `query` | `/ask` — give Gemini activity + rules + question |
| `scheduler` | Time-window primitive (`is_schedule_active`) for rule activation |
| `privacy` | One config key: `minimal | balanced | full` |

**Transport**:
| Module | Purpose |
|---|---|
| `server` | FastAPI — the only thing GUI/agents talk to |
| `ui` | Single-file HTML/CSS/JS dashboard |
| `cli` | `sentinel serve` (used by the macOS app) |

Pomodoro, focus sessions, chat history, full-text search, audit log, intervention countdowns, goals, streaks, allowances, PII redaction, TTL cache — all gone. Anything an AI agent can compose from the primitives above plus a trigger recipe is no longer in this codebase.

## Tests

```bash
python -m pytest tests/   # 509 tests in <1s
```

## License

MIT
