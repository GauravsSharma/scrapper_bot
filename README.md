# 🤖 Personal Job Digest Bot

An automated, free daily job digest bot built with Python and GitHub Actions. It finds fresh, high-quality, verified tech jobs matching your profile and delivers them directly to your Telegram every morning at 09:00 IST (03:30 UTC).

---

## 🚀 How to Set Up Your Own Bot (3 Steps)

You can fork this repository to get your own personalized job alerts delivered daily for free.

### Step 1: Fork this Repository
Click the **Fork** button at the top-right of this repository to create your own copy.

---

### Step 2: Create Your Telegram Bot
1. Open Telegram and search for **[@BotFather](https://t.me/BotFather)**.
2. Send `/newbot`, choose a name and username, and copy your **Bot Token**.
3. Open your new bot in Telegram and send it any message (e.g. `hi`).
4. In your browser, open `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates` to get your **Chat ID** (look for `"chat":{"id":123456789}`).

---

### Step 3: Add Secrets & Personalize

#### A. Add Secrets to your Forked Repo:
1. Go to your forked repo on GitHub → **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret** and add:
   - `TG_TOKEN`: Your Telegram Bot Token from Step 2.
   - `TG_CHAT`: Your Telegram Chat ID from Step 2.
3. In repo **Settings** → **Actions** → **General** → scroll down to **Workflow permissions** → select **Read and write permissions** → click **Save**.

#### B. Personalize Your Preferences in `config.json`:
Click on [`config.json`](config.json) in your repository and edit it directly in GitHub with the pencil ✏️ icon:

```json
{
  "user_name": "YourName",
  "keywords": [
    "node",
    "react",
    "next",
    "full stack",
    "backend",
    "python",
    "ai engineer"
  ],
  "target_cities": [
    "noida",
    "gurgaon",
    "delhi",
    "bangalore",
    "pune"
  ],
  "allow_remote": true,
  "prioritize_remote": true,
  "exclude_senior": true,
  "max_jobs": 10
}
```

---

### Step 4: Test & Automation

1. Go to the **Actions** tab in your repository.
2. Click **daily-jobs** on the left menu → click **Run workflow**.
3. You will receive your personalized job digest on Telegram within 30 seconds!
4. From now on, GitHub Actions will automatically run every morning at **09:00 AM IST (03:30 UTC)**.

---

## 🛠 Features
- **Zero Cost**: 100% free using GitHub Actions and Telegram Bot API.
- **High-Quality Sources**: Scrapes verified public APIs (Greenhouse, Lever, Remotive, Arbeitnow, Jobicy, RemoteOK).
- **Smart Filtering**: Blocks senior/lead titles and filters out non-tech internships (tax, HR, sales).
- **Geo-Fencing**: Discards foreign-locked listings (US/UK/EU only) that do not hire in India/Worldwide.
- **Duplicate Prevention**: Remembers previously sent jobs using `seen.json`.
