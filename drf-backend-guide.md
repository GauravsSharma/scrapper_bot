# 🚀 Job Digest SaaS: Complete Django REST Framework (DRF) Backend Guide

This guide details the complete backend architecture for the multi-user Job Digest platform built with **Python, Django, and Django REST Framework (DRF)** with PostgreSQL.

---

## 1. Tech Stack & Dependencies

- **Framework**: Django 5.x + Django REST Framework (DRF)
- **Database**: PostgreSQL (via Supabase, Neon, or local PostgreSQL)
- **Authentication**: `djangorestframework-simplejwt` (JWT Auth)
- **Task Scheduling**: Celery + Redis OR Django Management Commands (`python manage.py run_daily_digest` via Cron)
- **File Storage**: `django-storages` with AWS S3 or Supabase S3-compatible storage (for Resumes)
- **Telegram Bot API**: `requests` / `python-telegram-bot`

### `requirements.txt`

```txt
django>=5.0
djangorestframework>=3.15
djangorestframework-simplejwt>=5.3
django-cors-headers>=4.3
psycopg2-binary>=2.9
requests>=2.31
python-dotenv>=1.0
django-storages>=1.14
boto3>=1.34
celery>=5.3
redis>=5.0
```

---

## 2. Django Project Structure

```
backend/
├── manage.py
├── core/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── users/
│   │   ├── models.py          # Custom User model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   ├── preferences/
│   │   ├── models.py          # Preference model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   └── jobs/
│       ├── models.py          # SeenJob, DigestLog models
│       ├── services/
│       │   ├── scraper.py     # Fetches jobs from Greenhouse, Lever, Remotive, etc.
│       │   ├── matcher.py     # Role and Location regex matching logic
│       │   └── dispatcher.py  # Multi-user dispatch loop
│       ├── management/
│       │   └── commands/
│       │       └── run_daily_digest.py # Command to run the daily job loop
│       ├── views.py           # Telegram webhook view
│       └── urls.py
├── .env
├── requirements.txt
└── Dockerfile
```

---

## 3. Database Models (`apps/*/models.py`)

### A. Custom User Model (`apps/users/models.py`)

```python
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    telegram_chat_id = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    telegram_active = models.BooleanField(default=True)
    resume = models.FileField(upload_to="resumes/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return f"{self.email} ({self.get_full_name() or self.username})"
```

---

### B. User Preferences Model (`apps/preferences/models.py`)

```python
from django.db import models
from django.conf import settings


class Preference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preference")
    keywords = models.JSONField(default=list, help_text="e.g. ['node', 'react', 'next', 'backend', 'full stack']")
    target_cities = models.JSONField(default=list, help_text="e.g. ['noida', 'gurgaon', 'delhi', 'agra']")
    allow_remote = models.BooleanField(default=True)
    prioritize_remote = models.BooleanField(default=True)
    exclude_senior = models.BooleanField(default=True)
    max_jobs_daily = models.PositiveIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user.email}"
```

---

### C. Seen Jobs & Logs (`apps/jobs/models.py`)

```python
from django.db import models
from django.conf import settings


class SeenJob(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seen_jobs")
    job_url = models.URLField(max_length=1000, db_index=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "job_url")
        indexes = [
            models.Index(fields=["user", "job_url"]),
        ]

    def __str__(self):
        return f"{self.user.email} -> {self.job_url}"


class DigestLog(models.Model):
    STATUS_CHOICES = [
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("NO_JOBS", "No Jobs Found"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="digest_logs")
    jobs_sent = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="SUCCESS")
    error_msg = models.TextField(null=True, blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log: {self.user.email} - {self.status} ({self.jobs_sent} jobs)"
```

---

## 4. Telegram Bot Service (Copy-Paste Chat ID)

When a user messages `/start` to `@job_scrapper_99_bot`, the bot returns their **Chat ID** so they can copy-paste it into the dashboard.

### Telegram Webhook View (`apps/jobs/views.py`)

```python
import os
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


class TelegramWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        update = request.data
        message = update.get("message")
        if not message or "text" not in message:
            return Response({"ok": True})

        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()

        if text.startswith("/start") or text.startswith("/id"):
            reply = (
                f"👋 *Welcome to Job Digest!*\n\n"
                f"Here is your Telegram Chat ID:\n"
                f"`{chat_id}`\n\n"
                f"📋 *Next Steps:*\n"
                f"1. Tap the ID above to copy it.\n"
                f"2. Go to your Dashboard settings.\n"
                f"3. Paste it in the *Telegram Chat ID* field and save.\n\n"
                f"You will receive your personalized job digest every morning at 09:00 AM IST!"
            )
            requests.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"},
                timeout=10,
            )

        return Response({"ok": True})
```

---

## 5. DRF Serializers & API Views

### A. Telegram Chat ID Linking (`apps/users/views.py`)

