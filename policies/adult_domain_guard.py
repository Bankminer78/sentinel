"""
Recurring policy: checks the current foreground browser domain,
classifies it, and auto-blocks any adult/porn domain with the same
type_text friction lock (250 chars ≈ a paragraph).
"""
from sentinel import db, monitor, classifier, blocker, locks, audit

conn = db.connect()
api_key = db.get_config(conn, "gemini_api_key")

current = monitor.get_current()
domain = getattr(current, "domain", None) or (current or {}).get("domain")

if not domain:
    exit()

# Skip if already blocked
if blocker.is_blocked_domain(domain):
    exit()

# Classify via Gemini
category = classifier.classify_domain(api_key, domain)

if category == "adult":
    blocker.block_domain(domain)
    locks.create(
        conn,
        name=f"auto_porn_block_{domain.replace('.', '_')}",
        kind="no_unblock_domain",
        target=domain,
        duration_seconds=365 * 24 * 3600,
        friction={"type": "type_text", "chars": 250},
        actor="policy:adult_domain_guard",
    )
    audit.log(
        conn,
        "policy:adult_domain_guard",
        "block_domain",
        {"domain": domain, "category": category},
        status="ok",
    )
