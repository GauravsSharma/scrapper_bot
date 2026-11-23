# Job Digest Bot: Build Guide for an AI Agent

## 0. Goal

Build a small, free tool that runs once a day and sends the user a Telegram message with up to 10 **new** job postings that match their profile. The user applies manually. This tool **never applies to jobs automatically**.

### User profile (used for filtering)

- Fresher full-stack / backend developer (Node.js, React, microservices, AI/LLM integrations)
- Target roles: Node.js developer, React developer, full-stack, backend, AI / LLM application engineer
- Target locations: Noida, Gurgaon/Gurugram, Delhi, India, Remote
- Exclude senior-level roles

### Hard constraints

1. Everything must be free: Python, public APIs, GitHub Actions free tier, Telegram Bot API.
2. **Do not scrape** LinkedIn, Naukri, Indeed or any site whose terms forbid it. Use only the public JSON APIs listed below.
3. Never hardcode secrets. Read `TG_TOKEN` and `TG_CHAT` from environment variables.
4. A failure in one source must not stop the others.
5. Do not invent company tokens. Leave `GREENHOUSE` and `LEVER` empty unless the user supplies verified tokens (see Step 7).

### Division of work

| Task | Who |
|---|---|
| Create files, write code, run local tests | AI agent |
| Create Telegram bot via @BotFather, get token and chat id | **Human** |
| Create GitHub repo, add secrets | **Human** (agent can give exact click-paths) |
| Find and verify company board tokens | Human + agent |

---

## 1. Project structure

Create exactly this layout:

```
job-digest/
├── jobs.py
├── requirements.txt
├── seen.json
├── test_match.py
├── .gitignore
└── .github/
    └── workflows/
        └── daily.yml
```

---

## 2. Create `requirements.txt`

```
requests>=2.31
```

## 3. Create `seen.json`

Content must be exactly:

```json
[]
```

## 4. Create `.gitignore`

```
__pycache__/
*.pyc
.env
.venv/
```

Do **not** ignore `seen.json`. The workflow commits it to remember which jobs were already sent.

## 5. Create `jobs.py`

```python
# jobs.py
import json
import os
import requests

KEYWORDS = ["node", "react", "full stack", "fullstack", "full-stack",
            "backend", "back end", "ai engineer", "llm"]
BLOCK = ["senior", "staff", "principal", "manager", "architect", "sr.", "lead "]
LOCATIONS = ["india", "noida", "gurgaon", "gurugram", "delhi", "remote"]

# Verified board tokens only. Leave empty until the human provides them.
GREENHOUSE = []   # e.g. "acme"  -> boards.greenhouse.io/acme
LEVER = []        # e.g. "acme"  -> jobs.lever.co/acme

HEADERS = {"User-Agent": "Mozilla/5.0 job-digest"}
MAX_JOBS = 10


def get(url):
    """GET a JSON URL. Return parsed JSON or None on any failure."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("FAIL", url, e)
        return None


def fetch_all():
    """Return a list of (title, company, location, url)."""
    jobs = []

    for token in GREENHOUSE:
        data = get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
        for j in (data or {}).get("jobs", []):
            jobs.append((
                j.get("title", ""),
                token,
                (j.get("location") or {}).get("name", ""),
                j.get("absolute_url", ""),
            ))

    for token in LEVER:
        data = get(f"https://api.lever.co/v0/postings/{token}?mode=json")
        for j in data or []:
            jobs.append((
                j.get("text", ""),
                token,
                (j.get("categories") or {}).get("location", ""),
                j.get("hostedUrl", ""),
            ))

    # RemoteOK: first element of the array is a legal notice, skip it.
    data = get("https://remoteok.com/api")
    for j in (data or [])[1:]:
        jobs.append((
            j.get("position", ""),
            j.get("company", ""),
            "Remote",
            j.get("url", ""),
        ))

    data = get("https://remotive.com/api/remote-jobs?search=developer")
    for j in (data or {}).get("jobs", []):
        loc = "Remote (" + j.get("candidate_required_location", "") + ")"
        jobs.append((
            j.get("title", ""),
            j.get("company_name", ""),
            loc,
            j.get("url", ""),
        ))

    return jobs


def match(title, location):
    t, l = title.lower(), location.lower()
    return (
        any(k in t for k in KEYWORDS)
        and not any(b in t for b in BLOCK)
        and any(x in l for x in LOCATIONS)
    )


def send(text):
    token = os.environ.get("TG_TOKEN")
    chat = os.environ.get("TG_CHAT")
    if not token or not chat:
        print(text)  # local run without Telegram: just print
        return
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": text[:4000]},  # Telegram limit is 4096
        timeout=20,
    )


def main():
    seen = set(json.load(open("seen.json"))) if os.path.exists("seen.json") else set()

    new, urls = [], set()
    for title, company, loc, url in fetch_all():
        if url and url not in seen and url not in urls and match(title, loc):
            new.append((title, company, loc, url))
            urls.add(url)
    new = new[:MAX_JOBS]  # jobs beyond the cap are NOT marked seen, so they return tomorrow

    if new:
        text = "\n\n".join(f"{t} @ {c} ({l})\n{u}" for t, c, l, u in new)
    else:
        text = "No new jobs today"
    send(text)

    with open("seen.json", "w") as f:
        json.dump(sorted(seen | {j[3] for j in new}), f)


if __name__ == "__main__":
    main()
```

