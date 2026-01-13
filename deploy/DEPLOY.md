# AnyArchie Server Deployment

## Server: defibeats@100.109.104.88

### 1. Install PostgreSQL

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 2. Create Database

```bash
# Switch to postgres user and create database
sudo -u postgres createdb anyarchie
sudo -u postgres psql -c "CREATE USER defibeats WITH PASSWORD 'anyarchie_db_pass';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE anyarchie TO defibeats;"
sudo -u postgres psql -c "ALTER DATABASE anyarchie OWNER TO defibeats;"

# Connect and run schema
sudo -u postgres psql anyarchie < /var/www/anyarchie/schema.sql

# Grant permissions on tables
sudo -u postgres psql anyarchie -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO defibeats;"
sudo -u postgres psql anyarchie -c "GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO defibeats;"
```

### 3. Clone Repository

```bash
sudo mkdir -p /var/www/anyarchie
sudo chown defibeats:defibeats /var/www/anyarchie
cd /var/www/anyarchie
git clone https://github.com/jgabriele321/any_archie.git .
```

### 4. Create Virtual Environment

```bash
cd /var/www/anyarchie
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Create .env File

```bash
cat > /var/www/anyarchie/.env << 'EOF'
# AnyArchie Configuration

# Database
DATABASE_URL=postgresql://defibeats:anyarchie_db_pass@localhost:5432/anyarchie

# OpenRouter (LLM) - GET FROM PERSONAL ASSISTANT .env
OPENROUTER_API_KEY=your_key_here

# Exa (Web Search) - GET FROM PERSONAL ASSISTANT .env
EXA_API_KEY=your_key_here

# Hub Bot Token (optional - not using for now)
# HUB_BOT_TOKEN=

# Bot Token Pool - Add your bot tokens here (comma-separated)
BOT_TOKEN_POOL=your_bot_token_here

# Admin Telegram ID (Johnny's Telegram ID)
ADMIN_TELEGRAM_ID=
EOF
```

Then edit to add your actual API keys:
```bash
nano /var/www/anyarchie/.env
```

### 6. Install Systemd Services

```bash
sudo cp /var/www/anyarchie/deploy/anyarchie-bot.service /etc/systemd/system/
sudo cp /var/www/anyarchie/deploy/anyarchie-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### 7. Start Services

```bash
sudo systemctl enable anyarchie-bot
sudo systemctl enable anyarchie-worker
sudo systemctl start anyarchie-bot
sudo systemctl start anyarchie-worker
```

### 8. Verify

```bash
# Check status
sudo systemctl status anyarchie-bot
sudo systemctl status anyarchie-worker

# View logs
sudo journalctl -u anyarchie-bot -f --no-pager
sudo journalctl -u anyarchie-worker -f --no-pager
```

---

## Quick Commands

```bash
# Restart bot
sudo systemctl restart anyarchie-bot

# View bot logs
sudo journalctl -u anyarchie-bot -f --no-pager

# Update code
cd /var/www/anyarchie && git pull && sudo systemctl restart anyarchie-bot anyarchie-worker

# Check database
psql anyarchie -c "SELECT * FROM users;"
```

---

## Adding More Users

1. Create new bot via @BotFather
2. Add token to BOT_TOKEN_POOL in .env (comma-separated)
3. Restart: `sudo systemctl restart anyarchie-bot`
4. User messages the new bot → auto-onboarded!
