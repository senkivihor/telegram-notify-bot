import logging
import os

from core.models import LocationInfo

from flask import Flask, Response, request

# Imports
from infrastructure.database import init_db
from infrastructure.repositories import SqlAlchemyUserRepository
from infrastructure.telegram_adapter import TelegramAdapter

from services.admin import AdminService
from services.location import LocationService
from services.notifier import NotificationService

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelegramBot")
app = Flask(__name__)

# Config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
INTERNAL_KEY = os.getenv("INTERNAL_API_KEY")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def normalize_multiline_env(raw: str) -> str:
    # Strip wrapping quotes if present and convert escaped newlines to real newlines
    trimmed = raw.strip()
    if (trimmed.startswith('"') and trimmed.endswith('"')) or (trimmed.startswith("'") and trimmed.endswith("'")):
        trimmed = trimmed[1:-1]
    return trimmed.replace("\\n", "\n")


LOCATION_LAT = float(require_env("LOCATION_LAT"))
LOCATION_LON = float(require_env("LOCATION_LON"))
LOCATION_VIDEO_URL = require_env("LOCATION_VIDEO_URL")
LOCATION_SCHEDULE_TEXT = normalize_multiline_env(require_env("LOCATION_SCHEDULE_TEXT"))
LOCATION_CONTACT_PHONE = require_env("LOCATION_CONTACT_PHONE")
SUPPORT_CONTACT_USERNAME = os.getenv("SUPPORT_CONTACT_USERNAME", "@SupportHero")
ADMIN_IDS = {item.strip() for item in ADMIN_IDS_RAW.split(",") if item.strip()}

# Init
init_db()
repo = SqlAlchemyUserRepository()
telegram = TelegramAdapter(TELEGRAM_TOKEN)
location_info = LocationInfo(
    latitude=LOCATION_LAT,
    longitude=LOCATION_LON,
    video_url=LOCATION_VIDEO_URL,
    schedule_text=LOCATION_SCHEDULE_TEXT,
    contact_phone=LOCATION_CONTACT_PHONE,
)
location_service = LocationService(telegram, location_info)


def get_admin_service() -> AdminService:
    return AdminService(repo, telegram)


# ==========================
#  TELEGRAM WEBHOOK
# ==========================
@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    data = request.json
    admin_service = get_admin_service()

    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]

        if "text" in msg:
            text = msg["text"].strip()
            # Handle /help
            if text == "/help":
                logger.info("/help received for chat_id=%s", chat_id)
                telegram.send_message(
                    chat_id,
                    (
                        "🆘 Потрібна допомога?\n\n"
                        "Якщо у вас є питання щодо замовлення, звертайтеся напряму:\n"
                        f"👤 {SUPPORT_CONTACT_USERNAME}\n"
                        f"📞 {LOCATION_CONTACT_PHONE}"
                    ),
                    parse_mode=None,
                )
                return Response("OK", 200)

            # Handle /admin with RBAC
            if text == "/admin":
                if str(chat_id) in ADMIN_IDS:
                    telegram.send_admin_menu(chat_id)
                    return Response("OK", 200)

                telegram.send_message(chat_id, "Повертаємо вас до головного меню 🧵")
                telegram.ask_for_phone(chat_id)
                return Response("OK", 200)

            # Handle admin stats button
            if text in {"📊 Статистика", "📊 Stats"}:
                if str(chat_id) in ADMIN_IDS:
                    admin_service.send_stats(chat_id)
                    return Response("OK", 200)
                telegram.send_message(chat_id, "Повертаємо вас до головного меню 🧵")
                telegram.ask_for_phone(chat_id)
                return Response("OK", 200)

            # Handle broadcast button
            if text in {"📢 Розсилка", "📢 Broadcast"}:
                if str(chat_id) in ADMIN_IDS:
                    admin_service.send_broadcast_instructions(chat_id)
                    return Response("OK", 200)
                telegram.send_message(chat_id, "Повертаємо вас до головного меню 🧵")
                telegram.ask_for_phone(chat_id)
                return Response("OK", 200)

            # Handle /broadcast command
            if text.startswith("/broadcast"):
                if str(chat_id) not in ADMIN_IDS:
                    telegram.send_message(chat_id, "Повертаємо вас до головного меню 🛍️")
                    telegram.ask_for_phone(chat_id)
                    return Response("OK", 200)

                broadcast_text = text[len("/broadcast") :].strip()
                admin_service.broadcast(chat_id, broadcast_text)
                return Response("OK", 200)

            # A. Handle "Deep Link" or Start
            # Format: /start ORD-123
            if text.startswith("/start"):
                if str(chat_id) in ADMIN_IDS:
                    telegram.send_admin_menu(chat_id)
                    return Response("OK", 200)

                telegram.ask_for_phone(chat_id)
                return Response("OK", 200)

            # C. Handle Location request
            if text in {"📍 Локація та контакти", "Локація та контакти", "/location"}:
                location_service.send_location_details(chat_id)
                return Response("OK", 200)

        # B. Handle "Shared Phone Number"
        elif "contact" in msg:
            contact = msg["contact"]
            phone_number = contact["phone_number"]
            # Standardize phone format
            if not phone_number.startswith("+"):
                phone_number = "+" + phone_number

            name = contact.get("first_name", "Client")

            # Save User to DB
            repo.save_or_update_user(phone_number=phone_number, name=name, telegram_id=str(chat_id))

            # Confirm and hide contact keyboard
            telegram.send_message(
                chat_id,
                "✅ Підключено! Ви отримуватимете оновлення замовлень тут.",
                reply_markup={"remove_keyboard": True},
            )

            # Re-open reply keyboard so location CTA stays visible
            telegram.send_location_menu(chat_id)

    return Response("OK", 200)


# ==========================
#  INTERNAL TRIGGER API
# ==========================
@app.route("/trigger-notification", methods=["POST"])
def trigger():
    key = request.headers.get("X-Internal-API-Key")
    if not key or key != INTERNAL_KEY:
        return Response("Unauthorized", 403)

    data = request.json or {}
    phone_number = data.get("phone_number") or data.get("phone")
    service = NotificationService(
        repo,
        telegram,
        schedule_text=LOCATION_SCHEDULE_TEXT,
        contact_phone=LOCATION_CONTACT_PHONE,
    )
    result = service.notify_order_ready(
        phone_number=phone_number,
        order_id=data.get("order_id"),
        items=data.get("items", []),
    )

    return {"status": result}, 200


# ==========================================
# ➕ ADD THIS NEW SECTION HERE
# ==========================================
@app.route("/health", methods=["GET"])
def health_check():
    """Lightweight endpoint for UptimeRobot to keep the bot awake."""
    return "OK", 200


# === RUN SERVER ===
if __name__ == "__main__":
    # Use the PORT environment variable if available, otherwise 5000
    port = int(os.environ.get("PORT", 5000))
    # '0.0.0.0' is required for Docker containers to be accessible
    app.run(host="0.0.0.0", port=port)
