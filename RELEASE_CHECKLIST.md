# Release Checklist (Production)

## 1. Pre-flight
- `.env` ichida `BOT_TOKEN` mavjudligini tekshiring.
- `requirements.txt` bo'yicha dependencylar o'rnatilgan bo'lsin.
- Ishchi papka: `germanic_bot`.

## 2. Static checks
- `python3 -m py_compile main.py config.py database.py handlers/*.py keyboards/*.py utils/*.py scripts/*.py`

## 3. Data/DB checks
- `python3 scripts/health_check.py`
- `python3 scripts/smoke_day7.py`
- `python3 scripts/smoke_daily_lesson.py`
- `python3 scripts/ops_report.py --days 7 --top 10` (read-only operational snapshot)

## 4. Manual smoke (Telegram)
- `/start` -> menyu chiqishini tekshiring.
- `🚀 Kunlik dars` oqimi to'liq yursin:
  - context
  - vocab
  - grammar
  - material
  - quiz
  - writing
  - finish
- `📊 Natijalar` ekranida qiymatlar chiqishini tekshiring.
- `⚙️ Profil` ochilishini tekshiring.

## 5. Background run
- `pkill -f main.py` (eski processni to'xtatish)
- `sh run_background.sh`
- `ps aux | rg main.py` orqali process borligini tekshirish.

## 6. Rollback (safe)
- Agar deploydan keyin muammo bo'lsa:
  - eski barqaror commitga qaytish
  - bot process restart
- DB destructive amal qilinmaydi; faqat additive migration ishlatiladi.
