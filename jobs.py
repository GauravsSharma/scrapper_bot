# jobs.py
import json
import os
import re
import requests

# Load .env file if present (for local runs)
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if v and k not in os.environ:
                    os.environ[k] = v

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JobDigestBot/1.0)"}

DEFAULT_CONFIG = {
    "user_name": "Developer",
    "keywords": [
        "node", "react", "next", "full stack", "backend", "frontend",
        "ai engineer", "llm", "genai"
    ],
    "target_cities": [
        "noida", "gurgaon", "gurugram", "delhi", "new delhi", "ncr", "agra"
    ],
    "allow_remote": True,
    "prioritize_remote": True,
    "exclude_senior": True,
    "max_jobs": 10
}


def load_config():
    config = dict(DEFAULT_CONFIG)
    if os.path.exists("config.json"):
        try:
            with open("config.json") as f:
                user_cfg = json.load(f)
                config.update(user_cfg)
        except Exception as e:
            print(f"Warning: could not parse config.json ({e}), using defaults")
    return config


CONFIG = load_config()
MAX_JOBS = CONFIG.get("max_jobs", 10)

# Verified Greenhouse and Lever boards
GREENHOUSE = ["canonical", "vercel", "groww", "inmobi", "slice"]
LEVER = ["paytm", "cred"]

TECH_KEYWORDS = [
    r"\bsoftware\b", r"\bdeveloper\b", r"\bengineer\b", r"\bsde\b",
    r"\bweb\b", r"\bfrontend\b", r"\bbackend\b", r"\bfullstack\b",
    r"\bprogramming\b", r"\btechnology\b", r"\btech\b", r"\bit\b"
]

JUNIOR_INTERN = [
    r"\bintern(ship)?\b", r"\bfresher\b", r"\bjunior\b", r"\btrainee\b",
    r"\bentry[- ]level\b", r"\bsde[- ]?(1|i)\b", r"\bgraduate\b", r"\bassociate\b"
]

BLOCK_TITLE = [
    r"\bsenior\b", r"\bstaff\b", r"\bprincipal\b", r"\bmanager\b", r"\barchitect\b",
    r"\bsr\.?\b", r"\blead\b", r"\bdirector\b", r"\bhead of\b", r"\bvp\b",
    r"\bchief\b", r"\brecruiter\b", r"\btalent acquisition\b", r"\bsales\b",
    r"\bmarketing\b", r"\bdesigner\b", r"\bcontent\b", r"\bhr\b", r"\bfinance\b",
    r"\btax\b", r"\blegal\b", r"\boperations\b", r"\bproduct manager\b",
    r"\banalyst\b", r"\baccount executive\b", r"\bpayroll\b"
]

BLOCKED_GEO = [
    r"\bus only\b", r"\busa only\b", r"\bunited states\b", r"\busa\b", r"\bus\b",
    r"\bcanada\b", r"\beurope only\b", r"\buk only\b", r"\buk\b", r"\bgermany\b",
    r"\bpoland\b", r"\blatin america\b", r"\blatam\b", r"\bbrazil\b", r"\baustralia\b",
    r"\bamericas\b"
]

OVERRIDE_GEO = [
    r"\bindia\b", r"\bworldwide\b", r"\bglobal\b", r"\banywhere\b", r"\bapac\b"
]

REMOTE_REGEX = [
    r"\bremote\b", r"\bworldwide\b", r"\banywhere\b",
    r"\bwfh\b", r"\bwork from home\b", r"\bhome based\b"
]


def build_keyword_regexes(keywords):
    regexes = []
    for k in keywords:
        k = k.lower().strip()
        if not k:
            continue
        if k in ("node", "node.js"):
            regexes.append(r"\bnode(\.js)?\b")
        elif k in ("react", "react.js"):
            regexes.append(r"\breact(\.js)?\b")
        elif k in ("next", "next.js"):
            regexes.append(r"\bnext(\.js)?\b")
        elif "full" in k and "stack" in k:
            regexes.append(r"\bfull[- ]?stack\b")
        elif "back" in k and "end" in k:
            regexes.append(r"\bback[- ]?end\b")
        elif "front" in k and "end" in k:
            regexes.append(r"\bfront[- ]?end\b")
        else:
            regexes.append(r"\b" + re.escape(k) + r"\b")
    return regexes


def is_remote(loc_str):
    return any(re.search(r, loc_str.lower()) for r in REMOTE_REGEX)


def match_role(title, config=None):
    cfg = config or CONFIG
    t = title.lower()

    if cfg.get("exclude_senior", True) and any(re.search(b, t) for b in BLOCK_TITLE):
        return False

    kw_patterns = build_keyword_regexes(cfg.get("keywords", []))
    if any(re.search(k, t) for k in kw_patterns):
        return True

    # Check junior/intern technical role
    if any(re.search(j, t) for j in JUNIOR_INTERN) and any(re.search(tk, t) for tk in TECH_KEYWORDS):
        return True

    return False


