import logging


import requests


class TelegramAdapter:
    def __init__(self, bot_token: str):
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger("TelegramAdapter")

    @staticmethod
    def get_guest_keyboard() -> dict:
        return {
            "keyboard": [
                [
                    {
                        "text": "📞 Поділитись номером",
                        "request_contact": True,
                    }
                ],
                [
                    {"text": "💰 Ціни"},
                    {"text": "📸 Наші роботи"},
                ],
                [
                    {"text": "📍 Локація"},
                    {"text": "📅 Графік"},
                ],
                [
                    {"text": "📞 Контактний телефон"},
                    {"text": "🆘 Допомога"},
                ],
            ],
            "one_time_keyboard": True,
            "resize_keyboard": True,
        }

    @staticmethod
    def get_member_keyboard() -> dict:
        return {
            "keyboard": [
                [
                    {"text": "💰 Ціни"},
                    {"text": "📸 Наші роботи"},
                ],
                [
                    {"text": "📍 Локація"},
                    {"text": "📅 Графік"},
                ],
                [
                    {"text": "📞 Контактний телефон"},
                    {"text": "🆘 Допомога"},
                ],
            ],
            "one_time_keyboard": False,
            "resize_keyboard": True,
        }

    def send_message(
        self, chat_id: str, text: str, reply_markup: dict | None = None, parse_mode: str | None = "Markdown"
    ):
        """Send a text message and surface Telegram API errors; retry without parse_mode on parse failures."""
        url = f"{self.api_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            response = requests.post(url, json=payload, timeout=5)
            # Telegram returns HTTP 200 even when ok=false, so check both
            if not response.ok:
                self.logger.error(
                    "❌ Telegram sendMessage failed for %s: status=%s body=%s",
                    chat_id,
                    response.status_code,
                    response.text,
                )
                if parse_mode and response.status_code == 400 and "parse" in response.text.lower():
                    self.logger.info("Retrying sendMessage without parse_mode for chat_id=%s", chat_id)
                    payload.pop("parse_mode", None)
                    retry_response = requests.post(url, json=payload, timeout=5)
                    if retry_response.ok and retry_response.json().get("ok", False):
                        self.logger.info("✅ Sent message to %s after retry without parse_mode", chat_id)
                        return True
                    self.logger.error(
                        "❌ Retry sendMessage failed for %s: status=%s body=%s",
                        chat_id,
                        retry_response.status_code,
                        retry_response.text,
                    )
                return False

            body = response.json()
            if not body.get("ok", False):
                self.logger.error("❌ Telegram API returned ok=false for %s: %s", chat_id, body)
                if parse_mode and "parse" in str(body).lower():
                    self.logger.info("Retrying sendMessage without parse_mode for chat_id=%s", chat_id)
                    payload.pop("parse_mode", None)
                    retry_response = requests.post(url, json=payload, timeout=5)
                    if retry_response.ok and retry_response.json().get("ok", False):
                        self.logger.info("✅ Sent message to %s after retry without parse_mode", chat_id)
                        return True
                    self.logger.error(
                        "❌ Retry sendMessage failed for %s: status=%s body=%s",
                        chat_id,
                        retry_response.status_code,
                        retry_response.text,
                    )
                return False

            self.logger.info(f"✅ Sent message to {chat_id}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to send Telegram message: {e}")
            return False

    def send_location(self, chat_id: int, latitude: float, longitude: float) -> bool:
        """Sends a geo location pin."""
        try:
            url = f"{self.api_url}/sendLocation"
            payload = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude}
            requests.post(url, json=payload, timeout=5)
            self.logger.info(f"✅ Sent location to {chat_id}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to send location: {e}")
            return False

    def send_video(self, chat_id: int, video_url: str, caption: str | None = None) -> bool:
        """Sends a video by URL (can also be used with MP4 clip of entrance)."""
        try:
            url = f"{self.api_url}/sendVideo"
            payload = {"chat_id": chat_id, "video": video_url}
            if caption:
                payload["caption"] = caption
            requests.post(url, json=payload, timeout=5)
            self.logger.info(f"✅ Sent video to {chat_id}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to send video: {e}")
            return False

    def ask_for_phone(self, chat_id: str):
        """Sends a button asking the user to share their phone number."""
        self.send_message(
            chat_id,
            "👋 Вітаємо! Щоб продовжити, поділіться своїм номером.",
            reply_markup=self.get_guest_keyboard(),
            parse_mode=None,
        )

    def send_admin_menu(self, chat_id: str):
        """Sends the admin-only reply keyboard with privileged options."""
        url = f"{self.api_url}/sendMessage"
        keyboard = {
            "keyboard": [
                [
                    {
                        "text": "📊 Статистика",
                    }
                ],
                [
                    {
                        "text": "📢 Розсилка",
                    }
                ],
            ],
            "one_time_keyboard": False,
            "resize_keyboard": True,
        }
        payload = {
            "chat_id": chat_id,
            "text": "🔐 Адмін меню",
            "reply_markup": keyboard,
        }
        requests.post(url, json=payload)

    def send_location_menu(self, chat_id: str):
        """Re-opens a lightweight keyboard with the location CTA after contact sharing."""
        self.send_main_menu(
            chat_id,
            'Натисніть "📍 Локація" щоб отримати адресу та "📞 Контактний телефон" для дзвінка.',
        )

    def send_main_menu(self, chat_id: str, text: str):
        """Shows the main menu keyboard without requesting contact."""
        self.send_message(chat_id, text, reply_markup=self.get_member_keyboard(), parse_mode=None)
