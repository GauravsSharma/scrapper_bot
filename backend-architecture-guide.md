# 🚀 Job Digest SaaS: Complete Backend Implementation Guide

This guide details the complete backend architecture for the multi-user Job Digest platform. It implements **Method 1 (Copy-Paste Chat ID)** for Telegram linking, a centralized job scraping engine, per-user preference filtering, deduplication, and automated daily dispatch.

---

## 1. Tech Stack & Environment

- **Runtime & Framework**: Next.js 14+ (App Router) or Node.js (Express / Fastify) with TypeScript
- **Database**: PostgreSQL (Hosted on Neon, Supabase, or Railway)
- **ORM**: Prisma ORM
- **Authentication**: NextAuth.js / JWT / Session
- **Storage**: AWS S3 or Supabase Storage (for Resume PDFs)
- **Telegram Bot API**: Single Central Bot (`@job_scrapper_99_bot`)

### Environment Variables (`.env`)

```env
# Database
DATABASE_URL="postgresql://user:password@localhost:5432/job_digest?schema=public"

# Auth Secrets
NEXTAUTH_SECRET="your-super-secret-jwt-key"
NEXTAUTH_URL="http://localhost:3000"

# Telegram Bot (The Central Official Bot)
TELEGRAM_BOT_TOKEN="8168549397:AAFTfvnxE8kSR86PNUdXAyvvT3oTyfXQKOY"

# Cron Security (Protects the dispatch trigger endpoint)
CRON_SECRET="your-secure-cron-secret-token"

# Optional: AWS S3 or Supabase for Resume uploads
AWS_ACCESS_KEY_ID=""
AWS_SECRET_ACCESS_KEY=""
AWS_REGION="ap-south-1"
AWS_S3_BUCKET="job-digest-resumes"
```

---

## 2. Database Schema (`prisma/schema.prisma`)

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
  passwordHash    String?
  telegramChatId  String?      @unique   // User enters their chat ID from the bot
  telegramActive  Boolean      @default(true)
  resumeUrl       String?      // Stored PDF link
  isActive        Boolean      @default(true)
  createdAt       DateTime     @default(now())
  updatedAt       DateTime     @updatedAt

  preference      Preference?
  seenJobs        SeenJob[]
  digestLogs      DigestLog[]

  @@index([telegramChatId])
}

