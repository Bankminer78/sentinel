# Sentinel

AI-native accountability app. 722 lines of Python, 209 tests.

## Features

- **Natural language rules**: `sentinel add "Block YouTube during work hours"`
- **LLM classification**: Gemini Flash classifies every new domain you visit
- **Domain blocking**: /etc/hosts + DNS flush
- **App blocking**: Force-kills blocked apps
- **Smart skiplist**: 60+ utility domains never classified (Google, GitHub, etc.)
- **Activity monitoring**: Tracks foreground app, window title, browser URL
- **REST API**: Browser extension talks to localhost server
- **CLI**: Add rules, check status, view stats

## Quickstart

```bash
pip install -e .
sentinel serve &           # Start the server
sentinel config --api-key YOUR_GEMINI_KEY
sentinel add "Block all social media during weekdays 9am-5pm"
sentinel add "No streaming sites ever"
sentinel status
```

## Architecture

```
CLI (click) ──→ FastAPI server (localhost:9849) ──→ Block enforcer (/etc/hosts, kill)
                      ↓
               LLM Classifier (Gemini Flash)
                      ↓
               SQLite (~/.config/sentinel/sentinel.db)
```

## Tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v  # 209 tests, <1s
```
