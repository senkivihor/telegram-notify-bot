import logging


import requests


class TelegramAdapter:
    def __init__(self, bot_token: str):
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger("TelegramAdapter")

    def send_message(self, chat_id: str, text: str, reply_markup: dict | None = None):
        """Sends a standard text message. Optionally attach reply_markup (e.g., remove keyboard)."""
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
            if reply_markup:
                payload["reply_markup"] = reply_markup
            requests.post(url, json=payload, timeout=5)
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
        url = f"{self.api_url}/sendMessage"
        keyboard = {
            "keyboard": [
                [
                    {
                        "text": "📱 Поділитися номером для замовлення",
                        "request_contact": True,
                    }
                ],
                [
                    {
                        "text": "📍 Локація та контакти",
                    }
                ],
            ],
            "one_time_keyboard": True,
            "resize_keyboard": True,
        }
        payload = {
            "chat_id": chat_id,
            "text": "👋 Вітаємо! Натисніть кнопку нижче, щоб прив'язати ваш акаунт.",
            "reply_markup": keyboard,
        }
        requests.post(url, json=payload)

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
        url = f"{self.api_url}/sendMessage"
        keyboard = {
            "keyboard": [
                [
                    {
                        "text": "📍 Локація та контакти",
                    }
                ],
            ],
            "one_time_keyboard": False,
            "resize_keyboard": True,
        }
        payload = {
            "chat_id": chat_id,
            "text": 'Натисніть "Локація та контакти" щоб отримати адресу, графік та контактний телефон.',
            "reply_markup": keyboard,
        }
        requests.post(url, json=payload)
