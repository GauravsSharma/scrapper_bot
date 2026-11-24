# Job Digest SaaS: Complete Backend & System Architecture Guide

## 1. System Overview

A multi-user job digest backend that allows users to manage their target job preferences (skills, cities, remote vs on-site) via a web dashboard, links their Telegram account, and runs an automated daily scheduler that fetches jobs from public APIs, filters matches per user, and delivers personalized alerts to their Telegram chats.

---

## 2. Tech Stack

- **Framework**: Next.js 14+ (App Router) or Node.js / Express
- **Database**: PostgreSQL (via Supabase or Neon Serverless)
- **ORM**: Prisma ORM
- **Authentication**: NextAuth.js / Clerk / JWT
- **File Storage**: AWS S3 / Supabase Storage (for resume PDFs)
- **Background Scheduler**: Node-cron / Vercel Cron / GitHub Actions dispatch
- **Messaging**: Telegram Bot API

---

## 3. Database Schema (`schema.prisma`)

```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

model User {
  id              String       @id @default(uuid())
  email           String       @unique
  name            String
  password        String?      // If credentials auth
  telegramChatId  String?      @unique
  telegramToken   String?      // Optional: if user provides their own bot (AES-256 encrypted)
  telegramActive  Boolean      @default(true)
  resumeUrl       String?      // S3 or storage URL
  isActive        Boolean      @default(true)
  createdAt       DateTime     @default(now())
  updatedAt       DateTime     @updatedAt

  preference      Preference?
  seenJobs        SeenJob[]
  digestLogs      DigestLog[]

  @@index([telegramChatId])
}

model Preference {
  id              String       @id @default(uuid())
  userId          String       @unique
  user            User         @relation(fields: [userId], references: [id], onDelete: Cascade)
  keywords        String[]     // e.g. ["node", "react", "next", "backend", "full stack"]
  targetCities    String[]     // e.g. ["noida", "gurgaon", "delhi", "remote"]
  allowRemote     Boolean      @default(true)
  prioritizeRemote Boolean     @default(true)
  excludeSenior   Boolean      @default(true)
  maxJobsDaily    Int          @default(10)
  createdAt       DateTime     @default(now())
  updatedAt       DateTime     @updatedAt
}

model SeenJob {
  id        String   @id @default(uuid())
  userId    String
  user      User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  jobUrl    String
  sentAt    DateTime @default(now())

  @@unique([userId, jobUrl])
  @@index([userId])
}

model DigestLog {
  id          String   @id @default(uuid())
  userId      String
  user        User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  jobsSent    Int
  status      String   // "SUCCESS" | "FAILED" | "NO_JOBS"
  errorMsg    String?
  executedAt  DateTime @default(now())

  @@index([userId])
}
```

---

## 4. Backend Endpoints (API Routes)

### A. Authentication
- `POST /api/auth/register` - Create account (email, password, name)
- `POST /api/auth/login` - Authenticate & return session/JWT

### B. User Profile & Preferences
- `GET /api/user/profile` - Fetch current user, resume status, and preferences
- `PUT /api/user/preferences` - Update keywords, target cities, remote priority, exclude senior toggle
  - Payload:
    ```json
    {
      "keywords": ["node", "react", "next", "full stack", "backend"],
      "targetCities": ["noida", "gurgaon", "delhi", "agra"],
      "allowRemote": true,
      "prioritizeRemote": true,
      "excludeSenior": true,
      "maxJobsDaily": 10
    }
    ```
- `POST /api/user/resume` - Upload resume (multipart/form-data), save to S3/Supabase Storage, store URL in DB.

### C. Telegram Account Linking
Two supported methods:
1. **Method 1 (Recommended - Central Bot)**:
   - User clicks `Connect Telegram` on dashboard.
   - Link opens: `https://t.me/YourOfficialBot?start=<USER_ID>`.
   - Telegram sends webhook event to `POST /api/telegram/webhook`.
   - Backend extracts `/start <userId>`, links `telegramChatId = message.chat.id`, and saves to DB.
   - Bot replies on Telegram: *"✅ Connected successfully to your account, Gaurav!"*

2. **Method 2 (Custom Bot Credentials)**:
   - `PUT /api/user/telegram`
   - User inputs custom `TG_TOKEN` and `TG_CHAT`.
   - Backend encrypts `TG_TOKEN` with AES-256 before saving to DB.

---

## 5. Daily Dispatch Cron Engine (The Core Loop)

Runs every morning (e.g. 09:00 AM IST) via `POST /api/cron/dispatch-jobs` (protected by `CRON_SECRET` header) or a standalone Node.js worker.

```
                  ┌────────────────────────────────────────┐
                  │ 1. Trigger Cron Job (Every Day 09:00)  │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │ 2. Fetch Raw Jobs from All Sources     │
                  │    (Greenhouse, Lever, Remotive, etc.) │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │ 3. Fetch All Active Users from DB      │
                  │    (where telegramChatId != null)      │
                  └───────────────────┬────────────────────┘
                                      │
                      ┌───────────────┴───────────────┐
                      │ Loop Through Each Active User │
                      └───────────────┬───────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │ 4. Filter Jobs by User's Preference    │
                  │    - Keyword match                     │
                  │    - City / Remote match               │
                  │    - Exclude Senior/Lead roles         │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │ 5. Deduplicate Against SeenJob Table   │
                  │    (Exclude URLs already sent to user) │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │ 6. Format & Prioritize Digest          │
                  │    (Remote Priority 1, On-site Pri. 2) │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │ 7. Dispatch via Telegram Bot API       │
                  │    (Respect rate limits: max 25 msg/s) │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │ 8. Record in DB                        │
                  │    - Save sent URLs to SeenJob         │
                  │    - Write log entry to DigestLog      │
                  └────────────────────────────────────────┘
```

