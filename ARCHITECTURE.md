# Sentinel Architecture

The world's first AI-native accountability app. Every feature is powered by or enhanced by LLMs.

**Design principles**: Minimal code (Python, fewer lines for more features). LLM-native (natural language in, structured behavior out). Text-first (CLI + browser extension now, GUI later). macOS first, cross-platform later.

---

## System Overview

```
                          +------------------+
                          |   CLI (click)    |
                          +--------+---------+
                                   |
+---------------------+   +--------v---------+   +------------------+
| Browser Extension   +-->|   Core Engine    +-->| Block Enforcer   |
| (Chrome/Arc)        |   |   (FastAPI)      |   | - /etc/hosts     |
+---------------------+   +--------+---------+   | - pf firewall    |
                                   |              | - process killer |
                          +--------v---------+   +------------------+
                          |  LLM Classifier  |
                          |  (Gemini Flash)  |
                          +--------+---------+
                                   |
                          +--------v---------+
                          |  SQLite Database |
                          +------------------+
```

All communication between the browser extension and the core engine happens over `localhost` HTTP. The core engine runs as a LaunchDaemon for persistence.

---

## File Structure

```
sentinel/
  sentinel/
    __init__.py
    main.py                 # CLI entry point (click)
    server.py               # FastAPI server (localhost:9849)
    db.py                   # SQLite models + migrations
    config.py               # Settings, API key, preferences

    engine/
      __init__.py
      rules.py              # Rule engine — NL rules -> structured conditions via LLM
      monitor.py            # Activity monitor — foreground app, window title, URL
      classifier.py         # LLM classifier — classifies activity against rules
      enforcer.py           # Block enforcer — kills apps, edits /etc/hosts, pf rules
      scheduler.py          # Time-based rule activation, break allowances

    llm/
      __init__.py
      client.py             # Gemini Flash client (user-provided API key)
      prompts.py            # All LLM prompts (rule parsing, classification, negotiation)

    interventions/
      __init__.py
      countdown.py          # 5-second countdown before block
      friction.py           # Breathing exercises, typing challenges
      negotiation.py        # AI negotiation to earn unblock time
      photo_proof.py        # Photo proof of task completion

    accountability/
      __init__.py
      penalties.py          # Financial penalties (Stripe integration)
      partners.py           # Accountability partner notifications
      stats.py              # Usage statistics, productivity scoring

  extension/
    manifest.json           # Chrome MV3 manifest
    background.js           # Service worker — manages state, talks to core engine
    content.js              # Content script — monitors URLs, injects overlays
    overlay.html            # Blocking overlay with countdown
    overlay.css

  daemon/
    com.sentinel.daemon.plist   # LaunchDaemon config
    install.sh                  # Installs daemon, sets permissions
    uninstall.sh

  pyproject.toml
  Makefile                  # install, dev, test, build
```

---

## Component Details

### Rule Engine (`engine/rules.py`)

Natural language rules are sent to Gemini Flash and parsed into structured conditions.

```
User input:  "Don't let me watch YouTube during work hours"

LLM output:  {
  "target": {"domains": ["youtube.com"], "apps": ["YouTube"]},
  "schedule": {"days": ["mon-fri"], "start": "09:00", "end": "17:00"},
  "action": "block",
  "context": "entertainment"
}
```

Rules are stored in SQLite and evaluated by the classifier in real-time. Context-aware: the same domain (e.g., reddit.com/r/programming vs reddit.com/r/funny) can be productive or distracting depending on the rule.

### Activity Monitor (`engine/monitor.py`)

Polls every 1 second via macOS APIs:
- **Foreground app**: `NSWorkspace.sharedWorkspace().frontmostApplication()`
- **Window title**: Accessibility API (`AXUIElementCopyAttributeValue`)
- **Browser URL**: Received from browser extension via HTTP

Activity is logged to SQLite for stats. Only the last 30 days are kept.

### LLM Classifier (`engine/classifier.py`)

On every activity change, the classifier sends the current activity + active rules to Gemini Flash. The LLM returns a verdict: `allow`, `warn`, or `block`.

Batching: multiple rules are evaluated in a single LLM call. Response is cached per (activity, rule_set) tuple for 60 seconds to minimize API costs.

For ambiguous cases (context-aware blocking), the classifier considers page title, URL path, and content summary from the browser extension.

### Block Enforcer (`engine/enforcer.py`)

Three-layer blocking (hardest to bypass):

1. **Process killing**: `kill -9` on blocked app PIDs. Re-kills on respawn (polled every 1s).
2. **DNS blocking**: Writes blocked domains to `/etc/hosts` pointing to `127.0.0.1`.
3. **Firewall blocking**: `pf` (packet filter) rules to block IPs associated with blocked domains.

Requires `sudo` — granted once during installation via the LaunchDaemon.

### Persistence Daemon (`daemon/`)

A macOS LaunchDaemon (`com.sentinel.daemon.plist`) that:
- Starts on boot before user login
- Restarts if killed
- Re-applies `/etc/hosts` and `pf` rules if tampered with
- Survives app deletion (daemon lives in `/Library/LaunchDaemons/`)

The daemon is the enforcer. The CLI and server are the interface. Separation ensures blocking persists even if the user deletes the app directory.

