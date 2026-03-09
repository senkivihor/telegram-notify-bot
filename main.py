import logging
import os

from core.models import LocationInfo

from flask import Flask, Response, request

# Imports
from infrastructure.database import init_db
from infrastructure.repositories import SqlAlchemyFeedbackTaskRepository, SqlAlchemyUserRepository
from infrastructure.telegram_adapter import TelegramAdapter

from services.admin import AdminService
from services.ai_service import AIService, AI_DISCLAIMER, calculate_smart_price_range, format_business_time
from services.feedback import FeedbackButtons, FeedbackService
from services.location import LocationService
from services.notifier import NotificationService
from services.price_service import PriceService
from services.pricing_model import CONSUMABLES_FEE, DEPRECIATION_FEE, TAX_RATE, calculate_min_price

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelegramBot")
app = Flask(__name__)

# Config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
INTERNAL_KEY = os.getenv("INTERNAL_API_KEY")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
DEFAULT_INSTAGRAM_URL = "https://instagram.com/your-portfolio"
_INSTAGRAM_WARNING_EMITTED = False
MAPS_URL = os.getenv("MAPS_URL")
CRON_SECRET = os.getenv("CRON_SECRET", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

WAITING_FOR_AI_PROMPT = "WAITING_FOR_AI_PROMPT"
USER_STATES: dict[str, str] = {}
MAIN_MENU_BUTTONS = {
    "📊 Статистика",
    "📊 Stats",
    "📢 Розсилка",
    "📢 Broadcast",
    "💰 Ціни",
    "💰 Prices",
    "🪄 AI Оцінка вартості",
    "🧮 AI Калькулятор вартості",
    "📸 Наші роботи",
    "📸 Our Work",
    "📍 Локація",
    "Локація",
    "📅 Графік",
    "Графік",
    "📞 Контактний телефон",
    "Контактний телефон",
    "🆘 Допомога",
    "📞 Поділитись номером",
}


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def normalize_multiline_env(raw: str) -> str:
    # Strip wrapping quotes if present and convert escaped newlines to real newlines
    trimmed = raw.strip()
    if (trimmed.startswith('"') and trimmed.endswith('"')) or (trimmed.startswith("'") and trimmed.endswith("'")):
        trimmed = trimmed[1:-1]
    return trimmed.replace("\\n", "\n")


LOCATION_LAT = float(require_env("LOCATION_LAT"))
LOCATION_LON = float(require_env("LOCATION_LON"))
LOCATION_VIDEO_URL = require_env("LOCATION_VIDEO_URL")
LOCATION_SCHEDULE_TEXT = normalize_multiline_env(require_env("LOCATION_SCHEDULE_TEXT"))
LOCATION_CONTACT_PHONE = require_env("LOCATION_CONTACT_PHONE")
SUPPORT_CONTACT_USERNAME = os.getenv("SUPPORT_CONTACT_USERNAME", "@SupportHero")
ADMIN_IDS = {item.strip() for item in ADMIN_IDS_RAW.split(",") if item.strip()}


def get_instagram_url() -> str:
    """Return the configured Instagram URL, warning once when falling back to default."""
    global _INSTAGRAM_WARNING_EMITTED
    url = os.getenv("INSTAGRAM_URL")
    if url:
        return url
    if not _INSTAGRAM_WARNING_EMITTED:
        logger.warning("INSTAGRAM_URL missing; using default placeholder link.")
        _INSTAGRAM_WARNING_EMITTED = True
    return DEFAULT_INSTAGRAM_URL


# Init
init_db()
repo = SqlAlchemyUserRepository()
feedback_repo = SqlAlchemyFeedbackTaskRepository()
telegram = TelegramAdapter(TELEGRAM_TOKEN)
location_info = LocationInfo(
    latitude=LOCATION_LAT,
    longitude=LOCATION_LON,
    video_url=LOCATION_VIDEO_URL,
    schedule_text=LOCATION_SCHEDULE_TEXT,
    contact_phone=LOCATION_CONTACT_PHONE,
)
location_service = LocationService(telegram, location_info)
price_service = PriceService()
feedback_service = FeedbackService(repo, feedback_repo, telegram, admin_ids=ADMIN_IDS, maps_url=MAPS_URL)
_AI_SERVICE: AIService | None = None


def get_ai_service() -> AIService:
    global _AI_SERVICE
    if _AI_SERVICE is None:
        _AI_SERVICE = AIService(GEMINI_API_KEY)
    return _AI_SERVICE


def handle_welcome_flow(user_id: int | str):
    user = repo.get_user(str(user_id))
    if user:
        name = user.name or "друже"
        logger.info("✅ Welcome flow | User %s (Member) -> Showing member menu", user_id)
        telegram.send_message(
            user_id,
            f"🎉 З поверненням, {name}! Чим можемо допомогти?",
            reply_markup=telegram.get_member_keyboard(),
            parse_mode=None,
        )
    else:
        logger.info("📩 Welcome flow | User %s (New) -> Requesting phone", user_id)
        telegram.send_message(
            user_id,
            "👋 Вітаємо! Щоб почати роботу, будь ласка, поділіться номером.",
            reply_markup=telegram.get_guest_keyboard(),
            parse_mode=None,
        )

    return Response("OK", 200)


def instagram_button_markup(instagram_url: str) -> dict:
    return {"inline_keyboard": [[{"text": "Відкрити Instagram", "url": instagram_url}]]}


def get_admin_service() -> AdminService:
    return AdminService(repo, telegram)


def get_main_menu_markup(chat_id: int) -> dict:
    if str(chat_id) in ADMIN_IDS:
        return telegram.get_admin_keyboard()
    user = repo.get_user(str(chat_id))
    if user:
        return telegram.get_member_keyboard()
    return telegram.get_guest_keyboard()


# ==========================
#  TELEGRAM WEBHOOK
# ==========================
@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    data = request.json
    admin_service = get_admin_service()

    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]

        if "text" in msg:
            text = msg["text"].strip()
            logger.info(
                '📩 Received text from User %s | Text: "%s"', chat_id, text[:50] + ("..." if len(text) > 50 else "")
            )
            if USER_STATES.get(str(chat_id)) == WAITING_FOR_AI_PROMPT:
                if text.startswith("/") or text in MAIN_MENU_BUTTONS:
                    USER_STATES.pop(str(chat_id), None)
                else:
                    USER_STATES.pop(str(chat_id), None)
                    telegram.send_message(chat_id, "⏳ Аналізую запит...", parse_mode=None)
                    ai_result = get_ai_service().analyze_tailoring_task(text)
                    estimated_minutes = int(ai_result.get("estimated_minutes", 60))
                    task_summary = str(ai_result.get("task_summary") or "").strip() or "Опис не надано"
                    min_list_price = int(ai_result.get("min_list_price") or 0)
                    if estimated_minutes == 0:
                        if task_summary == "AI Unavailable":
                            telegram.send_message(
                                chat_id,
                                "⚠️ Вибачте, штучний інтелект тимчасово недоступний або не зміг обробити запит. Спробуйте пізніше або оберіть послугу з меню.",  # noqa: E501
                                reply_markup=get_main_menu_markup(chat_id),
                                parse_mode=None,
                            )
                            return Response("OK", 200)
                        client_message = (
                            "На жаль, ми не зможемо допомогти з цим замовленням. 😔\n\n"
                            "Ми **не працюємо** з:\n"
                            "• Натуральним хутром та товстою шкірою\n"
                            "• Головними уборами, сумками та рюкзаками\n"
                            "• Пошиттям нижньої білизни/купальників з нуля\n"
                            "• Складним перешивом в'язаних виробів (кетлювання, ловіння петель)\n\n"
                            "Дякуємо за розуміння! Якщо у вас є інші речі для ремонту чи пошиття — з радістю допоможемо. 🧵"  # noqa: E501
                        )
                        telegram.send_message(
                            chat_id,
                            client_message,
                            reply_markup=get_main_menu_markup(chat_id),
                            parse_mode="Markdown",
                        )
                        return Response("OK", 200)
                    pricing = calculate_min_price(estimated_minutes)
                    final_price = max(pricing["final_price"], min_list_price)
                    is_price_overridden = min_list_price > 0 and final_price != pricing["final_price"]
                    readable_time = format_business_time(estimated_minutes)
                    is_admin = str(chat_id) in ADMIN_IDS
                    if is_admin:
                        depreciation_fee = int(round(DEPRECIATION_FEE))
                        consumables_fee = int(round(CONSUMABLES_FEE))
                        tax_percent = int(round(TAX_RATE * 100))
                        price_list_note = (
                            f"📌 Мінімум за прайсом: {min_list_price} грн\n" if is_price_overridden else ""
                        )
                        response_text = (
                            "🧮 **AI Калькулятор вартості:**\n"
                            f"Завдання: *{task_summary}*\n"
                            f"Оцінений час: **{readable_time}**\n\n"
                            "💰 **Вартість:**\n"
                            f"- Робота (час): {pricing['labor']} грн\n"
                            f"- Амортизація та комунальні: {pricing['overhead'] + depreciation_fee} грн\n"
                            f"- Матеріали: {consumables_fee} грн\n"
                            f"- Податок ({tax_percent}%): {pricing['tax']} грн\n\n"
                            f"{price_list_note}"
                            f"🏆 **Мінімальна ціна для клієнта: {final_price} грн**"
                        )
                    else:
                        min_price, max_price = calculate_smart_price_range(
                            pricing["final_price"],
                            min_list_price,
                        )
                        response_text = (
                            "🪄 **Попередня оцінка AI:**\n"
                            f"Завдання: *{task_summary}*\n"
                            f"💰 Орієнтовна вартість: від {min_price} до {max_price} грн"
                        )
                        response_text += AI_DISCLAIMER
                    telegram.send_message(
                        chat_id,
                        response_text,
                        reply_markup=get_main_menu_markup(chat_id),
                        parse_mode="Markdown",
                    )
                    return Response("OK", 200)
            if text in {FeedbackButtons.yes, FeedbackButtons.no}:
                logger.info('📩 Feedback pickup response from User %s | Text: "%s"', chat_id, text)
                feedback_service.handle_pickup_response(str(chat_id), text)
                return Response("OK", 200)

            if text in {"1", "2", "3", "4", "5"}:
                logger.info("📩 Feedback rating from User %s | Score: %s", chat_id, text)
                feedback_service.handle_rating(str(chat_id), int(text))
                return Response("OK", 200)
            # Handle /help
            if text in {"/help", "🆘 Допомога"}:
                logger.info("📩 Received /help from User %s -> Sending support info", chat_id)
                telegram.send_message(
                    chat_id,
                    (
                        "🆘 Потрібна допомога?\n"
                        "Якщо у вас є питання щодо замовлення, звертайтеся напряму:\n"
                        f"👤 {SUPPORT_CONTACT_USERNAME}\n"
                        f"📞 {LOCATION_CONTACT_PHONE}"
                    ),
                    parse_mode=None,
                )
                return Response("OK", 200)

            # Handle /admin with RBAC
            if text == "/admin":
                if str(chat_id) in ADMIN_IDS:
                    logger.info("📩 Received /admin from User %s (Admin) -> Showing admin menu", chat_id)
                    telegram.send_admin_menu(chat_id)
                    return Response("OK", 200)

                logger.info("📩 Received /admin from User %s (Non-Admin) -> Redirecting to welcome flow", chat_id)
                telegram.send_message(chat_id, "🤔 Команда не розпізнана.")
                return handle_welcome_flow(chat_id)

            # Handle admin stats button
            if text in {"📊 Статистика", "📊 Stats"}:
                if str(chat_id) in ADMIN_IDS:
                    logger.info("📩 Admin stats requested by User %s", chat_id)
                    admin_service.send_stats(chat_id)
                    return Response("OK", 200)
                logger.info("📩 Non-admin stats attempt by User %s -> Redirecting", chat_id)
                telegram.send_message(chat_id, "Повертаємо вас до головного меню 🧵")
                telegram.ask_for_phone(chat_id)
                return Response("OK", 200)

            # Handle broadcast button
            if text in {"📢 Розсилка", "📢 Broadcast"}:
                if str(chat_id) in ADMIN_IDS:
                    logger.info("📩 Admin broadcast requested by User %s", chat_id)
                    admin_service.send_broadcast_instructions(chat_id)
                    return Response("OK", 200)
                logger.info("📩 Non-admin broadcast attempt by User %s -> Redirecting", chat_id)
                telegram.send_message(chat_id, "Повертаємо вас до головного меню 🧵")
                telegram.ask_for_phone(chat_id)
                return Response("OK", 200)

            # Handle /broadcast command
            if text.startswith("/broadcast"):
                if str(chat_id) not in ADMIN_IDS:
                    logger.info("📩 Non-admin /broadcast attempt by User %s -> Redirecting", chat_id)
                    telegram.send_message(chat_id, "Повертаємо вас до головного меню 🛍️")
                    telegram.ask_for_phone(chat_id)
                    return Response("OK", 200)

                broadcast_text = text[len("/broadcast") :].strip()
                logger.info(
                    '📩 Admin broadcast command by User %s | Text: "%s"',
                    chat_id,
                    broadcast_text[:50] + ("..." if len(broadcast_text) > 50 else ""),
                )
                admin_service.broadcast(chat_id, broadcast_text)
                return Response("OK", 200)

            # A. Handle "Deep Link" or Start
            # Format: /start ORD-123
            if text.startswith("/start"):
                logger.info("📩 Received /start from User %s -> Triggering welcome flow", chat_id)
                return handle_welcome_flow(chat_id)

            # B. Handle portfolio / Instagram showcase
            if text in {"📸 Наші роботи", "📸 Our Work"}:
                instagram_url = get_instagram_url()
                logger.info("📩 Portfolio requested by User %s -> Sending Instagram link", chat_id)
                telegram.send_message(
                    chat_id,
                    ("👀 *Подивіться наше портфоліо!*\n\n" "Ось наші останні роботи:\n" f"{instagram_url}"),
                    reply_markup=instagram_button_markup(instagram_url),
                )
                return Response("OK", 200)

            # C. Handle Location request
            if text in {"📍 Локація", "Локація", "/location"}:
                logger.info("📩 Location requested by User %s", chat_id)
                location_service.send_location_details(chat_id)
                return Response("OK", 200)

            # D. Handle price list
            if text in {"💰 Ціни", "💰 Prices"}:
                prices_text = price_service.get_formatted_prices()
                logger.info("📩 Prices requested by User %s", chat_id)
                telegram.send_message(chat_id, prices_text, parse_mode="Markdown")
                return Response("OK", 200)

            # D2. Handle AI estimator (client)
            if text == "🪄 AI Оцінка вартості":
                logger.info("📩 AI estimator requested by User %s", chat_id)
                USER_STATES[str(chat_id)] = WAITING_FOR_AI_PROMPT
                telegram.send_message(
                    chat_id,
                    (
                        "🧵 Опишіть своїми словами, що потрібно зробити? "
                        "(Наприклад: 'Треба вкоротити джинси, але зберегти оригінальний шов' "
                        "або 'Замінити блискавку на зимовій куртці')."
                    ),
                    parse_mode=None,
                )
                return Response("OK", 200)

            # D3. Handle AI cost calculator (admin)
            if text == "🧮 AI Калькулятор вартості":
                if str(chat_id) in ADMIN_IDS:
                    logger.info("📩 AI cost calculator requested by Admin %s", chat_id)
                    USER_STATES[str(chat_id)] = WAITING_FOR_AI_PROMPT
                    telegram.send_message(
                        chat_id,
                        (
                            "🧵 Опишіть своїми словами, що потрібно зробити? "
                            "(Наприклад: 'Треба вкоротити джинси, але зберегти оригінальний шов' "
                            "або 'Замінити блискавку на зимовій куртці')."
                        ),
                        parse_mode=None,
                    )
                    return Response("OK", 200)
                logger.info("📩 Non-admin AI cost calculator attempt by User %s", chat_id)
                telegram.send_message(chat_id, "Повертаємо вас до головного меню 🧵")
                telegram.ask_for_phone(chat_id)
                return Response("OK", 200)

            # E. Handle schedule button
            if text in {"📅 Графік", "Графік"}:
                logger.info("📩 Schedule requested by User %s", chat_id)
                telegram.send_message(chat_id, LOCATION_SCHEDULE_TEXT, parse_mode=None)
                return Response("OK", 200)

            # F. Handle contact phone
            if text in {"📞 Контактний телефон", "Контактний телефон"}:
                logger.info("📩 Contact phone requested by User %s", chat_id)
                telegram.send_message(chat_id, f"📞 {LOCATION_CONTACT_PHONE}", parse_mode=None)
                return Response("OK", 200)

        # B. Handle "Shared Phone Number"
        elif "contact" in msg:
            contact = msg["contact"]
            phone_number = contact["phone_number"]
            # Standardize phone format
            if not phone_number.startswith("+"):
                phone_number = "+" + phone_number

            name = contact.get("first_name", "Client")

            instagram_url = get_instagram_url()

            # Save User to DB
            repo.save_or_update_user(phone_number=phone_number, name=name, telegram_id=str(chat_id))
            logger.info("✅ Saved user contact | User %s | Phone: %s", chat_id, phone_number)

            # Confirm and hide contact keyboard
            telegram.send_message(
                chat_id,
                (
                    "✅ *Дякуємо, зберегли ваш номер!*\n\n"
                    "Коли замовлення буде готове, бот надішле сповіщення тут.\n"
                    "Щоб не пропустити оновлення, збережіть цей чат.\n\n"
                    "Поки чекаєте, зазирніть у наш Instagram 👇\n"
                    f"{instagram_url}"
                ),
                reply_markup=instagram_button_markup(instagram_url),
            )

            # Re-open reply keyboard so location CTA stays visible
            telegram.send_location_menu(chat_id)

    return Response("OK", 200)


