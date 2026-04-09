"""Input validation and sanitization."""
import re

_DOMAIN_RE = re.compile(
    r"^(?!-)([a-z0-9-]{1,63}(?<!-)\.)+[a-z]{2,63}$", re.IGNORECASE)
_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_BUNDLE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*(\.[a-zA-Z0-9][a-zA-Z0-9._-]*)+$")
_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun",
         "monday", "tuesday", "wednesday", "thursday", "friday",
         "saturday", "sunday", "all", "everyday"}


def is_valid_domain(s: str) -> bool:
    if not isinstance(s, str) or not s or len(s) > 253:
        return False
    return bool(_DOMAIN_RE.match(s))


def is_valid_url(s: str) -> bool:
    if not isinstance(s, str) or not s:
        return False
    return bool(_URL_RE.match(s))


def is_valid_time(s: str) -> bool:
    if not isinstance(s, str):
        return False
    return bool(_TIME_RE.match(s))


def is_valid_day(s: str) -> bool:
    if not isinstance(s, str):
        return False
    return s.lower().strip() in _DAYS


def is_valid_bundle_id(s: str) -> bool:
    if not isinstance(s, str) or not s or len(s) > 255:
        return False
    return bool(_BUNDLE_RE.match(s))


def sanitize_rule_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    out = re.sub(r"\s+", " ", s)
    out = re.sub(r"[^\S ]|[\x00-\x08\x0b-\x1f\x7f]", "", out).strip()
    return out[:500]


def sanitize_filename(s: str) -> str:
    if not isinstance(s, str):
        return ""
    out = re.sub(r"[^\w.\-]", "_", s)
    out = re.sub(r"_+", "_", out).strip("_.")
    return out[:255] or "unnamed"


def normalize_domain(s: str) -> str:
    if not isinstance(s, str):
        return ""
    out = s.strip().lower()
    out = re.sub(r"^https?://", "", out)
    out = out.split("/", 1)[0]
    out = out.split(":", 1)[0]
    if out.startswith("www."):
        out = out[4:]
    return out


def validate_rule_dict(d: dict) -> tuple:
    if not isinstance(d, dict):
        return (False, "not a dict")
    if "action" in d and d["action"] not in ("block", "warn", "allow"):
        return (False, "invalid action")
    for k in ("domains", "apps", "categories"):
        if k in d and not isinstance(d[k], list):
            return (False, f"{k} must be a list")
    if "domains" in d:
        for dom in d["domains"]:
            pat = dom.replace("*.", "") if isinstance(dom, str) else ""
            if not is_valid_domain(pat):
                return (False, f"invalid domain: {dom}")
    if "schedule" in d:
        s = d["schedule"]
        if not isinstance(s, dict):
            return (False, "schedule must be a dict")
        if "start" in s and not is_valid_time(s["start"]):
            return (False, "invalid start time")
        if "end" in s and not is_valid_time(s["end"]):
            return (False, "invalid end time")
    if "allowed_minutes" in d:
        v = d["allowed_minutes"]
        if not isinstance(v, int) or v < 0:
            return (False, "allowed_minutes must be non-negative int")
    return (True, "")