def match_location(loc_str, config=None):
    cfg = config or CONFIG
    l = loc_str.lower()

    # Reject geo locked outside India unless worldwide/apac/india
    has_blocked_geo = any(re.search(bg, l) for bg in BLOCKED_GEO)
    has_override = any(re.search(ok, l) for ok in OVERRIDE_GEO)
    if has_blocked_geo and not has_override:
        return False

    # Check remote
    if cfg.get("allow_remote", True) and is_remote(loc_str):
        return True

    # Check target cities
    target_cities = cfg.get("target_cities", [])
    city_patterns = [r"\b" + re.escape(c.lower().strip()) + r"\b" for c in target_cities if c.strip()]
    return any(re.search(cp, l) for cp in city_patterns)


def match(title, location, config=None):
    return match_role(title, config) and match_location(location, config)


def get(url):
    """GET a JSON URL. Return parsed JSON or None on any failure."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("FAIL", url, e)
        return None


def fetch_all():
    """Return a list of (title, company, location, url)."""
    jobs = []

    # 1. Greenhouse company boards
    for token in GREENHOUSE:
        data = get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
        for j in (data or {}).get("jobs", []):
            jobs.append((
                j.get("title", ""),
                token.capitalize(),
                (j.get("location") or {}).get("name", ""),
                j.get("absolute_url", ""),
            ))

    # 2. Lever company boards
    for token in LEVER:
        data = get(f"https://api.lever.co/v0/postings/{token}?mode=json")
        for j in data or []:
            jobs.append((
                j.get("text", ""),
                token.upper(),
                (j.get("categories") or {}).get("location", ""),
                j.get("hostedUrl", ""),
            ))

    # 3. Remotive API
    data = get("https://remotive.com/api/remote-jobs?search=developer")
    for j in (data or {}).get("jobs", []):
        loc = "Remote (" + j.get("candidate_required_location", "") + ")"
        jobs.append((
            j.get("title", ""),
            j.get("company_name", ""),
            loc,
            j.get("url", ""),
        ))

    # 4. Arbeitnow API (Free Public Job Board)
    data = get("https://www.arbeitnow.com/api/job-board-api")
    for j in (data or {}).get("data", []):
        loc = "Remote" if j.get("remote") else j.get("location", "")
        jobs.append((
            j.get("title", ""),
            j.get("company_name", ""),
            loc,
            j.get("url", ""),
        ))

    # 5. Jobicy API (Free Public Remote Job API)
    data = get("https://jobicy.com/api/v2/remote-jobs")
    for j in (data or {}).get("jobs", []):
        loc = "Remote (" + j.get("jobGeo", "") + ")"
        jobs.append((
            j.get("jobTitle", ""),
            j.get("companyName", ""),
            loc,
            j.get("url", ""),
        ))

    # 6. RemoteOK API
    data = get("https://remoteok.com/api")
    for j in (data or [])[1:]:
        jobs.append((
            j.get("position", ""),
            j.get("company", ""),
            "Remote",
            j.get("url", ""),
        ))

    return jobs


def send(text):
    print(text)
    token = os.environ.get("TG_TOKEN")
    chat = os.environ.get("TG_CHAT")
    if not token or not chat:
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True},
            timeout=20,
        )
        if r.ok:
            print("\n[✓] Sent to Telegram successfully!")
        else:
            print(f"\n[!] Telegram error ({r.status_code}): {r.text}")
    except Exception as e:
        print(f"\n[!] Failed to contact Telegram: {e}")


def format_digest(new_jobs, config=None):
    cfg = config or CONFIG
    user_name = cfg.get("user_name", "Developer")

    if not new_jobs:
        return f"No new matching jobs today for {user_name}."

    remote = [j for j in new_jobs if is_remote(j[2])]
    onsite = [j for j in new_jobs if not is_remote(j[2])]

    lines = [f"🎯 Job Digest for {user_name} ({len(new_jobs)} new matches)\n"]

    if remote:
        lines.append("🌐 REMOTE OPPORTUNITIES (Priority 1):")
        for t, c, l, u in remote:
            lines.append(f"• {t} @ {c}\n  📍 {l}\n  🔗 {u}\n")

    if onsite:
        cities_str = " / ".join(c.capitalize() for c in cfg.get("target_cities", []))
        lines.append(f"📍 ON-SITE / HYBRID ({cities_str}) (Priority 2):")
        for t, c, l, u in onsite:
            lines.append(f"• {t} @ {c}\n  📍 {l}\n  🔗 {u}\n")

    return "\n".join(lines).strip()


def main():
    config = load_config()
    max_jobs = config.get("max_jobs", 10)
    seen = set(json.load(open("seen.json"))) if os.path.exists("seen.json") else set()

    new, urls = [], set()
    for title, company, loc, url in fetch_all():
        if url and url not in seen and url not in urls and match(title, loc, config):
            new.append((title, company, loc, url))
            urls.add(url)

    # Sort so Remote roles appear first if prioritize_remote is True
    if config.get("prioritize_remote", True):
        new.sort(key=lambda j: 0 if is_remote(j[2]) else 1)

    new = new[:max_jobs]

    text = format_digest(new, config)
    send(text)

    with open("seen.json", "w") as f:
        json.dump(sorted(seen | {j[3] for j in new}), f)


if __name__ == "__main__":
    main()
