import os
import logging
from flask import Flask, request, Response

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
service = NotificationService(repo, telegram)


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
            phone = contact["phone_number"]
            # Standardize phone format
            if not phone.startswith("+"):
                phone = "+" + phone

            name = contact.get("first_name", "Client")

            # Save User to DB
            repo.save_or_update_user(phone=phone, name=name, telegram_id=str(chat_id))

            # Confirm
            telegram.send_message(chat_id, "✅ Connected! You will receive order updates here.")

    return Response("OK", 200)


# ==========================
#  INTERNAL TRIGGER API
# ==========================
@app.route("/trigger-notification", methods=["POST"])
def trigger():
    key = request.headers.get("X-Internal-API-Key")
    if key != INTERNAL_KEY:
        return Response("Unauthorized", 403)

    data = request.json
    result = service.notify_order_ready(
        phone=data.get("phone"),
        order_id=data.get("order_id"),
        items=data.get("items", []),
    )

    return {"status": result}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
