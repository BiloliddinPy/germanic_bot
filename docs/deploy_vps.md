# Deploy to Ubuntu VPS (systemd) with Railway Compatibility

This project keeps Railway compatibility and adds VPS deployment assets.

## 1) Server prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git sqlite3
```

Optional Docker path:

```bash
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

## 2) Clone and prepare app

```bash
sudo mkdir -p /opt/germanic_bot
sudo chown -R $USER:$USER /opt/germanic_bot
git clone <YOUR_REPO_URL> /opt/germanic_bot
cd /opt/germanic_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Environment config (.env)

Create `/opt/germanic_bot/.env`:

```env
BOT_TOKEN=123456:ABCDEF...
ADMIN_ID=123456789

# Optional: DB location. If omitted, app falls back safely:
# 1) legacy ./germanic.db (if exists), else
# 2) default ./data/app.db
DB_PATH=/opt/germanic_bot/data/app.db

# Optional: daily backup time in UTC
BACKUP_TIME_UTC=03:00
```

Railway note: Railway uses Variables; `.env` is mostly for local/VPS.

## 4) systemd install

1. Copy service template:

```bash
cp germanic.service.example /etc/systemd/system/germanic.service
sudo nano /etc/systemd/system/germanic.service
```

2. Adjust values if needed:
- `User`, `Group`
- `WorkingDirectory`
- `EnvironmentFile`
- `ExecStart`

3. Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable germanic.service
sudo systemctl start germanic.service
```

4. Check logs/status:

```bash
sudo systemctl status germanic.service
journalctl -u germanic.service -f
```

## 5) Update flow on VPS

```bash
cd /opt/germanic_bot
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart germanic.service
sudo systemctl status germanic.service
```

## 6) Optional Docker deployment

```bash
cd /opt/germanic_bot
docker compose up -d --build
docker compose logs -f bot
```

Volumes:
- `./data:/app/data` (DB persistence)
- `./backups:/app/backups` (backup artifacts)

## 7) Troubleshooting

### TelegramConflictError
- Only one polling instance can run for one bot token.
- Stop old Railway/VPS instance before starting another.

### Permission errors (DB/backups)
- Ensure app user can write `data/` and `backups/`.
- Verify `DB_PATH` directory exists and is writable.

### DB path confusion
- Current resolution order if `DB_PATH` not set:
  1. `./germanic.db` (legacy, if present)
  2. `./data/app.db` (default)

### Scheduler / backup timing
- Backup scheduler uses UTC (`BACKUP_TIME_UTC`, default `03:00`).
- Confirm via admin `/health` scheduler fields and logs.

## 8) Railway safety check after these changes

- Keep Railway Variables unchanged (`BOT_TOKEN`, `ADMIN_ID`, etc.).
- No webhook migration introduced; polling remains unchanged.
- If `DB_PATH` is not configured, existing legacy DB path still works.
