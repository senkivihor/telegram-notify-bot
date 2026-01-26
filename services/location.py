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
        self.telegram.send_message(chat_id, f"{self.location_info.schedule_text}{contact_line}")