model Preference {
  id               String    @id @default(uuid())
  userId           String    @unique
  user             User      @relation(fields: [userId], references: [id], onDelete: Cascade)
  keywords         String[]  // e.g. ["node", "react", "next", "full stack", "backend", "ai"]
  targetCities     String[]  // e.g. ["noida", "gurgaon", "delhi", "agra", "remote"]
  allowRemote      Boolean   @default(true)
  prioritizeRemote Boolean   @default(true)
  excludeSenior    Boolean   @default(true)
  maxJobsDaily     Int       @default(10)
  createdAt        DateTime  @default(now())
  updatedAt        DateTime  @updatedAt
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

## 3. Telegram Bot Service (How Users Get Their Chat ID)

The official central bot has a webhook or polling listener. When any user sends `/start` or `/id`, the bot responds with their unique `chat_id` formatted for easy one-tap copying.

### Bot Logic (`src/lib/telegramBot.ts`)

```typescript
import axios from "axios";

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_API = `https://api.telegram.org/bot${BOT_TOKEN}`;

export async function handleTelegramWebhook(update: any) {
  const message = update?.message;
  if (!message || !message.text) return;

  const chatId = message.chat.id;
  const text = message.text.trim();

  // If user sends /start, /id, or any greeting
  if (text.startsWith("/start") || text.startsWith("/id")) {
    const replyText = 
      `👋 *Welcome to Job Digest!*\n\n` +
      `Here is your Telegram Chat ID:\n` +
      `\`${chatId}\`\n\n` +
      `📋 *Instructions:*\n` +
      `1. Tap the ID above to copy it.\n` +
      `2. Go to your Dashboard.\n` +
      `3. Paste it in the *Telegram Chat ID* box and click Save.\n\n` +
      `You will receive your personalized job digest every morning at 09:00 AM!`;

    await axios.post(`${TELEGRAM_API}/sendMessage`, {
      chat_id: chatId,
      text: replyText,
      parse_mode: "Markdown",
    });
  }
}

// Function to send a message to any user by their chatId
export async function sendTelegramMessage(chatId: string, text: string) {
  return axios.post(`${TELEGRAM_API}/sendMessage`, {
    chat_id: chatId,
    text: text.slice(0, 4000),
    disable_web_page_preview: true,
  });
}
```

---

## 4. API Endpoints Specification

### A. Telegram Chat ID Linking
- **Endpoint**: `PUT /api/user/telegram-chat`
- **Auth**: Protected (Session / JWT)
- **Request Body**:
  ```json
  {
    "chatId": "5241697143"
  }
  ```
- **Handler Logic**:
  ```typescript
  // 1. Validate chatId is non-empty
  // 2. Send a confirmation test message via Telegram API to verify the chat ID exists
  // 3. Update User table: user.telegramChatId = chatId, user.telegramActive = true
  // 4. Return success response
  ```

---

### B. User Preferences
- **Endpoint**: `GET /api/user/preferences`
  - Returns current saved preferences or default empty values.
- **Endpoint**: `PUT /api/user/preferences`
  - **Request Body**:
    ```json
    {
      "keywords": ["node", "react", "next", "full stack", "backend", "ai engineer"],
      "targetCities": ["noida", "gurgaon", "delhi", "agra"],
      "allowRemote": true,
      "prioritizeRemote": true,
      "excludeSenior": true,
      "maxJobsDaily": 10
    }
    ```
  - **Handler Logic**:
    ```typescript
    await prisma.preference.upsert({
      where: { userId: session.user.id },
      update: { keywords, targetCities, allowRemote, prioritizeRemote, excludeSenior, maxJobsDaily },
      create: { userId: session.user.id, keywords, targetCities, allowRemote, prioritizeRemote, excludeSenior, maxJobsDaily }
    });
    ```

---

### C. Resume PDF Upload
- **Endpoint**: `POST /api/user/resume`
- **Content-Type**: `multipart/form-data`
- **File**: `resume` (PDF only, max 5MB)
- **Handler Logic**:
  1. Validate file extension (`.pdf`) and size.
  2. Upload to S3 or Supabase Storage: `resumes/${userId}-${Date.now()}.pdf`.
  3. Save storage URL into `User.resumeUrl`.
  4. Return `{ success: true, url: resumeUrl }`.

---

## 5. Daily Dispatch Cron Engine (The Multi-User Loop)

This service runs every day at 09:00 AM IST via an automated cron trigger (`POST /api/cron/dispatch-jobs`).

### Step-by-Step Dispatch Flow

```mermaid
flowchart TD
    A["1. Cron Trigger (09:00 AM IST)"] --> B["2. Fetch All Jobs from Public APIs Once\n(Greenhouse, Lever, Remotive, Arbeitnow, Jobicy)"]
    B --> C["3. Fetch All Users where telegramChatId is NOT null\n& telegramActive = true"]
    C --> D["4. Loop through each User"]
    D --> E["5. Filter jobs matching user's keywords & target cities"]
    E --> F["6. Exclude jobs already present in user's SeenJob records"]
    F --> G["7. Prioritize Remote first, On-site second (up to maxJobsDaily)"]
    G --> H["8. Dispatch message to user's telegramChatId"]
    H --> I["9. Save sent job URLs into SeenJob table for this user"]
    I --> J["10. Pause 60ms to prevent Telegram rate-limiting (30 msg/sec)"]
    J --> D
```

### Complete Dispatcher Implementation (`src/services/dispatcher.ts`)

```typescript
import prisma from "@/lib/prisma";
import { fetchAllJobs, RawJob } from "@/services/aggregator";
import { matchRole, matchLocation, isRemote } from "@/services/filter";
import { sendTelegramMessage } from "@/lib/telegramBot";

export async function runDailyJobDispatch() {
  console.log("[CRON] Starting multi-user job dispatch cycle...");

  // Step 1: Fetch raw jobs ONCE for all users (saves API calls)
  const allJobs: RawJob[] = await fetchAllJobs();
  console.log(`[CRON] Fetched ${allJobs.length} active jobs from sources.`);

  // Step 2: Fetch all active users who saved a Telegram chat ID
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

  console.log(`[CRON] Processing ${users.length} subscribed users.`);

  // Step 3: Loop through each user
  for (const user of users) {
    const chatId = user.telegramChatId!;
    const pref = user.preference || {
      keywords: ["node", "react", "next", "full stack", "backend"],
      targetCities: ["noida", "gurgaon", "delhi", "agra"],
      allowRemote: true,
      prioritizeRemote: true,
      excludeSenior: true,
      maxJobsDaily: 10,
    };

    try {
      const seenUrls = new Set(user.seenJobs.map((s) => s.jobUrl));

      // Filter jobs matching user's specific preferences
      const matched = allJobs.filter((job) => {
        if (!job.url || seenUrls.has(job.url)) return false;
        const roleOk = matchRole(job.title, pref.keywords, pref.excludeSenior);
        const locOk = matchLocation(job.location, pref.targetCities, pref.allowRemote);
        return roleOk && locOk;
      });

      // Sort: Remote first if prioritizeRemote is enabled
      if (pref.prioritizeRemote) {
        matched.sort((a, b) => (isRemote(a.location) ? -1 : 1));
      }

      const jobsToSend = matched.slice(0, pref.maxJobsDaily);

      if (jobsToSend.length > 0) {
        // Format message
        const message = formatTelegramMessage(jobsToSend, user.name, pref.targetCities);
        
        // Send via central bot
        await sendTelegramMessage(chatId, message);

        // Record in SeenJob table
        await prisma.seenJob.createMany({
          data: jobsToSend.map((j) => ({
            userId: user.id,
            jobUrl: j.url,
          })),
          skipDuplicates: true,
        });

        await prisma.digestLog.create({
          data: {
            userId: user.id,
            jobsSent: jobsToSend.length,
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

      // Small async delay to comply with Telegram rate limits (max 30 msg/sec)
      await new Promise((r) => setTimeout(r, 60));
    } catch (err: any) {
      console.error(`[ERROR] Failed to dispatch for user ${user.id} (${user.email}):`, err);

      // Handle user blocking the bot (HTTP 403 Forbidden)
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

  console.log("[CRON] Multi-user job dispatch cycle finished.");
}

function formatTelegramMessage(jobs: RawJob[], userName: string, cities: string[]) {
  const remote = jobs.filter((j) => isRemote(j.location));
  const onsite = jobs.filter((j) => !isRemote(j.location));

  const lines = [`🎯 *Job Digest for ${userName}* (${jobs.length} new matches)\n`];

  if (remote.length > 0) {
    lines.push(`🌐 *REMOTE OPPORTUNITIES (Priority 1):*`);
    for (const j of remote) {
      lines.push(`• *${j.title}* @ ${j.company}\n  📍 ${j.location}\n  🔗 ${j.url}\n`);
    }
  }

  if (onsite.length > 0) {
    const citiesStr = cities.map((c) => c.toUpperCase()).join(" / ");
    lines.push(`📍 *ON-SITE / HYBRID (${citiesStr}) (Priority 2):*`);
    for (const j of onsite) {
      lines.push(`• *${j.title}* @ ${j.company}\n  📍 ${j.location}\n  🔗 ${j.url}\n`);
    }
  }

  return lines.join("\n").trim();
}
```

---

## 6. Project Directory Layout

```
job-digest-backend/
├── prisma/
│   └── schema.prisma                # Database schema
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth/
│   │   │   │   └── [...nextauth]/route.ts
│   │   │   ├── user/
│   │   │   │   ├── profile/route.ts
│   │   │   │   ├── preferences/route.ts
│   │   │   │   ├── resume/route.ts
│   │   │   │   └── telegram-chat/route.ts
│   │   │   ├── telegram/
│   │   │   │   └── webhook/route.ts # Receives /start and replies with chat ID
│   │   │   └── cron/
│   │   │       └── dispatch/route.ts # Daily trigger protected by CRON_SECRET
│   │   ├── dashboard/               # Frontend dashboard pages
│   │   │   ├── page.tsx
│   │   │   ├── preferences/page.tsx
│   │   │   └── telegram/page.tsx
│   │   └── layout.tsx
│   ├── lib/
│   │   ├── prisma.ts                # Prisma singleton instance
│   │   ├── telegramBot.ts           # Telegram sendMessage & webhook handler
│   │   └── s3.ts                    # AWS S3 / Supabase storage uploader
│   └── services/
│       ├── aggregator.ts            # Public API scrapers (Greenhouse, Lever, etc.)
│       ├── filter.ts                # Role & Location matchers
│       └── dispatcher.ts            # Multi-user loop dispatcher
├── .env.example
├── package.json
└── tsconfig.json
```

---

## 7. Step-by-Step Implementation Roadmap

1. **Phase 1: Database & Prisma Setup**
   - Run `npx prisma init`
   - Paste schema into `prisma/schema.prisma`
   - Run `npx prisma migrate dev --name init`

2. **Phase 2: Telegram Bot Webhook**
   - Create route `POST /api/telegram/webhook`
   - Register webhook with Telegram: `https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<your-domain>/api/telegram/webhook`
   - Now when users open your bot and type `/start`, the bot gives them their Chat ID.

3. **Phase 3: Dashboard APIs**
   - Implement `PUT /api/user/telegram-chat` to save chat ID.
   - Implement `PUT /api/user/preferences` to save keywords and cities.
   - Implement `POST /api/user/resume` to save uploaded PDF.

4. **Phase 4: Cron Dispatcher**
   - Connect `src/services/dispatcher.ts` to `POST /api/cron/dispatch`.
   - Set up daily trigger using GitHub Actions, Vercel Cron, or Railway Cron at 09:00 AM IST.
