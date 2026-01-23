from infrastructure.repositories import SqlAlchemyUserRepository
from infrastructure.telegram_adapter import TelegramAdapter


class NotificationService:
    def __init__(self, repo: SqlAlchemyUserRepository, telegram: TelegramAdapter):
        self.repo = repo
        self.telegram = telegram

    def notify_order_ready(self, phone_number: str, order_id: str, items: list) -> str:
        # 1. Find user by phone
        user = self.repo.get_user_by_phone(phone_number)

        if not user:
            return "Failed: User not found (Not subscribed to bot)"

        # 2. Format Message
        message = (
            f"📦 *Order #{order_id} is Ready!*\n\n" f"Items: {', '.join(items)}\n" "📍 Ready for pickup at the counter."
        )

        # 3. Send
        if self.telegram.send_message(user.telegram_id, message):
            return "Success"
        else:
            return "Failed: Telegram API Error"
