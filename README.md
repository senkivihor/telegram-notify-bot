🔔 Telegram Notification Bot
A production-grade, secure notification service for sending transactional updates (e.g., "Order Ready", "Payment Received") to clients via Telegram. Built with Python (Flask), PostgreSQL, and Docker, following Hexagonal Architecture principles. A simplified deep link onboarding flow eliminates manual user registration.

## Key Features
- ⚡ Frictionless onboarding via deep links (t.me/MyBot?start=ORD-123) or "Share Contact"; no passwords or sign-ups.
- 🔒 Secure phone mapping that links a client's phone number to their Telegram Chat ID in PostgreSQL.
- 🛡️ Internal API gateway: protected /trigger-notification endpoint for CRM/website/warehouse systems.
- 🐳 Fully Dockerized with a single docker-compose command.
- 🏗️ Hexagonal Architecture keeps business logic decoupled and testable.
- 🖼️ Portfolio CTA: inline "Open Instagram" button plus reply-keyboard entry to showcase your work.
- 💰 Price list: Markdown-formatted price menu backed by a single data file for easy business edits.
- 🧭 Smart welcome flow: auto-routes guests vs members to the right keyboard (client card vs share phone).

## Tech Stack
- Language: Python 3.11
- Framework: Flask 3.0
- Database: PostgreSQL 15
- Dependency manager: Poetry
- Containerization: Docker & Docker Compose
- Testing: Pytest

## Project Structure
```text
/telegram-notify-bot
├── core/                   # Domain models & interfaces (pure Python)
├── infrastructure/         # Adapters (database, Telegram API)
├── services/               # Business logic (notification service)
├── tests/                  # Unit tests
├── main.py                 # Application entry point (webhooks)
├── docker-compose.yml      # Orchestration
├── Dockerfile              # Container definition
└── pyproject.toml          # Dependencies
```

## Getting Started
### 1. Prerequisites
- Docker & Docker Compose installed.
- Telegram Bot Token (from @BotFather).
- Generated Internal API Key (to secure the trigger endpoint).

### 2. Configuration
Create a .env file in the project root (do not commit this file):

```bash
# .env
# 1. Get this from @BotFather
TELEGRAM_BOT_TOKEN=123456789:ABCdef-GHIjkl...

# 2. Generate a strong random string (e.g., using 'openssl rand -hex 32')
INTERNAL_API_KEY=my_secure_secret_key_change_me

# 3. Location & schedule (required)
LOCATION_LAT=00.000000
LOCATION_LON=00.000000
LOCATION_VIDEO_URL=https://example.com/entrance.mp4
LOCATION_SCHEDULE_TEXT="⏰ **Наш графік:**\n• Пн-Пт: 10:00 – 19:00\n• Сб: 11:00 – 14:00 (за дзвінком)\n• Нд: Вихідний"
LOCATION_CONTACT_PHONE=+380000000000

# 4. Admins (comma-separated chat IDs; optional)
ADMIN_IDS=12345,67890

# 5. Support contacts (optional, used in /help)
SUPPORT_CONTACT_USERNAME=@SupportHero
# Help will reuse LOCATION_CONTACT_PHONE for the phone line

# 6. Portfolio (optional, recommended)
# If absent, the bot logs a warning and falls back to a placeholder link.
INSTAGRAM_URL=https://instagram.com/your-portfolio

```

### 3. Run with Docker
Start the application and database:

```bash
docker-compose up --build -d
```

Application: http://localhost:5000

### 4. Set the Webhook
Tell Telegram where your bot is hosted (replace <YOUR_DOMAIN> and <YOUR_TOKEN>):

```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://<YOUR_DOMAIN>/webhook/telegram"
```

> If running locally, use a tool like ngrok to get a public HTTPS URL.