### Browser Extension (`extension/`)

Chrome Manifest V3 extension (compatible with Arc):

- **Content script** runs on every page. Sends the current URL and page title to `http://localhost:9849/activity` every second.
- **Blocking overlay**: When the core engine returns `block`, the content script injects a full-page overlay with a 5-second countdown, then redirects to a blocked page. Reuses the proven Cold Turkey overlay pattern.
- **Content sampling**: For context-aware rules, the content script sends a summary of visible text to help the classifier distinguish productive vs. distracting content.

### Interventions

Before hard-blocking, Sentinel offers friction-based interventions:

| Intervention | Description |
|---|---|
| **Countdown** | 5-second warning overlay. User can back out voluntarily. |
| **Breathing** | Guided breathing exercise (10-30s) before allowing access. |
| **Typing challenge** | Type a phrase like "I am choosing distraction over my goals." |
| **AI negotiation** | Chat with the LLM to justify why you need access. LLM can grant 5-15 min. |
| **Photo proof** | Upload a photo proving you completed a task before unblocking. |

Each rule can specify which interventions to apply and in what order.

### CLI Interface

```
sentinel add "No Twitter except during lunch (12-1pm)"
sentinel add "Block all games on weekdays" --penalty 5.00
sentinel status                  # active rules, current activity
sentinel stats                   # today's productivity score, time wasted
sentinel stats --week            # weekly breakdown
sentinel config --api-key KEY    # set Gemini API key
sentinel config --partner EMAIL  # add accountability partner
sentinel pause 15m               # pause all blocking for 15 min (requires intervention)
sentinel remove <rule-id>        # remove a rule (requires intervention if locked)
```

Built with `click`. The CLI talks to the FastAPI server on `localhost:9849`.

---

## Data Model (SQLite)

```sql
rules
  id            INTEGER PRIMARY KEY
  natural_text  TEXT        -- original user input
  parsed_json   TEXT        -- LLM-structured conditions
  action        TEXT        -- block | warn | friction
  intervention  TEXT        -- countdown | breathing | typing | negotiate | photo
  penalty_usd   REAL        -- financial penalty amount
  locked        BOOLEAN     -- requires intervention to remove
  created_at    TIMESTAMP
  active        BOOLEAN

activity_log
  id            INTEGER PRIMARY KEY
  timestamp     TIMESTAMP
  app_name      TEXT
  window_title  TEXT
  url           TEXT
  domain        TEXT
  rule_id       INTEGER     -- matched rule, if any
  verdict       TEXT        -- allow | warn | block
  duration_s    INTEGER     -- seconds spent

stats_daily
  date          TEXT PRIMARY KEY
  productive_s  INTEGER
  distracted_s  INTEGER
  blocked_count INTEGER
  score         REAL        -- 0-100 productivity score

domains_seen
  domain        TEXT PRIMARY KEY
  first_seen    TIMESTAMP
  category      TEXT        -- LLM-classified category, cached
  times_blocked INTEGER
```

---

## LLM Usage

**Provider**: Google Gemini Flash (cheapest per-token, fast enough for real-time classification).

**API key**: User-provided, stored in `~/.config/sentinel/config.toml`.

**Where LLMs are used**:
1. **Rule parsing** — natural language to structured JSON (once per rule creation)
2. **Activity classification** — is this activity violating a rule? (on every activity change, cached)
3. **Context classification** — is this specific page productive or distracting? (on ambiguous pages)
4. **Domain categorization** — what category is this domain? (once per new domain, cached in DB)
5. **AI negotiation** — conversational unblocking with justification required
6. **Photo proof verification** — does this photo show task completion?
7. **Productivity scoring** — daily summary analysis

**Cost control**: Aggressive caching. Classification results are cached for 60s per unique activity. Domain categories are cached permanently. Estimated cost: <$0.10/day for typical use.

---

## Security Model

The blocking system is designed to be hard (not impossible) to bypass:

1. **LaunchDaemon** runs as root, survives reboot and app deletion
2. **pf firewall** rules require root to modify
3. **/etc/hosts** changes are monitored and re-applied by the daemon every 5s
4. **Locked rules** require completing an intervention chain to remove
5. **Financial penalties** are charged immediately on bypass attempts
6. **Accountability partners** are notified on bypass attempts

The user can always fully uninstall via `sentinel uninstall` — but this requires completing all active interventions and notifies accountability partners. The goal is friction, not a prison.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| CLI | click |
| HTTP server | FastAPI + uvicorn |
| Database | SQLite (via sqlite3 stdlib) |
| macOS APIs | pyobjc (NSWorkspace, Accessibility) |
| LLM | Google Gemini Flash (google-generativeai SDK) |
| Browser ext | Chrome MV3 (vanilla JS) |
| Payments | Stripe (for financial penalties) |
| Daemon | launchd (macOS native) |
| Packaging | pyproject.toml + Makefile |

---

## Installation Flow

```
git clone ... && cd sentinel
make install        # pip install -e ., installs CLI
sentinel setup      # prompts for Gemini API key, installs LaunchDaemon (requires sudo)
```

The browser extension is loaded manually via `chrome://extensions` (developer mode) during development. Production distribution via Chrome Web Store later.
