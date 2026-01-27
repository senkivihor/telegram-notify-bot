from core.models import LocationInfo

from services.location import LocationService


class DummyTelegram:
    def __init__(self):
        self.sent_location = None
        self.sent_video = None
        self.sent_message = None

    def send_location(self, chat_id, latitude, longitude):
        self.sent_location = (chat_id, latitude, longitude)
        return True

    def send_video(self, chat_id, video_url, caption=None):
        self.sent_video = (chat_id, video_url, caption)
        return True

    def send_message(self, chat_id, text, reply_markup=None):
        self.sent_message = (chat_id, text, reply_markup)
        return True


def test_location_flow_sends_pin_video_and_buttons():
    info = LocationInfo(
        latitude=49.1,
        longitude=24.5,
        video_url="https://example.com/video.mp4",
        schedule_text="⏰ Графік: 10-19",
        contact_phone="+380000000000",
    )
    telegram = DummyTelegram()
    service = LocationService(telegram, info)

    service.send_location_details(chat_id=123)

    assert telegram.sent_location == (123, 49.1, 24.5)
    assert telegram.sent_video == (123, "https://example.com/video.mp4", "Ось наш вхід, щоб легше знайти!")

    assert telegram.sent_message is not None
    chat_id, text, reply_markup = telegram.sent_message
    assert chat_id == 123
    assert "⏰" in text and "+380000000000" in text
    assert "Наша локація та контакти" in text