## Usage Guide
### 1. Client Onboarding (User Flow)
1. Send a deep link via SMS or email when an order is placed (e.g., https://t.me/YourBotName?start=ORD-5501).
2. User taps the link and hits "Start" in Telegram.
3. Smart welcome:
  - Guest: sees "📞 Отримати клієнтську карту", "💰 Ціни", "📸 Наші роботи", "📍 Локація та контакти".
  - Member: sees "💎 Моя клієнтська карта", "💰 Ціни", "📸 Наші роботи", "📍 Локація та контакти".
4. Guest shares phone → number is mapped to Chat ID and stored.
5. Users can tap "📸 Our Work" to see your Instagram portfolio with an inline "Open Instagram" button for a clean tap-through.
6. "💰 Ціни" shows the Markdown price list stored in services/price_data.py via PriceService.

### 1b. Admin and fallback flow
- Admins (`ADMIN_IDS`) still see the admin menu.
- Non-admin `/admin` requests get a friendly "Command not recognized" then are routed through the smart welcome (so members are not asked to reshare phone).

### 2. Location & Schedule
- Button: "📍 Де нас знайти?" appears on the reply keyboard during onboarding.
- Behavior: sends a map pin, entrance video (or compatible clip), operating hours, plus inline buttons to open the map and call.
- Env overrides (optional): `LOCATION_LAT`, `LOCATION_LON`, `LOCATION_VIDEO_URL`, `LOCATION_SCHEDULE_TEXT`.

### 3. Portfolio CTA (Instagram)
- Button: "📸 Our Work" lives alongside onboarding buttons and remains available after contact sharing.
- Behavior: sends a rich message with an inline "Open Instagram" button and the configured `INSTAGRAM_URL`.
- After a user shares their phone number, the confirmation message also includes the Instagram link to keep them engaged.
- If `INSTAGRAM_URL` is missing, the bot warns once on startup and uses a placeholder link.

### 4. Price List
- Button: "💰 Ціни" on both guest and member keyboards.
- Behavior: sends Markdown-rendered price text from services/price_data.py through PriceService.
- Editing prices: adjust the text in services/price_data.py; no code changes needed.

### 3. Admin Access (RBAC)
- Configure `ADMIN_IDS` with a comma-separated list of Telegram chat IDs of admins/owners.
- Behavior: when an admin sends `/start`, the bot shows a distinct admin keyboard (e.g., "📊 Статистика", "📢 Розсилка").
- Regular users never see or learn about the admin menu; they get the standard onboarding flow instead.
- Admin actions:
  - "📊 Статистика": shows total user count.
  - "📢 Розсилка": shows safe broadcast instructions.
  - `/broadcast <text>` (admins only): sends `<text>` to all users and reports successes/failures.

### 4. Triggering Notifications (API)
- Endpoint: POST /trigger-notification
- Headers:
  - Content-Type: application/json
  - X-Internal-API-Key: <YOUR_INTERNAL_KEY>
- Body example:

```json
{
  "phone": "+380501234567",
  "order_id": "ORD-5501",
  "items": ["Laptop", "Wireless Mouse"]
}
```

Example request (cURL):

```bash
curl -X POST http://localhost:5000/trigger-notification \
     -H "Content-Type: application/json" \
     -H "X-Internal-API-Key: my_secure_secret_key_change_me" \
     -d '{"phone": "+380501234567", "order_id": "ORD-5501", "items": ["Pizza"]}'
```

Responses:
- 200 OK: {"status": "Success"} (message sent)
- 200 OK: {"status": "Failed: User not found"} (user has not started the bot)
- 403 Forbidden: invalid API key

## Development & Testing
The project uses pytest; external calls (Telegram API, DB) are mocked, so tests run offline.

Option A: inside Docker (recommended):

```bash
docker-compose exec bot pytest
```

Option B: locally:

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

Key suites: tests/test_main.py (webhook flows), tests/test_flows.py (smart welcome + /admin redirects), tests/test_price_service.py (price data formatting).
```

## Security Best Practices
- Never commit .env to version control.
- Rotate your INTERNAL_API_KEY periodically.
- Run behind a reverse proxy (Nginx or Traefik) with SSL (HTTPS) in production; Telegram webhooks require HTTPS.

## Hosting notes
- Deployment: currently hosted on Render (Docker); Render sets the `PORT` env var automatically, which the app already honors.
- Database: Neon/PostgreSQL with `sslmode=require` in `DATABASE_URL` (default).
- Connection pool is configured with `pool_pre_ping` + `pool_recycle` to refresh stale sockets and Postgres keepalives; no extra config needed for Render + Neon.
- If you still observe occasional disconnects, shorten `pool_recycle` (e.g., 300–600s) and keep pool sizes modest to stay within Neon limits.

## CI/CD
- GitHub Actions runs flake8 and pytest on pushes and pull requests.
- On push to `main`, after checks pass, a deploy is triggered via Render deploy hook.
- Required secret: `RENDER_DEPLOY_HOOK` set in GitHub repo Actions secrets (full deploy hook URL from Render service settings).
