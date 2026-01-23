from dataclasses import dataclass


@dataclass
class UserDTO:
    phone_number: str
    name: str
    telegram_id: str
