from infrastructure.repositories import SqlAlchemyUserRepository
from infrastructure.telegram_adapter import TelegramAdapter


class AdminService:
    def __init__(self, repo: SqlAlchemyUserRepository, telegram: TelegramAdapter):
        self.repo = repo
        self.telegram = telegram

    def send_stats(self, chat_id: int) -> None:
        count = self.repo.count_all_users()
        message = (
            "📊 **Bot Statistics**\n\n"
            f"👥 Total Users: **{count}**\n"
            f"✅ Active: {count} (Assuming all are active for now)"
        )
        self.telegram.send_message(chat_id, message)

    def send_broadcast_instructions(self, chat_id: int) -> None:
        message = (
            "⚠️ **Панель керування розсилкою**\n\n"
            "Щоб надіслати повідомлення ВСІМ користувачам, використайте команду `/broadcast` та ваш текст.\n\n"
            "**Шаблони для копіювання:**\n\n"
            "1️⃣ **Нові можливості:**\n"
            "`/broadcast 🚀 **Оновлення:** Додали нові фічі! Напишіть /start, щоб оновити меню.`\n\n"
            "2️⃣ **Терміново/Закриття:**\n"
            "`/broadcast 🕒 **Повідомлення:** Сьогодні зачиняємось трохи раніше. Будь ласка, завітайте до 17:00!`"
        )
        self.telegram.send_message(chat_id, message)

    def broadcast(self, chat_id: int, text: str) -> None:
        if not text.strip():
            self.send_broadcast_instructions(chat_id)
            return

        user_ids = self.repo.get_all_user_ids()
        success_count = 0
        fail_count = 0

        for user_id in user_ids:
            try:
                sent = self.telegram.send_message(str(user_id), text)
                if sent:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception:
                fail_count += 1
                continue

        report = "✅ Broadcast complete. " f"Sent to {success_count} users. Failed/Blocked: {fail_count}."
        self.telegram.send_message(chat_id, report)
