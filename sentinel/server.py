"""FastAPI server — browser extension + CLI talk to this."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from . import db, classifier, monitor, blocker, skiplist
import asyncio

app = FastAPI(title="Sentinel")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
conn = None


def get_conn():
    global conn
    if conn is None:
        conn = db.connect()
    return conn


class ActivityReport(BaseModel):
    url: str = ""
    title: str = ""
    domain: str = ""


class RuleCreate(BaseModel):
    text: str


class ConfigSet(BaseModel):
    key: str
    value: str


@app.on_event("startup")
def startup():
    global conn
    conn = db.connect()
    monitor.start()


@app.post("/activity")
async def report_activity(report: ActivityReport):
    """Browser extension reports current URL."""
    monitor.set_browser_url(report.url)
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key")
    if not api_key or not report.domain:
        return {"verdict": "allow"}

    # Skip utility domains
    if skiplist.should_skip(report.domain):
        return {"verdict": "allow"}

    # Check if already seen
    seen = db.get_seen(c, report.domain)
    if seen == "none" or seen == "approved":
        return {"verdict": "allow"}

    # Check if already blocked
    if blocker.is_blocked_domain(report.domain):
        return {"verdict": "block"}

    # Classify if unseen
    if not seen:
        category = await classifier.classify_domain(api_key, report.domain)
        db.save_seen(c, report.domain, category)
        if category in ("streaming", "social", "adult", "gaming"):
            # Check rules
            rules = db.get_rules(c)
            if rules:
                verdict = await classifier.evaluate_rules(
                    api_key, report.title or "", report.domain, report.title or "", rules)
                if verdict == "block":
                    blocker.block_domain(report.domain)
                    db.log_activity(c, "", report.title, report.url, report.domain, "block")
                    return {"verdict": "block", "category": category}
            else:
                # No rules — auto-block known bad categories
                if category in ("adult",):
                    blocker.block_domain(report.domain)
                    return {"verdict": "block", "category": category}
                return {"verdict": "warn", "category": category}
        return {"verdict": "allow"}

    # Already categorized as bad
    if seen in ("streaming", "social", "adult", "gaming"):
        rules = db.get_rules(c)
        if rules:
            verdict = await classifier.evaluate_rules(
                api_key, "", report.domain, report.title or "", rules)
            return {"verdict": verdict, "category": seen}
    return {"verdict": "allow"}


@app.post("/rules")
async def create_rule(rule: RuleCreate):
    """Create a new rule from natural language."""
    c = get_conn()
    api_key = db.get_config(c, "gemini_api_key")
    parsed = {}
    if api_key:
        parsed = await classifier.parse_rule(api_key, rule.text)
    rule_id = db.add_rule(c, rule.text, parsed)
    return {"id": rule_id, "text": rule.text, "parsed": parsed}


@app.get("/rules")
def list_rules():
    return db.get_rules(get_conn(), active_only=False)


@app.delete("/rules/{rule_id}")
def remove_rule(rule_id: int):
    db.delete_rule(get_conn(), rule_id)
    return {"ok": True}


@app.post("/rules/{rule_id}/toggle")
def toggle_rule(rule_id: int):
    db.toggle_rule(get_conn(), rule_id)
    return {"ok": True}


@app.get("/status")
def status():
    c = get_conn()
    return {
        "current_activity": monitor.get_current(),
        "active_rules": db.get_rules(c),
        "blocked": blocker.get_blocked(),
    }


@app.get("/stats")
def stats():
    c = get_conn()
    activities = db.get_activities(c, limit=500)
    blocked = sum(1 for a in activities if a.get("verdict") == "block")
    return {"total_activities": len(activities), "blocked_count": blocked}


@app.post("/config")
def set_config(cfg: ConfigSet):
    db.set_config(get_conn(), cfg.key, cfg.value)
    return {"ok": True}


@app.get("/config/{key}")
def get_config(key: str):
    return {"value": db.get_config(get_conn(), key)}


@app.post("/block/domain/{domain}")
def manual_block_domain(domain: str):
    blocker.block_domain(domain)
    return {"ok": True}


@app.delete("/block/domain/{domain}")
def manual_unblock_domain(domain: str):
    blocker.unblock_domain(domain)
    return {"ok": True}
