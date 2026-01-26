from dataclasses import dataclass


@dataclass
class UserDTO:
    phone_number: str
    name: str
    telegram_id: str


@dataclass(frozen=True)
class LocationInfo:
    latitude: float
    longitude: float
    video_url: str
    schedule_text: str
    contact_phone: str
