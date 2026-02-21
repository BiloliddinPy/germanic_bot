# Germanic Bot - Run Instructions

## 1. Setup
Navigate to the project directory:
```bash
cd /Users/macbookpro/Desktop/Antigravity_Projects/germanic_bot
```

## 2. Install Dependencies
```bash
pip install -r requirements.txt
```

## 3. Run the Bot
```bash
python3 main.py
```

## 3.1 Health & Smoke Checks (recommended)
```bash
python3 scripts/health_check.py
python3 scripts/smoke_day7.py
python3 scripts/smoke_daily_lesson.py
```

## 3.2 Ops Monitoring Report (read-only, production-safe)
```bash
python3 scripts/ops_report.py --days 7 --top 10
```

Optional:
```bash
python3 scripts/ops_report.py --days 30 --top 20 --db germanic.db --log bot.log
```

## 3.3 Polling Conflict Check (Railway log analysis)
```bash
python3 scripts/check_polling_conflict.py --file bot.log --minutes 10 --warn 3 --crit 10
```

Railway plain text logni stdin orqali:
```bash
cat railway.log | python3 scripts/check_polling_conflict.py --file - --minutes 10
```

## 4. Admin
Your Admin ID (`1299147498`) is configured in `.env`.
Users will be able to click "Aloqa" to contact you directly via Telegram link.

## 5. Notes
- Database: `germanic.db` (auto-created)
- Content: Edit files in `data/`

### Railway / Postgres (staged rollout)
- Default backend is SQLite (`DB_BACKEND=sqlite`).
- To prepare Postgres env in Railway, set:
  - `DATABASE_URL=<Railway Postgres URL>`
  - `DB_BACKEND=postgres` (enable only after full SQL migration step)
  - `DB_POOL_MIN_SIZE=1`
  - `DB_POOL_MAX_SIZE=20`

## 6. Docker Persistence (important)
- In Docker, DB is pinned to `/app/data/germanic.db` (mounted from `./data`).
- This prevents onboarding reset after container restart/redeploy.
