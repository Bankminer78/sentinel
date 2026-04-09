# Sentinel — The world's first AI-native accountability app

> Every feature powered by an LLM. More features than every competitor combined.

Sentinel is a local-first, terminal-native accountability tool. You write rules in plain English, an LLM parses them into structured behavior, and a daemon enforces them on your machine. 71 modules, 1387 tests, 8227 lines of Python — and roughly one feature per 100 LoC.

```
71 modules · 1387 tests · 8227 LoC · 0 dependencies on the cloud for your data
```

---

## Why Sentinel

| Feature                          | Sentinel | Cold Turkey | SelfControl | Freedom | Opal | Overlord | RescueTime |
|----------------------------------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Natural-language rules           | ✓ |   |   |   |   |   |   |
| LLM-classified activity          | ✓ |   |   |   |   |   |   |
| Context-aware blocking           | ✓ |   |   |   |   |   |   |
| Domain blocking                  | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   |
| App blocking                     | ✓ | ✓ |   | ✓ | ✓ | ✓ |   |
| Whitelist mode                   | ✓ | ✓ |   | ✓ |   |   |   |
| Hard lockdown                    | ✓ | ✓ |   | ✓ |   |   |   |
| Pomodoro                         | ✓ |   |   |   |   |   |   |
| Focus modes                      | ✓ | ✓ |   | ✓ | ✓ |   |   |
| Schedules                        | ✓ | ✓ |   | ✓ | ✓ |   |   |
| Friction interventions           | ✓ | ✓ |   |   | ✓ |   |   |
| AI negotiation to unblock        | ✓ |   |   |   |   |   |   |
| Photo proof                      | ✓ |   |   |   |   |   |   |
| Achievements + XP + levels       | ✓ |   |   |   |   |   |   |
| Challenges + leaderboards        | ✓ |   |   |   |   |   |   |
| Habit tracker                    | ✓ |   |   |   |   |   |   |
| Journal with mood + AI search    | ✓ |   |   |   |   |   |   |
| Commitments with stakes          | ✓ |   |   |   |   |   |   |
| Long-form journeys               | ✓ |   |   |   |   |   |   |
| Daily rituals                    | ✓ |   |   |   |   |   |   |
| Behavioral forecasting           | ✓ |   |   |   |   |   |   |
| Correlation discovery            | ✓ |   |   |   |   |   |   |
| Self-experiments                 | ✓ |   |   |   |   |   |   |
| Pattern detection                | ✓ |   |   |   |   |   |   |
| Trigger detection                | ✓ |   |   |   |   |   |   |
| AI Q&A over your own data        | ✓ |   |   |   |   |   |   |
| Slack / Discord / SMS / email    | ✓ |   |   |   |   |   |   |
| Webhooks                         | ✓ |   |   |   |   |   |   |
| iCal calendar sync               | ✓ |   |   |   |   |   |   |
| Voice commands                   | ✓ |   |   |   |   |   |   |
| 3 privacy levels                 | ✓ |   |   |   |   |   |   |
| Local encryption + PII redaction | ✓ |   |   |   |   |   |   |
| Audit log                        | ✓ |   |   |   |   |   |   |
| Accountability partners          | ✓ |   |   | ✓ |   |   |   |
| Financial penalties              | ✓ |   |   |   |   |   |   |
| Undo / sharing / sync / backup   | ✓ |   |   |   |   |   |   |
| Web dashboard + realtime SSE     | ✓ |   |   |   |   |   | ✓ |
| CLI                              | ✓ |   |   |   |   |   |   |
| Browser extension                | ✓ | ✓ |   | ✓ | ✓ |   |   |
| Local-first                      | ✓ |   | ✓ |   |   |   |   |
| Open source                      | ✓ |   | ✓ |   |   |   |   |

Sentinel is the only one that wins on every row.

---

## Features

### Blocking
- Domain blocking via `/etc/hosts` and DNS flush
- App blocking via process kill
- Whitelist mode — block everything except what you allow
- Hard lockdown — password-gated, time-boxed, no exits

### AI classification
- LLM-powered rule parsing (Gemini Flash)
- Context-aware verdicts (`reddit.com/r/programming` vs `reddit.com/r/funny`)
- Skiplist of 60+ utility domains so the LLM never wastes a token on `google.com`

### Scheduling
- Pomodoro with configurable work/break/cycles
- Focus modes (locked or soft)
- Time-of-day and day-of-week schedules
- Break allowances per rule

### Interventions
- Countdown overlay
- Breathing exercise
- Typing challenge
- AI negotiation — chat with the LLM to earn unblock time
- Photo proof of task completion
- Math problem

### Gamification
- Achievements
- XP and levels
- Challenges with deadlines
- Leaderboards (local or shared)
- Streaks

### Tracking
- Habits with frequency and targets
- Journal with mood, tags, and AI search
- Time tracker by project
- Commitments with stakes
- Multi-step journeys with milestones
- Daily rituals

### Intelligence
- User profile inferred from behavior
- Behavioral forecasting (what will you do tomorrow?)
- Correlation discovery (sleep vs productivity, etc.)
- Self-experiments (A/B test yourself)
- Pattern detection
- Daily and weekly reports

### Integrations
- Slack notifications
- Discord notifications
- Email
- SMS via Twilio
- Webhooks
- iCal calendar sync
- Voice commands