# ==========================
#  INTERNAL TRIGGER API
# ==========================
@app.route("/trigger-notification", methods=["POST"])
def trigger():
    key = request.headers.get("X-Internal-API-Key")
    if not key or key != INTERNAL_KEY:
        return Response("Unauthorized", 403)

    data = request.json or {}
    phone_number = data.get("phone_number") or data.get("phone")
    service = NotificationService(
        repo,
        telegram,
        schedule_text=LOCATION_SCHEDULE_TEXT,
        contact_phone=LOCATION_CONTACT_PHONE,
        feedback_service=feedback_service,
    )
    result = service.notify_order_ready(
        phone_number=phone_number,
        order_id=data.get("order_id"),
        items=data.get("items", []),
    )

    return {"status": result}, 200


# ==========================================
# ➕ ADD THIS NEW SECTION HERE
# ==========================================
@app.route("/health", methods=["GET"])
def health_check():
    """Lightweight endpoint for UptimeRobot to keep the bot awake."""
    return "OK", 200


@app.route("/tasks/check-feedback", methods=["GET"])
def check_feedback_tasks():
    token = request.args.get("token")
    if not token or token != CRON_SECRET:
        return Response("Forbidden", 403)

    processed = feedback_service.process_queue()
    return {"processed": processed}, 200


# === RUN SERVER ===
if __name__ == "__main__":
    # Use the PORT environment variable if available, otherwise 5000
    port = int(os.environ.get("PORT", 5000))
    # '0.0.0.0' is required for Docker containers to be accessible
    app.run(host="0.0.0.0", port=port)