---

## 6. Detailed Step-by-Step Dispatch Algorithm

```typescript
import { PrismaClient } from "@prisma/client";
import { fetchAllJobs, matchJob, formatDigestMessage, sendTelegramMessage } from "./jobUtils";

const prisma = new PrismaClient();

export async function runDailyJobDispatch() {
  console.log("Starting daily job dispatch cycle...");

  // 1. Fetch raw jobs once for all users (efficient)
  const allJobs = await fetchAllJobs();
  console.log(`Fetched ${allJobs.length} raw jobs from all sources.`);

  // 2. Fetch all active users who linked Telegram
  const users = await prisma.user.findMany({
    where: {
      isActive: true,
      telegramActive: true,
      telegramChatId: { not: null },
    },
    include: {
      preference: true,
      seenJobs: {
        select: { jobUrl: true },
      },
    },
  });

  console.log(`Found ${users.length} active Telegram subscribers.`);

  // 3. Process each user
  for (const user of users) {
    try {
      const pref = user.preference || {
        keywords: ["node", "react", "next", "full stack", "backend"],
        targetCities: ["noida", "gurgaon", "delhi", "agra"],
        allowRemote: true,
        prioritizeRemote: true,
        excludeSenior: true,
        maxJobsDaily: 10,
      };

      const seenUrls = new Set(user.seenJobs.map((s) => s.jobUrl));

      // Filter jobs matching user's specific preferences
      const matched = allJobs.filter((job) => {
        if (seenUrls.has(job.url)) return false;
        return matchJob(job, pref);
      });

      // Sort: Remote first if prioritizeRemote is true
      if (pref.prioritizeRemote) {
        matched.sort((a, b) => (a.isRemote ? -1 : 1));
      }

      const topJobs = matched.slice(0, pref.maxJobsDaily);

      if (topJobs.length > 0) {
        const message = formatDigestMessage(topJobs, user.name, pref.targetCities);
        
        // Send via central bot or decrypted user token
        await sendTelegramMessage(user.telegramChatId!, message);

        // Record in SeenJob table
        await prisma.seenJob.createMany({
          data: topJobs.map((j) => ({
            userId: user.id,
            jobUrl: j.url,
          })),
          skipDuplicates: true,
        });

        await prisma.digestLog.create({
          data: {
            userId: user.id,
            jobsSent: topJobs.length,
            status: "SUCCESS",
          },
        });
      } else {
        await prisma.digestLog.create({
          data: {
            userId: user.id,
            jobsSent: 0,
            status: "NO_JOBS",
          },
        });
      }

      // Small delay to prevent hitting Telegram rate limits (30 requests/second)
      await new Promise((r) => setTimeout(r, 60));
    } catch (err: any) {
      console.error(`Failed to dispatch for user ${user.id}:`, err);
      
      // If user blocked the bot (Telegram 403 Forbidden)
      if (err?.response?.status === 403) {
        await prisma.user.update({
          where: { id: user.id },
          data: { telegramActive: false },
        });
      }

      await prisma.digestLog.create({
        data: {
          userId: user.id,
          jobsSent: 0,
          status: "FAILED",
          errorMsg: err?.message || String(err),
        },
      });
    }
  }

  console.log("Daily dispatch cycle completed.");
}
```

---

## 7. Security Best Practices

1. **Telegram Token Encryption**:
   - If users supply custom bot tokens, encrypt them before saving:
   - Algorithm: `aes-256-gcm` using a master `ENCRYPTION_KEY` in environment variables.
2. **Cron Route Security**:
   - Protect the cron endpoint (`/api/cron/dispatch-jobs`) with a secret bearer token:
   - Check `req.headers.authorization === Bearer ${CRON_SECRET}`.
3. **Telegram Rate Limiting**:
   - Telegram allows at most ~30 messages per second. The loop must include a small async delay (`50-100ms`) between users when subscriber count grows.
4. **403 User Block Handling**:
   - If a user blocks the bot, catch the 403 error and set `telegramActive: false` so future runs don't waste requests.

---

## 8. Directory Layout

```
job-digest-saas/
├── prisma/
│   └── schema.prisma
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth/
│   │   │   │   └── [...nextauth]/route.ts
│   │   │   ├── user/
│   │   │   │   ├── preferences/route.ts
│   │   │   │   ├── resume/route.ts
│   │   │   │   └── profile/route.ts
│   │   │   ├── telegram/
│   │   │   │   └── webhook/route.ts
│   │   │   └── cron/
│   │   │       └── dispatch-jobs/route.ts
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── dashboard/
│   │   │   ├── page.tsx
│   │   │   ├── preferences/page.tsx
│   │   │   └── telegram/page.tsx
│   │   └── layout.tsx
│   ├── lib/
│   │   ├── prisma.ts
│   │   ├── telegram.ts
│   │   ├── encrypt.ts
│   │   └── s3.ts
│   └── services/
│       ├── aggregator.ts
│       ├── filter.ts
│       └── dispatcher.ts
├── .env.example
├── package.json
└── tsconfig.json
```
