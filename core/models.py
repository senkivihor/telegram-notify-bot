from dataclasses import dataclass
from typing import Optional


@dataclass
class UserDTO:
    phone_number: str
    name: str
    telegram_id: str
