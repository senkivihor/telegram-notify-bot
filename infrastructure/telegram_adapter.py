import logging


import requests


class TelegramAdapter:
    def __init__(self, bot_token: str):
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger("TelegramAdapter")

    @staticmethod
    def _truncate_text(text: str, limit: int = 50) -> str:
        if not text:
            return ""
        return f"{text[:limit]}..." if len(text) > limit else text

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
                    {"text": "🪄 AI Оцінка вартості"},
                ],
                [
                    {"text": "📸 Наші роботи"},
                    {"text": "📍 Локація"},
                ],
                [
                    {"text": "📅 Графік"},
                    {"text": "📞 Контактний телефон"},
                ],
                [
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
                    {"text": "🪄 AI Оцінка вартості"},
                ],
                [
                    {"text": "📸 Наші роботи"},
                    {"text": "📍 Локація"},
                ],
                [
                    {"text": "📅 Графік"},
                    {"text": "📞 Контактний телефон"},
                ],
                [
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

        text_snippet = self._truncate_text(text)
        keyboard_present = "Yes" if reply_markup else "No"

        try:
            response = requests.post(url, json=payload, timeout=5)
            # Telegram returns HTTP 200 even when ok=false, so check both
            if not response.ok:
                self.logger.error(
                    '❌ Telegram sendMessage failed | chat_id=%s | status=%s | text="%s" | keyboard=%s | body=%s',
                    chat_id,
                    response.status_code,
                    text_snippet,
                    keyboard_present,
                    response.text,
                )
                if parse_mode and response.status_code == 400 and "parse" in response.text.lower():
                    self.logger.info("Retrying sendMessage without parse_mode for chat_id=%s", chat_id)
                    payload.pop("parse_mode", None)
                    retry_response = requests.post(url, json=payload, timeout=5)
                    if retry_response.ok and retry_response.json().get("ok", False):
                        self.logger.info(
                            '✅ Sent to %s | Text: "%s" | Keyboard: %s | Retry: Yes',
                            chat_id,
                            text_snippet,
                            keyboard_present,
                        )
                        return True
                    self.logger.error(
                        '❌ Retry sendMessage failed | chat_id=%s | status=%s | text="%s" | keyboard=%s | body=%s',
                        chat_id,
                        retry_response.status_code,
                        text_snippet,
                        keyboard_present,
                        retry_response.text,
                    )
                return False

            body = response.json()
            if not body.get("ok", False):
                self.logger.error(
                    '❌ Telegram API ok=false | chat_id=%s | text="%s" | keyboard=%s | body=%s',
                    chat_id,
                    text_snippet,
                    keyboard_present,
                    body,
                )
                if parse_mode and "parse" in str(body).lower():
                    self.logger.info("Retrying sendMessage without parse_mode for chat_id=%s", chat_id)
                    payload.pop("parse_mode", None)
                    retry_response = requests.post(url, json=payload, timeout=5)
                    if retry_response.ok and retry_response.json().get("ok", False):
                        self.logger.info(
                            '✅ Sent to %s | Text: "%s" | Keyboard: %s | Retry: Yes',
                            chat_id,
                            text_snippet,
                            keyboard_present,
                        )
                        return True
                    self.logger.error(
                        '❌ Retry sendMessage failed | chat_id=%s | status=%s | text="%s" | keyboard=%s | body=%s',
                        chat_id,
                        retry_response.status_code,
                        text_snippet,
                        keyboard_present,
                        retry_response.text,
                    )
                return False

            self.logger.info(
                '✅ Sent to %s | Text: "%s" | Keyboard: %s',
                chat_id,
                text_snippet,
                keyboard_present,
            )
            return True
        except Exception:
            self.logger.error(
                '❌ Failed to send Telegram message | chat_id=%s | text="%s" | keyboard=%s',
                chat_id,
                text_snippet,
                keyboard_present,
                exc_info=True,
            )
            return False

    def send_location(self, chat_id: int, latitude: float, longitude: float) -> bool:
        """Sends a geo location pin."""
        try:
            url = f"{self.api_url}/sendLocation"
            payload = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude}
            requests.post(url, json=payload, timeout=5)
            self.logger.info("✅ Sent location to %s | Data: %s,%s", chat_id, latitude, longitude)
            return True
        except Exception:
            self.logger.error("❌ Failed to send location | chat_id=%s", chat_id, exc_info=True)
            return False

    def send_video(self, chat_id: int, video_url: str, caption: str | None = None) -> bool:
        """Sends a video by URL (can also be used with MP4 clip of entrance)."""
        try:
            url = f"{self.api_url}/sendVideo"
            payload = {"chat_id": chat_id, "video": video_url}
            if caption:
                payload["caption"] = caption
            requests.post(url, json=payload, timeout=5)
            self.logger.info(
                '✅ Sent video to %s | Url: "%s"',
                chat_id,
                self._truncate_text(video_url),
            )
            return True
        except Exception:
            self.logger.error("❌ Failed to send video | chat_id=%s", chat_id, exc_info=True)
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
        keyboard = self.get_admin_keyboard()
        payload = {
            "chat_id": chat_id,
            "text": "🔐 Адмін меню",
            "reply_markup": keyboard,
        }
        requests.post(url, json=payload)
        self.logger.info('✅ Sent to %s | Text: "%s" | Keyboard: Yes', chat_id, "🔐 Адмін меню")

    @staticmethod
    def get_admin_keyboard() -> dict:
        return {
            "keyboard": [
                [
                    {
                        "text": "📊 Статистика",
                    }
                ],
                [
                    {
                        "text": "🧮 AI Калькулятор собівартості",
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

    def send_location_menu(self, chat_id: str):
        """Re-opens a lightweight keyboard with the location CTA after contact sharing."""
        self.send_main_menu(
            chat_id,
            'Натисніть "📍 Локація" щоб отримати адресу та "📞 Контактний телефон" для дзвінка.',
        )

    def send_main_menu(self, chat_id: str, text: str):
        """Shows the main menu keyboard without requesting contact."""
        self.send_message(chat_id, text, reply_markup=self.get_member_keyboard(), parse_mode=None)
