from abc import ABC, abstractmethod
from typing import Optional

from core.models import UserDTO


class IUserRepository(ABC):
    """Interface (Contract) for User Data Access."""

    @abstractmethod
    def save_or_update_user(self, phone_number: str, name: str, telegram_id: str) -> None:
        """Creates a new user or updates the telegram_id if they already exist."""
        pass

    @abstractmethod
    def get_user_by_phone(self, phone_number: str) -> Optional[UserDTO]:
        """Finds a user by their phone number. Returns None if not found."""
        pass

    @abstractmethod
    def count_all_users(self) -> int:
        """Returns total number of users."""
        pass

    @abstractmethod
    def get_all_user_ids(self) -> list[str]:
        """Returns all telegram_id values for broadcast operations."""
        pass
