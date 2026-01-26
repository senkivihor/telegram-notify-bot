from urllib.parse import quote_plus

from core.models import LocationInfo

from infrastructure.telegram_adapter import TelegramAdapter


class LocationService:
    def __init__(self, telegram: TelegramAdapter, location_info: LocationInfo):
        self.telegram = telegram
        self.location_info = location_info

    def send_location_details(self, chat_id: int) -> None:
        # Send map pin
        self.telegram.send_location(
            chat_id=chat_id,
            latitude=self.location_info.latitude,
            longitude=self.location_info.longitude,
        )

        # Send entrance video (or photo-compatible video) for visual guidance
        self.telegram.send_video(
            chat_id=chat_id,
            video_url=self.location_info.video_url,
            caption="Ось наш вхід, щоб легше знайти!",
        )

        # Send schedule text + phone
        contact_line = f"\n\n📞 {self.location_info.contact_phone}" if self.location_info.contact_phone else ""
        schedule_text = f"{self.location_info.schedule_text}{contact_line}"
        message_text = f"{schedule_text}\n\nКорисні дії:"
        map_url = f"https://www.google.com/maps?q={self.location_info.latitude},{self.location_info.longitude}"
        tel_url = f"tel:{self.location_info.contact_phone}" if self.location_info.contact_phone else None
        schedule_share_url = f"https://t.me/share/url?text={quote_plus(schedule_text)}"

        buttons = [[{"text": "📍 Відкрити на мапі", "url": map_url}]]
        if tel_url:
            buttons.append([{"text": "📞 Подзвонити", "url": tel_url}])

        buttons.append([{"text": "⏰ Графік", "url": schedule_share_url}])

        self.telegram.send_message_with_buttons(chat_id, message_text, buttons)
