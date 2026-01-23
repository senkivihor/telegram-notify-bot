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
            "🎉 *Ура! Ваше замовлення вже готове!*\n\n"
            "Ми все підготували і чекаємо на вас.\n\n"
            "🏃 **Забігайте, коли зручно!**\n\n"
            "💡 *Порада:* Плануєте візит на самий ранок або під закриття? "
            "Краще наберіть нас заздалегідь, щоб ми точно не розминулися! 😉\n\n"
            "📞 **073 436 5788**\n\n"
            "⏰ **Наш графік:**\n"
            "• Пн, Пт: 10:00 – 19:00\n"
            "• Вт - Чт: 10:00 – 17:00\n"
            "• Сб: 11:00 – 14:00 (за попереднім дзвінком)\n"
            "• Нд: Вихідний"
        )
        # 3. Send
        if self.telegram.send_message(user.telegram_id, message):
            return "Success"
        else:
            return "Failed: Telegram API Error"
