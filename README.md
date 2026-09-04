# Telegram Referral Growth & Group Management Bot

A production-ready, continuous 24/7 Telegram bot engineered for viral referral-based member growth, recursive invite tracking, automated deadline enforcement, group administration, member moderation, anti-spam protection, warning systems, and real-time statistics.

Built with **Python 3.12+**, **aiogram 3.x**, **SQLAlchemy 2.x async**, **PostgreSQL**, **Redis**, and **APScheduler**.

---

## 1. Project Overview

The primary goal of this bot is to create a self-propagating, viral Telegram group growth system with strict attribution and moderation:

1. **Member Joins**: A user joins the group.
2. **Unique Invite Link**: The bot generates a personal, tracked Telegram chat invite link for the member using the official Telegram Bot API `createChatInviteLink`.
3. **Deadline & Requirement**: The member must successfully invite a configurable number of new members (default: 1) within a configurable time window (default: 24 hours).
4. **Attribution & Chain**: When another user joins through that invite link, Telegram's `ChatMemberUpdated.invite_link` attributes credit to the referrer, marks their requirement complete, and generates a new link for the new arrival:
   $$\text{Member A} \longrightarrow \text{Member B} \longrightarrow \text{Member C} \longrightarrow \dots$$
5. **Enforcement**: An independent background worker continuously verifies deadlines in PostgreSQL. If a user fails to meet their requirement in time, the bot automatically executes the configured failure action (`KICK`, `RESTRICT`, or `NONE`).

---

## 2. Key Features

- **Official Telegram Referral Attribution**: Uses native Telegram Bot API unique chat invite links (`createChatInviteLink`) and `ChatMemberUpdated.invite_link` rather than deep-links that cannot verify private group joins.
- **Permanent Database Persistence**: All deadlines, relationships, invite links, warnings, and settings are saved permanently in PostgreSQL/SQLAlchemy. No state is lost across bot restarts, crashes, or server reboots.
- **24/7 Background Deadline Worker**: Periodically checks PostgreSQL for expired requirements and enforces failure actions idempotently (`action_taken = True`).
- **Interactive `/admin` Dashboard**: Real-time inline keyboard to toggle referral system, adjust deadlines (1h, 6h, 12h, 24h, 48h, custom), change required referrals (1, 2, 3, custom), toggle anti-spam, and select failure policies.
- **Dynamic User Dashboard (`/start`, `/status`)**: Real-time countdown timer ("18 hours 32 minutes remaining") and one-tap `🔄 Refresh Status` button without spamming Telegram servers.
- **Recursive Referral Tree (`/referrals`)**: Visual ASCII tree representation of the referral hierarchy with interactive page-by-page pagination.
- **Multi-Factor Anti-Spam**: Redis-backed sliding window rate limiter to detect and eliminate message flooding, repeated messages, excessive links, and excessive mentions.
- **Automated Warning System (`/warn`, `/warnings`, `/resetwarnings`)**: Issues warnings and automatically restricts or kicks members upon reaching the configured threshold (default: 3).
- **Group Rules & Welcome System**: Customizable welcome message with dynamic placeholders (`{first_name}`, `{username}`, `{group_name}`, `{required_referrals}`, `{deadline_hours}`) and `/rules` viewing.

---

## 3. Architecture

```
                                +---------------------------+
                                |     Telegram Bot API      |
                                +-------------+-------------+
                                              |
                   Updates (messages, joins)  |  API calls (links, kicks, restricts)
                                              v
+-----------------------------------------------------------------------------------------+
|                                    BOT APPLICATION                                      |
|                                                                                         |
|  +--------------------+    +--------------------+    +-------------------------------+  |
|  |     Middleware     |    |      Handlers      |    |           Services            |  |
|  | - DB Session       | -> | - admin.py         | -> | - ReferralService             |  |
|  | - AntiSpam (Redis) |    | - members.py       |    | - InviteLinkService           |  |
|  +--------------------+    | - referral.py      |    | - DeadlineService             |  |
|                            | - moderation.py    |    | - WarningService              |  |
|                            | - commands.py      |    | - SpamService                 |  |
|                            +--------------------+    +-------------------------------+  |
+-----------------------------------------------------------------------------------------+
                    |                                           ^
                    v                                           |
         +---------------------+                     +---------------------+
         |     PostgreSQL      | <------------------ |   Deadline Worker   |
         |  (Persistent Data)  |   Periodically      |    (APScheduler)    |
         +---------------------+   checks deadlines  +---------------------+
                    |
         +---------------------+
         |     Redis Cache     |
         |   (Rate Limiting)   |
         +---------------------+
```

---

## 4. Folder Structure