## 6. Create `test_match.py`

```python
# test_match.py  (run: python test_match.py)
from jobs import match

assert match("Node.js Developer", "Remote")
assert match("Full Stack Engineer", "Noida, India")
assert match("AI Engineer", "Remote (Worldwide)")
assert not match("Senior Node.js Developer", "Remote")
assert not match("Tech Lead - Backend", "Remote")
assert not match("Sales Manager", "Remote")
assert not match("React Developer", "San Francisco, USA")
print("All match() tests passed")
```

**Run it now.** If an assertion fails, fix `KEYWORDS`, `BLOCK` or `LOCATIONS` in `jobs.py`, not the test, unless the test itself is wrong.

## 7. Verify locally (agent)

```bash
pip install -r requirements.txt
python test_match.py
python jobs.py
```

Expected: tests pass; `jobs.py` prints up to 10 jobs (or `No new jobs today`) and rewrites `seen.json`.

If `FAIL <url>` lines appear for RemoteOK or Remotive, that is a network or API issue. Report it to the user rather than silently removing the source.

After the verification run, **reset `seen.json` to `[]`** so the user's first real run is not empty.

---

## 8. Human step: Telegram bot (agent gives instructions, human does them)

1. In Telegram, open **@BotFather**, send `/newbot`, choose a name and username, and copy the **token**.
2. Open the new bot and send it any message, for example `hi`.
3. In a browser, open `https://api.telegram.org/bot<TOKEN>/getUpdates` (replace `<TOKEN>`).
4. In the JSON, find `result[0].message.chat.id`. That number is the **chat id**.

Local test with Telegram:

```bash
export TG_TOKEN="<token>"
export TG_CHAT="<chat id>"
python jobs.py
```

The message should arrive in Telegram. Never commit the token.

## 9. Create `.github/workflows/daily.yml`

```yaml
name: daily-jobs

on:
  schedule:
    - cron: "30 3 * * *"   # 03:30 UTC = 09:00 IST
  workflow_dispatch:        # enables the manual "Run workflow" button

permissions:
  contents: write           # required so the bot can push seen.json

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - run: pip install -r requirements.txt

      - run: python jobs.py
        env:
          TG_TOKEN: ${{ secrets.TG_TOKEN }}
          TG_CHAT: ${{ secrets.TG_CHAT }}

      - name: Save seen.json
        run: |
          git config user.name "job-digest-bot"
          git config user.email "bot@users.noreply.github.com"
          git add seen.json
          git diff --staged --quiet || (git commit -m "update seen" && git push)
```

## 10. Human step: GitHub

1. Create a **private** GitHub repo and push the `job-digest/` contents.
2. Repo **Settings → Secrets and variables → Actions → New repository secret**. Add `TG_TOKEN` and `TG_CHAT`.
3. Repo **Actions** tab → **daily-jobs** → **Run workflow**. Confirm the Telegram message arrives and a `update seen` commit appears.

## 11. Add company boards (optional, improves results)

For each target company:

1. Open its careers page. If the URL looks like `boards.greenhouse.io/<token>` or `jobs.lever.co/<token>`, that `<token>` is the board token.
2. **Verify** by opening one of these in a browser:
   - `https://boards-api.greenhouse.io/v1/boards/<token>/jobs`
   - `https://api.lever.co/v0/postings/<token>?mode=json`
3. If JSON is returned, add the token to `GREENHOUSE` or `LEVER` in `jobs.py`. If you get a 404, the token is wrong, so do not add it.

---

## 12. Acceptance criteria

- [ ] `python test_match.py` passes
- [ ] `python jobs.py` runs without a crash even if one source fails
- [ ] No secrets in the repo (`git grep -i token` shows only `os.environ` usage and docs)
- [ ] The workflow run succeeds and sends a Telegram message
- [ ] A second run the same day does **not** resend the same jobs
- [ ] The `seen.json` commit appears after each run that finds new jobs

## 13. Known limitations (tell the user honestly)

- Covers mostly startups, product companies and remote jobs. It does **not** cover Naukri, LinkedIn or Indeed, so the user should keep saved search alerts there for India on-site roles.
- Many Remotive and RemoteOK jobs are restricted to the US or EU. The location is shown in each message so the user can check before applying.
- Matching is based on substrings in the job title only, so tune `KEYWORDS` and `BLOCK` after 2-3 days of real results.
- GitHub scheduled runs can be 10-30 minutes late. GitHub also pauses schedules after 60 days of repo inactivity; the bot's `seen.json` commits normally prevent this, but if it happens, re-enable the workflow in the Actions tab.

## 14. Optional next steps (only if the user asks)

- Add an LLM-based match score (resume vs. job description) using a free-tier API.
- Add more sources that have public APIs.
- Pair with the user's Chrome autofill extension: the digest finds the jobs, the extension fills the forms, and the user submits manually.