### Privacy
- 3 privacy levels (open / private / paranoid)
- Local encryption at rest
- Automatic PII redaction before LLM calls
- Append-only audit log

### Accountability
- Accountability partners (notified on bypass)
- Financial penalties on bypass
- Shared leaderboards

### Advanced
- Undo for any destructive action
- Tags on rules
- Triggers (event-driven rules)
- Alerts
- Sharing rule packs
- Encrypted backup
- Multi-device sync
- Modes (work / weekend / vacation / custom)

### Dashboard
- Web dashboard
- Realtime updates over Server-Sent Events
- CLI with 100+ subcommands
- Browser extension (Chrome MV3 / Arc)

---

## Quick start

```bash
pip install -e .
sentinel serve &
sentinel config --api-key YOUR_GEMINI_KEY
sentinel add "Block YouTube during work hours"
sentinel add "No social media on weekdays 9am to 6pm"
sentinel pomodoro start
sentinel status
```

That's it. The daemon is running, your rules are live, and the LLM is classifying every new domain as it appears.

---

## Architecture

```
                   +------------------+
                   |   CLI (click)    |
                   +--------+---------+
                            |
+-------------------+   +---v---------------+   +-------------------+
| Browser Extension +-->|   FastAPI Server  +-->| Block Enforcer    |
| (Chrome MV3)      |   |   localhost:9849  |   | /etc/hosts + kill |
+-------------------+   +---+---------------+   +-------------------+
                            |
                   +--------v---------+
                   |  LLM Classifier  |
                   |  (Gemini Flash)  |
                   +--------+---------+
                            |
                   +--------v---------+        +------------------+
                   |  SQLite (local)  +<------>+  Realtime SSE    |
                   +------------------+        +------------------+
```

All your data stays on your machine. The only outbound traffic is structured prompts to the LLM provider you configured.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full module map.

---

## CLI reference

### Core
```
sentinel serve                            start the FastAPI daemon
sentinel config --api-key KEY             set the LLM API key
sentinel add "<rule in english>"          add a rule
sentinel rules                            list rules
sentinel remove <id>                      remove a rule
sentinel toggle <id>                      enable/disable a rule
sentinel block <domain>                   block a single domain
sentinel unblock <domain>                 unblock a single domain
sentinel status                           current activity + active rules
sentinel stats                            today's productivity score
sentinel score                            productivity score
sentinel week                             weekly summary
sentinel top                              top apps and domains
sentinel ask "<question>"                 ask the LLM about your own data
```

### Focus and time
```
sentinel pomodoro start --work 25 --break 5 --cycles 4
sentinel pomodoro status
sentinel pomodoro stop
sentinel focus start --minutes 90 --locked
sentinel focus status
sentinel mode switch work
sentinel mode current
sentinel limit add social daily 1800
sentinel limit status
```

### Tracking
```
sentinel habit add "Read 30 min" daily 1
sentinel habit log <id>
sentinel habit today
sentinel journal add "Felt focused today" --mood 8 --tags work,flow
sentinel journal mood
sentinel commitment add "Ship v1" --deadline 2026-05-01 --stakes 100
sentinel journey create "Learn Rust" --milestones 10
sentinel tracker start sentinel "writing docs"
sentinel tracker stop
```

### Gamification
```
sentinel achievement list
sentinel achievement check
sentinel points total
sentinel challenge create "No twitter week" 168
sentinel leaderboard show
```

### Accountability and lockdown
```
sentinel partner add Alex alex@example.com email
sentinel penalty list
sentinel lockdown enter --minutes 240 --password-hash ...
sentinel lockdown status
sentinel whitelist enable
sentinel whitelist add github.com
```

### Intelligence
```
sentinel report daily
sentinel report weekly
sentinel report peak-hours
sentinel report triggers
sentinel smart duplicates
sentinel smart conflicts
sentinel smart suggestions
sentinel smart explain youtube.com
sentinel digest daily
sentinel digest weekly
```

### Integrations and exports
```
sentinel calendar sync <ical_url>
sentinel calendar in-meeting
sentinel notify "Title" "Message" --channels slack,email
sentinel export
sentinel import <path>
sentinel export-rules-md
sentinel export-report-html
sentinel sync push
sentinel sync pull
```

### Setup helpers
```
sentinel onboarding check
sentinel onboarding apply student
sentinel template list
sentinel template apply deep-work
sentinel sensitivity set paranoid
sentinel health
```

Run `sentinel --help` or `sentinel <command> --help` for everything else.

---

## Stats

| | |
|---|---|
| Modules               | **71** |
| Tests                 | **1387** (passing in ~2.3s) |
| Lines of Python       | **8227** |
| Features per 100 LoC  | **~1.0** |
| External services required | **0** (LLM provider is pluggable, data is local) |

Sentinel is small on purpose. Every line earns its place. The LLM does the work that would otherwise be a thousand lines of regex and classification rules.

```
$ python -m pytest tests/
1387 passed, 2 warnings in 2.30s
```

---

## License

MIT. Do whatever you want with it.

---

## Credits

Built with:
- [click](https://click.palletsprojects.com/) for the CLI
- [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/) for the local server
- [Gemini Flash](https://ai.google.dev/) for the LLM work
- [pyobjc](https://pyobjc.readthedocs.io/) for macOS APIs
- The hard-won lessons of every accountability app that came before — Cold Turkey, SelfControl, Freedom, Opal, Overlord, RescueTime — none of which were AI-native, all of which made this one possible.
