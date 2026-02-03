from dataclasses import dataclass
from datetime import datetime
from enum import Enum


@dataclass
class UserDTO:
    phone_number: str
    name: str
    telegram_id: str
    id: int | None = None


class FeedbackStatus(str, Enum):
    PENDING = "PENDING"
    ASKING_PICKUP = "ASKING_PICKUP"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass
class FeedbackTaskDTO:
    id: int
    user_id: int
    created_at: datetime
    scheduled_for: datetime
    status: FeedbackStatus
    pickup_attempts: int


@dataclass(frozen=True)
class LocationInfo:
    latitude: float
    longitude: float
    video_url: str
    schedule_text: str
    contact_phone: str