```python
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import requests, os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


class UpdateTelegramChatView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        chat_id = request.data.get("telegram_chat_id", "").strip()
        if not chat_id:
            return Response({"error": "telegram_chat_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Optional: Send a test confirmation message via Telegram
        test_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            r = requests.post(
                test_url,
                json={"chat_id": chat_id, "text": "✅ Your Telegram is successfully connected to your Job Digest account!"},
                timeout=10
            )
            if not r.ok:
                return Response({"error": "Invalid Chat ID or bot was not started by this user."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Failed to reach Telegram API: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Save to user model
        user = request.user
        user.telegram_chat_id = chat_id
        user.telegram_active = True
        user.save(update_fields=["telegram_chat_id", "telegram_active"])

        return Response({"message": "Telegram Chat ID updated and verified successfully!"})
```

---

### B. User Preferences View (`apps/preferences/views.py`)

```python
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Preference
from .serializers import PreferenceSerializer


class UserPreferenceView(generics.RetrieveUpdateAPIView):
    serializer_class = PreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        preference, _ = Preference.objects.get_or_create(
            user=self.request.user,
            defaults={
                "keywords": ["node", "react", "next", "full stack", "backend", "ai engineer"],
                "target_cities": ["noida", "gurgaon", "delhi", "agra"],
                "allow_remote": True,
                "prioritize_remote": True,
                "exclude_senior": True,
                "max_jobs_daily": 10,
            }
        )
        return preference
```

---

### C. Resume PDF Upload View (`apps/users/views.py`)

```python
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class ResumeUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get("resume")
        if not file_obj:
            return Response({"error": "No file uploaded"}, status=400)

        if not file_obj.name.lower().endswith(".pdf"):
            return Response({"error": "Only PDF files are supported"}, status=400)

        user = request.user
        user.resume = file_obj
        user.save(update_fields=["resume"])

        return Response({
            "message": "Resume uploaded successfully!",
            "resume_url": user.resume.url
        })
```

---

## 6. Multi-User Job Dispatcher Service

### Matcher Service (`apps/jobs/services/matcher.py`)

```python
import re

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

TECH_KEYWORDS = [
    r"\bsoftware\b", r"\bdeveloper\b", r"\bengineer\b", r"\bsde\b",
    r"\bweb\b", r"\bfrontend\b", r"\bbackend\b", r"\bfullstack\b",
    r"\bprogramming\b", r"\btechnology\b", r"\btech\b", r"\bit\b"
]

JUNIOR_INTERN = [
    r"\bintern(ship)?\b", r"\bfresher\b", r"\bjunior\b", r"\btrainee\b",
    r"\bentry[- ]level\b", r"\bsde[- ]?(1|i)\b", r"\bgraduate\b", r"\bassociate\b"
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


def match_role(title, keywords, exclude_senior=True):
    t = title.lower()
    if exclude_senior and any(re.search(b, t) for b in BLOCK_TITLE):
        return False

    kw_patterns = build_keyword_regexes(keywords)
    if any(re.search(k, t) for k in kw_patterns):
        return True

    if any(re.search(j, t) for j in JUNIOR_INTERN) and any(re.search(tk, t) for tk in TECH_KEYWORDS):
        return True

    return False


def match_location(loc_str, target_cities, allow_remote=True):
    l = loc_str.lower()
    has_blocked_geo = any(re.search(bg, l) for bg in BLOCKED_GEO)
    has_override = any(re.search(ok, l) for ok in OVERRIDE_GEO)
    if has_blocked_geo and not has_override:
        return False

    if allow_remote and is_remote(loc_str):
        return True

    city_patterns = [r"\b" + re.escape(c.lower().strip()) + r"\b" for c in target_cities if c.strip()]
    return any(re.search(cp, l) for cp in city_patterns)
```

---

### Scraper Service (`apps/jobs/services/scraper.py`)

Fetches from Greenhouse (`canonical`, `vercel`, `groww`, `inmobi`, `slice`), Lever (`paytm`, `cred`), Remotive, Arbeitnow, Jobicy, and RemoteOK. Returns unified list of `{"title", "company", "location", "url"}`.

---

### Dispatcher Service (`apps/jobs/services/dispatcher.py`)

