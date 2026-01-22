import requests
import logging


class TelegramAdapter:
    def __init__(self, bot_token: str):
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger("TelegramAdapter")

    def send_message(self, chat_id: str, text: str):
        """Sends a standard text message."""
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
            requests.post(url, json=payload, timeout=5)
            self.logger.info(f"✅ Sent message to {chat_id}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to send Telegram message: {e}")
            return False

    def ask_for_phone(self, chat_id: str):
        """Sends a button asking the user to share their phone number."""
        url = f"{self.api_url}/sendMessage"
        keyboard = {
            "keyboard": [
                [
                    {
                        "text": "📱 Share Phone Number to Connect Order",
                        "request_contact": True,
                    }
                ]
            ],
            "one_time_keyboard": True,
            "resize_keyboard": True,
        }
        payload = {
            "chat_id": chat_id,
            "text": "👋 Welcome! Please tap the button below to link your account.",
            "reply_markup": keyboard,
        }
        requests.post(url, json=payload)
