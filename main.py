import logging
import os

from flask import Flask, Response, request

# Imports
from infrastructure.database import init_db
from infrastructure.repositories import SqlAlchemyUserRepository
from infrastructure.telegram_adapter import TelegramAdapter

from services.notifier import NotificationService

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelegramBot")
app = Flask(__name__)

# Config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
INTERNAL_KEY = os.getenv("INTERNAL_API_KEY")

# Init
init_db()
repo = SqlAlchemyUserRepository()
telegram = TelegramAdapter(TELEGRAM_TOKEN)


# ==========================
#  TELEGRAM WEBHOOK
# ==========================
@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    data = request.json

    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]

        # A. Handle "Deep Link" or Start
        # Format: /start ORD-123
        if "text" in msg and msg["text"].startswith("/start"):
            telegram.ask_for_phone(chat_id)

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

            # Confirm
            telegram.send_message(chat_id, "✅ Підключено! Ви отримуватимете оновлення замовлень тут.")

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
    service = NotificationService(repo, telegram)
    result = service.notify_order_ready(
        phone_number=phone_number,
        order_id=data.get("order_id"),
        items=data.get("items", []),
    )

    return {"status": result}, 200


# === RUN SERVER ===
if __name__ == "__main__":
    # Use the PORT environment variable if available, otherwise 5000
    port = int(os.environ.get("PORT", 5000))
    # '0.0.0.0' is required for Docker containers to be accessible
    app.run(host="0.0.0.0", port=port)