```python
import os
import time
import requests
from django.contrib.auth import get_user_model
from apps.jobs.models import SeenJob, DigestLog
from .scraper import fetch_all_jobs
from .matcher import match_role, match_location, is_remote

User = get_user_model()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def send_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    return requests.post(
        url,
        json={"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True},
        timeout=15
    )


def format_digest(jobs, user_name, cities):
    remote = [j for j in jobs if is_remote(j["location"])]
    onsite = [j for j in jobs if not is_remote(j["location"])]

    lines = [f"🎯 *Job Digest for {user_name}* ({len(jobs)} new matches)\n"]

    if remote:
        lines.append("🌐 *REMOTE OPPORTUNITIES (Priority 1):*")
        for j in remote:
            lines.append(f"• *{j['title']}* @ {j['company']}\n  📍 {j['location']}\n  🔗 {j['url']}\n")

    if onsite:
        cities_str = " / ".join(c.upper() for c in cities)
        lines.append(f"📍 *ON-SITE / HYBRID ({cities_str}) (Priority 2):*")
        for j in onsite:
            lines.append(f"• *{j['title']}* @ {j['company']}\n  📍 {j['location']}\n  🔗 {j['url']}\n")

    return "\n".join(lines).strip()


def run_daily_job_dispatch():
    print("[CRON] Starting daily job dispatch cycle...")

    # 1. Fetch raw jobs ONCE for all users
    all_jobs = fetch_all_jobs()
    print(f"[CRON] Fetched {len(all_jobs)} jobs from public APIs.")

    # 2. Get active subscribers
    users = User.objects.filter(is_active=True, telegram_active=True, telegram_chat_id__isnull=False).select_related("preference")
    print(f"[CRON] Found {users.count()} active subscribers.")

    for user in users:
        chat_id = user.telegram_chat_id
        pref = getattr(user, "preference", None)
        
        keywords = pref.keywords if pref else ["node", "react", "next", "full stack", "backend"]
        cities = pref.target_cities if pref else ["noida", "gurgaon", "delhi", "agra"]
        allow_remote = pref.allow_remote if pref else True
        prioritize_remote = pref.prioritize_remote if pref else True
        exclude_senior = pref.exclude_senior if pref else True
        max_jobs = pref.max_jobs_daily if pref else 10

        try:
            seen_urls = set(SeenJob.objects.filter(user=user).values_list("job_url", flat=True))

            matched = []
            for j in all_jobs:
                if j["url"] and j["url"] not in seen_urls:
                    if match_role(j["title"], keywords, exclude_senior) and match_location(j["location"], cities, allow_remote):
                        matched.append(j)

            if prioritize_remote:
                matched.sort(key=lambda j: 0 if is_remote(j["location"]) else 1)

            top_jobs = matched[:max_jobs]

            if top_jobs:
                msg = format_digest(top_jobs, user.first_name or user.username, cities)
                r = send_telegram(chat_id, msg)
                
                if r.ok:
                    SeenJob.objects.bulk_create([
                        SeenJob(user=user, job_url=j["url"]) for j in top_jobs
                    ], ignore_conflicts=True)

                    DigestLog.objects.create(user=user, jobs_sent=len(top_jobs), status="SUCCESS")
                else:
                    if r.status_code == 403:  # User blocked the bot
                        user.telegram_active = False
                        user.save(update_fields=["telegram_active"])
                    DigestLog.objects.create(user=user, jobs_sent=0, status="FAILED", error_msg=r.text)
            else:
                DigestLog.objects.create(user=user, jobs_sent=0, status="NO_JOBS")

            time.sleep(0.06)  # Telegram rate limit safety
        except Exception as e:
            DigestLog.objects.create(user=user, jobs_sent=0, status="FAILED", error_msg=str(e))

    print("[CRON] Dispatch cycle completed.")
```

---

## 7. Django Management Command

Run the dispatch loop anytime via CLI or Cron:

File: `apps/jobs/management/commands/run_daily_digest.py`

```python
from django.core.management.base import BaseCommand
from apps.jobs.services.dispatcher import run_daily_job_dispatch


class Command(BaseCommand):
    help = "Fetches jobs and sends personalized daily digests to all active Telegram users"

    def handle(self, *args, **options):
        self.stdout.write("Executing run_daily_digest command...")
        run_daily_job_dispatch()
        self.stdout.write(self.style.SUCCESS("Daily digest successfully completed!"))
```

### To run:
```bash
python manage.py run_daily_digest
```

---

## 8. Built-in Django Admin (`apps/*/admin.py`)

You can view, search, and manage all users, preferences, and delivery logs out-of-the-box:

```python
from django.contrib import admin
from apps.users.models import User
from apps.preferences.models import Preference
from apps.jobs.models import SeenJob, DigestLog

admin.site.register(User)
admin.site.register(Preference)
admin.site.register(SeenJob)
admin.site.register(DigestLog)
```

---

## 9. URL Routing Configuration (`core/urls.py`)

```python
from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.users.views import UpdateTelegramChatView, ResumeUploadView
from apps.preferences.views import UserPreferenceView
from apps.jobs.views import TelegramWebhookView

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Auth
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # User & Preferences
    path("api/user/telegram-chat/", UpdateTelegramChatView.as_view(), name="update_telegram_chat"),
    path("api/user/preferences/", UserPreferenceView.as_view(), name="user_preferences"),
    path("api/user/resume/", ResumeUploadView.as_view(), name="upload_resume"),

    # Telegram Webhook
    path("api/telegram/webhook/", TelegramWebhookView.as_view(), name="telegram_webhook"),
]
```