```
telegram-referral-bot/
├── .env.example                # Template for environment variables
├── .env                        # Local configuration (secrets)
├── .gitignore                  # Git exclusions
├── Dockerfile                  # Production-grade multi-stage container
├── docker-compose.yml          # Local Docker Compose (Postgres, Redis, Bot)
├── docker-compose.production.yml # Production Docker Compose with health checks & log rotation
├── requirements.txt            # Python dependencies
├── README.md                   # Full documentation
├── deploy.sh                   # 1-click cloud VPS deployment script
├── telegram-bot.service        # Systemd service unit file
├── alembic.ini                 # Alembic configuration
├── alembic/                    # Database migrations
│   ├── env.py
│   └── script.py.mako
├── app/
│   ├── __init__.py
│   ├── config.py               # Pydantic Settings
│   └── main.py                 # Application entry point & polling
├── bot/
│   ├── __init__.py
│   ├── filters/
│   │   ├── __init__.py
│   │   └── admin_filter.py     # Admin permission validation
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── admin.py            # /admin dashboard and inline callbacks
│   │   ├── commands.py         # /stats, /referrals, /userinfo, /rules, etc.
│   │   ├── members.py          # ChatMemberUpdated join/leave & attribution
│   │   ├── moderation.py       # /warn, /warnings, /remove, /restrict, etc.
│   │   ├── referral.py         # /start, /status, refresh button
│   │   └── welcome.py          # /setwelcome
│   ├── keyboards/
│   │   ├── __init__.py
│   │   ├── admin_kb.py         # Admin control panel inline keyboards
│   │   └── user_kb.py          # Status & tree pagination keyboards
│   └── middleware/
│       ├── __init__.py
│       ├── antispam.py         # Message rate & spam filter
│       └── db_session.py       # Async SQLAlchemy session provider
├── database/
│   ├── __init__.py
│   ├── session.py              # Engine and session maker
│   ├── models/                 # SQLAlchemy 2.0 async models
│   │   ├── user.py
│   │   ├── group.py
│   │   ├── group_settings.py
│   │   ├── referral_link.py
│   │   ├── referral_relationship.py
│   │   ├── referral_requirement.py
│   │   ├── warning.py
│   │   └── moderation_log.py
│   └── repositories/           # Encapsulated database queries
│       ├── user_repo.py
│       ├── group_repo.py
│       ├── referral_repo.py
│       └── moderation_repo.py
├── scheduler/
│   ├── __init__.py
│   └── deadline_worker.py      # Async background deadline worker
├── services/                   # Business logic layer
│   ├── invite_link_service.py
│   ├── referral_service.py
│   ├── member_service.py
│   ├── deadline_service.py
│   ├── moderation_service.py
│   ├── statistics_service.py
│   ├── warning_service.py
│   └── spam_service.py
├── utils/
│   ├── __init__.py
│   ├── logging.py              # Structured logging
│   └── security.py             # Crypto-safe referral code generation
└── tests/                      # Pytest automated test suite
    ├── __init__.py
    ├── conftest.py
    ├── test_security.py
    ├── test_referral_service.py
    ├── test_deadline_worker.py
    └── test_moderation.py
```

---

## 5. Requirements

- **Python 3.12+**
- **PostgreSQL 15+** (or SQLite for quick local test)
- **Redis 7+** (optional for local fallback; recommended for production rate limiting)
- **Docker & Docker Compose** (for containerized deployment)

---

## 6. Creating a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the instructions to choose a name and username.
3. BotFather will provide an **API Token** (e.g. `8290140755:AAH8kBCR2uoc0E3dex1arF794Ax7kG4GzYU`).
4. In @BotFather settings for your bot:
   - Go to **Bot Settings** -> **Group Privacy** -> **Turn OFF** (allows the bot to see messages in groups for anti-spam).
   - Go to **Bot Settings** -> **Allow Groups?** -> **Turn ON**.

---

## 7. Required Telegram Bot Permissions in Groups

Add the bot to your Telegram Group and promote it to **Administrator** with the following permissions:
- ✅ **Invite Users via Link** (`can_invite_users`): Critical for generating individual referral links.
- ✅ **Ban / Restrict Users** (`can_restrict_members`): Critical for enforcing deadline actions and warnings.
- ✅ **Delete Messages** (`can_delete_messages`): Critical for anti-spam filtering.
- ✅ **Pin Messages** (optional).

---

## 8. Environment Variables

Create `.env` file in the root directory:

```env
# Telegram Bot Token from @BotFather
BOT_TOKEN=8290140755:AAH8kBCR2uoc0E3dex1arF794Ax7kG4GzYU

# Environment: production or development
ENVIRONMENT=production

# Database URL
# Production PostgreSQL:
DATABASE_URL=postgresql+asyncpg://postgres:postgrespassword@localhost:5432/telegram_referral_bot
# Local SQLite fallback:
# DATABASE_URL=sqlite+aiosqlite:///./data/bot.db

# Redis URL for anti-spam
REDIS_URL=redis://localhost:6379/0

# Optional: Admin Chat ID for forwarding moderation & referral logs
ADMIN_LOG_CHAT_ID=

# Scheduler interval in seconds
DEADLINE_CHECK_INTERVAL_SECONDS=60

# Default Group Settings
DEFAULT_REFERRAL_DEADLINE_HOURS=24
DEFAULT_REQUIRED_REFERRALS=1
DEFAULT_FAILURE_ACTION=RESTRICT
DEFAULT_WARNING_LIMIT=3
```

---

## 9. Local Development Setup

1. **Clone or Navigate to the Directory**:
   ```bash
   cd telegram-referral-bot
   ```
2. **Create and Activate Virtual Environment**:
   ```bash
   python -m venv .venv
   # Linux/macOS:
   source .venv/bin/activate
   # Windows:
   .venv\Scripts\activate
   ```
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Run Automated Tests**:
   ```bash
   pytest -v
   ```
5. **Launch the Bot**:
   ```bash
   python -m app.main
   ```

---

## 10. Running with Docker Compose

Docker Compose launches PostgreSQL, Redis, the Bot, and the background worker with a single command:

```bash
docker compose up -d --build
```

View live logs:
```bash
docker compose logs -f bot
```

Stop services:
```bash
docker compose down
```

---

## 11. Production 24/7 Cloud Deployment (Runs When Laptop is OFF)

To run continuously 24/7 without keeping your laptop on:

### Option A: Any Linux VPS (DigitalOcean, Hetzner, AWS, Linode)

1. Provision a standard Ubuntu 22.04/24.04 VPS ($4–$6/month).
2. SSH into your VPS:
   ```bash
   ssh root@your-server-ip
   ```
3. Clone or copy your project folder to `/opt/telegram-referral-bot`.
4. Run the automated deployment script:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```
   This script will automatically install Docker, build the container with `restart: unless-stopped`, and launch PostgreSQL, Redis, and the bot daemon.

### Option B: Systemd Service on Linux VPS (Direct Python Execution)

If running without Docker:
1. Install Python 3.12, PostgreSQL, and Redis on the VPS:
   ```bash
   sudo apt update && sudo apt install -y python3-pip python3-venv postgresql redis-server
   ```
2. Copy files to `/opt/telegram-referral-bot`.
3. Install systemd service:
   ```bash
   sudo cp telegram-bot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now telegram-bot
   ```
4. Check status:
   ```bash
   sudo systemctl status telegram-bot
   ```

---

## 12. Complete Commands Reference

### User Commands
| Command | Description |
|---|---|
| `/start` | Opens personal dashboard with invite link, progress, and remaining time |
| `/status` | Shows referral status with dynamic countdown and refresh button |
| `/rules` | Displays the current group rules |

### Administrator Commands
| Command | Description |
|---|---|
| `/admin` | Opens the inline interactive dashboard |
| `/settings` | Alias for `/admin` |
| `/stats` | View group statistics and top referrers leaderboard |
| `/referrals` | View ASCII recursive referral tree with pagination |
| `/userinfo <USER_ID>` | View detailed profile, requirement, and referral info |
| `/exempt <USER_ID>` | Exempt a member from referral deadlines |
| `/reset_timer <USER_ID> [hours]` | Reset member's countdown timer (default: 24h) |
| `/regenerate_link <USER_ID>` | Revoke old link and issue a fresh invite link |
| `/warn <USER_ID> [reason]` | Issue a warning (triggers kick/restrict at limit) |
| `/warnings <USER_ID>` | View warnings list for a user |
| `/resetwarnings <USER_ID>` | Clear all warnings for a user |
| `/remove <USER_ID>` | Kick member (ban + unban so user can rejoin) |
| `/restrict <USER_ID>` | Restrict member chat permissions |
| `/unrestrict <USER_ID>` | Restore member chat permissions |
| `/setrules <text>` | Set group rules |
| `/setwelcome <text>` | Set custom welcome template with placeholders |

---

## 13. Telegram Bot API Limitations & Edge Cases Handled

1. **Private Message Restrictions**: Telegram does not allow bots to send unsolicited DMs to users who have not started the bot. The bot handles this gracefully by posting an inline button `👉 Get My Personal Referral Link` in the group's welcome message, which launches the bot in DM.
2. **Kick vs. Ban**: In Telegram API, "kick" is achieved by calling `ban_chat_member` followed immediately by `unban_chat_member`. This removes the user from the group while permitting them to rejoin later through a referral link.
3. **Idempotent Deadlines**: Stored permanently in PostgreSQL with `action_taken = True` so multiple background check ticks never apply duplicate actions.
4. **Duplicate Joins**: Database constraints prevent the same user from generating multiple referral credits for a referrer if they leave and rejoin.
