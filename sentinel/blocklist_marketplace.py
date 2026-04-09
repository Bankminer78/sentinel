"""Blocklist marketplace — curated public blocklists users can subscribe to."""
import time


PUBLIC_BLOCKLISTS = {
    "streaming_mega": {
        "name": "Streaming Mega List",
        "description": "500+ streaming/piracy sites",
        "category": "streaming",
        "domains": ["netflix.com", "twitch.tv", "fmovies.co", "braflix.tube",
                    "123movies.com", "hulu.com", "disneyplus.com"],
    },
    "social_detox": {
        "name": "Social Detox",
        "description": "Major social media platforms",
        "category": "social",
        "domains": ["twitter.com", "x.com", "instagram.com", "facebook.com",
                    "tiktok.com", "reddit.com", "snapchat.com"],
    },
    "adult_shield": {
        "name": "Adult Content Shield",
        "description": "Comprehensive adult content blocklist",
        "category": "adult",
        "domains": ["pornhub.com", "xvideos.com", "xnxx.com", "onlyfans.com"],
    },
    "gaming_no": {
        "name": "No Gaming",
        "description": "Online games and gaming platforms",
        "category": "gaming",
        "domains": ["steam.com", "epicgames.com", "roblox.com", "fortnite.com"],
    },
    "shopping_stop": {
        "name": "Stop Shopping",
        "description": "E-commerce impulse buying",
        "category": "shopping",
        "domains": ["amazon.com", "ebay.com", "etsy.com", "aliexpress.com"],
    },
    "news_fast": {
        "name": "News Fast",
        "description": "Major news sites for a news fast",
        "category": "news",
        "domains": ["cnn.com", "foxnews.com", "nytimes.com", "bbc.com",
                    "news.google.com", "theverge.com"],
    },
    "ai_procrastination": {
        "name": "AI Procrastination",
        "description": "Block AI tools that become procrastination",
        "category": "ai",
        "domains": ["chatgpt.com", "claude.ai", "midjourney.com"],
    },
}


def list_available() -> list:
    return [{"id": k, **{k2: v2 for k2, v2 in v.items() if k2 != "domains"}}
            for k, v in PUBLIC_BLOCKLISTS.items()]


def get_blocklist(blocklist_id: str) -> dict:
    return PUBLIC_BLOCKLISTS.get(blocklist_id)


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS blocklist_subscriptions (
        blocklist_id TEXT PRIMARY KEY, subscribed_at REAL
    )""")


def subscribe(conn, blocklist_id: str) -> int:
    _ensure_table(conn)
    if blocklist_id not in PUBLIC_BLOCKLISTS:
        return 0
    conn.execute(
        "INSERT OR REPLACE INTO blocklist_subscriptions (blocklist_id, subscribed_at) VALUES (?, ?)",
        (blocklist_id, time.time()))
    # Apply: add domains to seen as the category
    bl = PUBLIC_BLOCKLISTS[blocklist_id]
    from . import db, blocker
    count = 0
    for d in bl["domains"]:
        db.save_seen(conn, d, bl["category"])
        blocker.block_domain(d)
        count += 1
    conn.commit()
    return count


def unsubscribe(conn, blocklist_id: str):
    _ensure_table(conn)
    conn.execute("DELETE FROM blocklist_subscriptions WHERE blocklist_id=?", (blocklist_id,))
    # Remove the domains from the blocker
    bl = PUBLIC_BLOCKLISTS.get(blocklist_id)
    if bl:
        from . import blocker
        for d in bl["domains"]:
            blocker.unblock_domain(d)
    conn.commit()


def get_subscriptions(conn) -> list:
    _ensure_table(conn)
    rows = conn.execute("SELECT * FROM blocklist_subscriptions").fetchall()
    return [{**dict(r), **PUBLIC_BLOCKLISTS.get(r["blocklist_id"], {})} for r in rows]


def is_subscribed(conn, blocklist_id: str) -> bool:
    _ensure_table(conn)
    r = conn.execute(
        "SELECT 1 FROM blocklist_subscriptions WHERE blocklist_id=?", (blocklist_id,)).fetchone()
    return r is not None


def count_available() -> int:
    return len(PUBLIC_BLOCKLISTS)


def search_blocklists(query: str) -> list:
    q = query.lower()
    return [{"id": k, **{k2: v2 for k2, v2 in v.items() if k2 != "domains"}}
            for k, v in PUBLIC_BLOCKLISTS.items()
            if q in v["name"].lower() or q in v["description"].lower()]
