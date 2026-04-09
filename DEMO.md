# Sentinel Demo

A walkthrough of the things you'll actually do in your first day with Sentinel. Every command in this file is a real command you can run.

---

## 1. Start the server and set the API key

The daemon is a local FastAPI server on port 9849. Start it once, then leave it running.

```bash
pip install -e .
sentinel serve &
sentinel config --api-key YOUR_GEMINI_KEY
```

Verify it came up:

```bash
sentinel health
```

Expected output:
```
ok  server: up        port: 9849
ok  database: ready
ok  llm: configured
```

---

## 2. Add rules in natural language

Sentinel sends your sentence to the LLM and gets structured rule conditions back. You don't pick a domain or a schedule from a dropdown — you just say what you want.

```bash
sentinel add "Block YouTube during work hours"
sentinel add "No Twitter or Reddit on weekdays from 9am to 6pm"
sentinel add "Always block all gambling sites"
sentinel add "Let me check Hacker News only between 12 and 1pm"
```

List what got created:

```bash
sentinel rules
```

Each rule shows its parsed schedule and target so you can verify the LLM got it right. Toggle one off:

```bash
sentinel toggle 2
```

---

## 3. Start a pomodoro

```bash
sentinel pomodoro start --work 25 --break 5 --cycles 4
sentinel pomodoro status
```

Output mid-session:
```
pomodoro  cycle 2/4  state: work  remaining: 18m12s
```

Stop early if you need to:

```bash
sentinel pomodoro stop
```

---

## 4. Set up habits and check in

```bash
sentinel habit add "Read 30 minutes" daily 1
sentinel habit add "Pushups" daily 50
sentinel habit add "Long walk" weekly 3
sentinel habit list
```

Log a habit:

```bash
sentinel habit log 1
```

See today's habit board:

```bash
sentinel habit today
```

Output:
```
[x] Read 30 minutes      streak: 12d
[ ] Pushups              streak: 4d
[x] Long walk            this week: 1/3
```

---

## 5. Use focus modes

A focus mode is a heavier pomodoro — usually longer, optionally locked.

```bash
sentinel focus start --minutes 90 --locked
sentinel focus status
```

While focus is active, every distraction rule is upgraded to `block` and the lockdown can't be exited until the timer ends. For a softer version, drop `--locked`.

You can also switch your global mode:

```bash
sentinel mode list
sentinel mode switch deep-work
sentinel mode current
```

Modes change which rule pack is active — work, weekend, vacation, etc.

---

## 6. Ask the AI a question about your data

This is the killer feature. Sentinel keeps your activity local, but lets you ask the LLM about it.

```bash
sentinel ask "What's my biggest distraction this week?"
sentinel ask "When am I most productive?"
sentinel ask "How does my journal mood correlate with my productivity?"
sentinel ask "What rule would help me the most right now?"
```

The LLM gets a summarized, PII-redacted view of your stats, habits, journal moods, and rules — and answers in plain English. Your raw data never leaves the box.

---

## 7. View your daily report

```bash
sentinel report daily
```

Sample:
```
daily report  2026-04-08
score          78 / 100
productive     5h 42m
distracted     1h 18m
top apps       VS Code (3h12m), Terminal (1h44m), Slack (38m)
top domains    github.com, openai.com, news.ycombinator.com
violations     2 (twitter.com x2)
streak         12 days
note           Strong focus block 9am-12pm. Afternoon dipped after Slack peak.
```

For more depth:

```bash
sentinel report weekly
sentinel report peak-hours
sentinel report triggers
sentinel digest daily
```

---

## 8. Run an experiment

Sentinel can A/B test you against yourself. Pick a hypothesis, set a duration, and Sentinel measures the difference.

```bash
sentinel ask "Suggest an experiment based on my last week of data"
```

The LLM might suggest: "Try blocking all news sites before noon for 7 days." Set it up:

```bash
sentinel add "Block all news sites before noon" --tag experiment-news
```

After a week:

```bash
sentinel report weekly
sentinel ask "Did blocking news in the morning change my productivity?"
```

The intelligence layer ties the experiment tag to the productivity delta and reports back.

---

## 9. Create and use templates

Templates are rule packs you can apply with one command. Sentinel ships with a few; you can save your own.

```bash
sentinel template list
sentinel template apply deep-work
```

This applies a curated set of rules — block all social media, enforce a 90-minute pomodoro, switch mode to `deep-work`, mute Slack notifications via webhook.

You can also bootstrap from a persona during onboarding:

```bash
sentinel onboarding apply student
sentinel onboarding apply founder
sentinel onboarding apply writer
```

Each persona is a tested set of rules + habits + focus defaults.

---

## 10. Check achievements and XP

Every productive action earns points. Crossing thresholds unlocks achievements and levels.

```bash
sentinel points total
sentinel points history
```

Output:
```
xp        4,820
level     7
next      level 8 at 5,500 xp (680 to go)
streak    12 days
```

List achievements:

```bash
sentinel achievement list
sentinel achievement check
```

```
[x] First Block             you blocked your first distraction
[x] Pomodoro Pro            completed 50 pomodoros
[x] Habit Hero              7-day habit streak
[ ] Iron Will               30-day streak (12/30)
[ ] Lockdown Survivor       complete a 4-hour locked focus block
```

Create a personal challenge with stakes:

```bash
sentinel challenge create "No twitter week" 168
sentinel commitment add "Ship Sentinel v1" --deadline 2026-05-01 --stakes 100
```

Check the leaderboard (local or shared):

```bash
sentinel leaderboard show
```

---

## What's next

- `sentinel --help` lists every top-level command.
- `sentinel <command> --help` lists subcommands.
- The web dashboard is at `http://localhost:9849/dashboard` once `sentinel serve` is running.
- Realtime activity streams over Server-Sent Events at `/events`.
- The browser extension lives in `extension/` — load it as an unpacked extension in Chrome or Arc.

Have fun. Block harder.
