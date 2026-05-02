#!/usr/bin/env python3
"""
Vertex SACCO Bot

A polished Telegram bot with a professional home keyboard, inline menus,
sample SACCO content, working branch links, and admin reply routing.
"""

from __future__ import annotations

import asyncio
from collections import deque
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
import threading
from typing import Any, Optional
from urllib import error, request
from datetime import datetime

from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PicklePersistence,
    filters,
)


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "google-service-account.json").strip()
CONTENT_FILE = "content.json"
SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("vertex_sacco_bot")

CONTENT = {}
def load_content():
    global CONTENT
    try:
        # Determine path relative to the script location
        base_path = os.path.dirname(os.path.abspath(__file__))
        abs_path = os.path.join(base_path, CONTENT_FILE)
        
        if os.path.exists(abs_path):
            with open(abs_path, 'r', encoding='utf-8') as f:
                CONTENT = json.load(f)
                logger.info("Content configuration loaded successfully from %s.", abs_path)
        else:
            logger.error("CRITICAL: Content file not found at %s. AI will use hardcoded defaults.", abs_path)
    except Exception as e:
        logger.error("FAILED to load content.json: %s", e)


BRAND_EMOJI = "💚"

BTN_AI = "💡 AI Assistant"
BTN_FAQ = "❓ Member FAQ"
BTN_SERVICES = "🟢 Services"
BTN_PROFILE = "🏢 Sacco Profile"
BTN_BRANCHES = "📍 Branches"
BTN_ADMIN = "📞 Support"
BTN_FEEDBACK = "⭐ Feedback"
BTN_CLEAR = "🔄 Clear Chat"
BTN_ADMIN_PANEL = "🛠 Admin Dashboard"
BTN_SUPPORT_SEND = "✅ Send Message"
BTN_SUPPORT_CANCEL = "❌ Cancel Message"
BTN_MAIN_MENU = "🟢 Main Menu"

STATE_REG_NAME = "reg_name"
STATE_REG_PHONE = "reg_phone"
STATE_CONTACT_ADMIN = "contact_admin"
STATE_FEEDBACK = "feedback"
STATE_GET_FILE_ID = "get_file_id"
SUPPORT_DRAFT_KEY = "support_draft"
IS_REGISTERED_KEY = "is_registered"
REG_DATA_NAME = "reg_data_name"

ADMIN_REPLY_MAP_KEY = "admin_reply_map"
CHAT_MEMORY_KEY = "chat_memory"
MAX_MEMORY_MESSAGES = 20
TELEGRAM_REQUEST_RETRIES = 1
TELEGRAM_RETRY_DELAY_SECONDS = 1.0
TELEGRAM_CONNECT_TIMEOUT = 20.0
TELEGRAM_READ_TIMEOUT = 30.0
TELEGRAM_WRITE_TIMEOUT = 30.0
TELEGRAM_POOL_TIMEOUT = 30.0
TELEGRAM_MEDIA_WRITE_TIMEOUT = 60.0
TELEGRAM_POLL_TIMEOUT = 30.0
RENDER_HOST = "0.0.0.0"
RENDER_DEFAULT_PORT = 10000

def home_keyboard(user_id: Optional[int] = None) -> ReplyKeyboardMarkup:
    buttons = [
        [BTN_AI, BTN_FAQ],
        [BTN_SERVICES, BTN_BRANCHES],
        [BTN_PROFILE, BTN_ADMIN],
        [BTN_FEEDBACK],
    ]
    if str(user_id) == ADMIN_ID:
        buttons.append([BTN_ADMIN_PANEL])

    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="💚 Ask anything about Vertex SACCO",
    )


def support_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [BTN_SUPPORT_SEND, BTN_SUPPORT_CANCEL],
            [BTN_MAIN_MENU],
        ],
        resize_keyboard=True,
        is_persistent=False,
        input_field_placeholder="Write your support message, then tap Send",
    )


def phone_registration_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Share Contact", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def back_home_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🟢 Main Menu", callback_data="nav_home")]])


def home_and_contact_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📞 Contact Admin", callback_data="menu_admin")],
            [InlineKeyboardButton("🟢 Main Menu", callback_data="nav_home")],
        ]
    )


def faq_inline() -> InlineKeyboardMarkup:
    rows = []
    for key, data in CONTENT.get("faq", {}).items():
        question = data[0]
        rows.append([InlineKeyboardButton(f"🧾 {question}", callback_data=key)])
    rows.append([InlineKeyboardButton("🟢 Main Menu", callback_data="nav_home")])
    return InlineKeyboardMarkup(rows)


def admin_dashboard_inline() -> InlineKeyboardMarkup:
    sheet_id = GOOGLE_SHEET_ID
    if "spreadsheets/d/" in sheet_id:
        sheet_url = sheet_id
    else:
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
    
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 Registration Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("🆔 Get Telegram File ID", callback_data="admin_get_file_id")],
            [InlineKeyboardButton("📄 View Google Sheet", url=sheet_url)],
            [InlineKeyboardButton("🟢 Main Menu", callback_data="nav_home")],
        ]
    )


def services_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💰 Savings Services", callback_data="service_savings")],
            [InlineKeyboardButton("📈 Loan Services", callback_data="service_loans")],
            [InlineKeyboardButton("💻 Digital Services", callback_data="service_digital")],
            [InlineKeyboardButton("🤝 Member Support", callback_data="service_support")],
            [InlineKeyboardButton("🟢 Main Menu", callback_data="nav_home")],
        ]
    )


def branches_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🏢 Main Office", callback_data="branch_hq")],
            [InlineKeyboardButton("👨‍💼 Member Desk", callback_data="branch_westlands")],
            [InlineKeyboardButton("✅ Verification Office", callback_data="branch_mombasa")],
            [InlineKeyboardButton("🟢 Main Menu", callback_data="nav_home")],
        ]
    )


def branch_actions(branch_key: str) -> InlineKeyboardMarkup:
    branch = CONTENT.get("branches", {}).get(branch_key, {})
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📍 Open in Maps", url=branch["maps_url"])],
            [InlineKeyboardButton("📍 Branches", callback_data="menu_branches")],
            [InlineKeyboardButton("🟢 Main Menu", callback_data="nav_home")],
        ]
    )


def feedback_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("1⭐", callback_data="feedback|1"),
                InlineKeyboardButton("2⭐", callback_data="feedback|2"),
                InlineKeyboardButton("3⭐", callback_data="feedback|3"),
                InlineKeyboardButton("4⭐", callback_data="feedback|4"),
                InlineKeyboardButton("5⭐", callback_data="feedback|5"),
            ],
            [InlineKeyboardButton("🟢 Main Menu", callback_data="nav_home")],
        ]
    )


def get_admin_reply_map(context: ContextTypes.DEFAULT_TYPE) -> dict[int, int]:
    reply_map = context.bot_data.get(ADMIN_REPLY_MAP_KEY)
    if reply_map is None:
        reply_map = {}
        context.bot_data[ADMIN_REPLY_MAP_KEY] = reply_map
    return reply_map


def get_chat_memory(context: ContextTypes.DEFAULT_TYPE) -> deque[dict[str, str]]:
    memory = context.user_data.get(CHAT_MEMORY_KEY)
    if memory is None:
        memory = deque(maxlen=MAX_MEMORY_MESSAGES)
        context.user_data[CHAT_MEMORY_KEY] = memory
    return memory


def clear_support_draft(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(SUPPORT_DRAFT_KEY, None)


def set_support_draft(context: ContextTypes.DEFAULT_TYPE, message: Message) -> dict[str, object]:
    draft = {
        "chat_id": message.chat_id,
        "message_id": message.message_id,
        "summary": summarize_message(message),
        "has_media": any(
            [
                bool(message.photo),
                bool(message.video),
                bool(message.document),
                bool(message.audio),
                bool(message.voice),
                bool(message.sticker),
                bool(message.location),
                bool(message.contact),
            ]
        ),
    }
    context.user_data[SUPPORT_DRAFT_KEY] = draft
    return draft


def get_support_draft(context: ContextTypes.DEFAULT_TYPE) -> Optional[dict[str, object]]:
    draft = context.user_data.get(SUPPORT_DRAFT_KEY)
    if isinstance(draft, dict):
        return draft
    return None


def remember_message(context: ContextTypes.DEFAULT_TYPE, role: str, text: str) -> None:
    clean_text = " ".join(text.split()).strip()
    if not clean_text:
        return
    memory = get_chat_memory(context)
    memory.append({"role": role, "text": clean_text})


def memory_text(memory: deque[dict[str, str]]) -> str:
    return " | ".join(f"{item['role']}: {item['text']}" for item in memory)


def load_google_credentials() -> Optional[Credentials]:
    """Loads Google service account credentials from env var or local file."""
    try:
        if GOOGLE_SERVICE_ACCOUNT_JSON:
            info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
            return Credentials.from_service_account_info(info, scopes=SHEETS_SCOPES)
        if os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
            return Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SHEETS_SCOPES)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        logger.error("Failed to load Google service account credentials: %s", exc)
    return None


async def save_to_google_sheets(name: str, phone: str, user_id: int, username: str) -> bool:
    if not GOOGLE_SHEET_ID:
        logger.warning("Google Sheet ID missing.")
        return False

    def _append():
        try:
            creds = load_google_credentials()
            if not creds:
                logger.error("Google credentials missing. Registration not saved.")
                return False
            
            client_email = getattr(creds, "service_account_email", "unknown email")
            client = gspread.authorize(creds)
            
            sheet_id = GOOGLE_SHEET_ID
            if "spreadsheets/d/" in sheet_id:
                sheet_id = sheet_id.split("spreadsheets/d/")[1].split("/")[0]
            
            spreadsheet = client.open_by_key(sheet_id)
            
            # Robust worksheet selection for 'Join Data'
            try:
                sheet = spreadsheet.worksheet("Join Data")
            except gspread.exceptions.WorksheetNotFound:
                try:
                    sheet = spreadsheet.worksheet("Sheet 1")
                except gspread.exceptions.WorksheetNotFound:
                    sheet = spreadsheet.get_worksheet(0)

            logger.info("Saving registration for %s to worksheet: %s", user_id, sheet.title)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Matches your headers: timestamp | telegram_user_id | full_name | phone_number | telegram_username | registration_status
            sheet.append_row([
                timestamp, 
                str(user_id), 
                name, 
                phone, 
                f"@{username}" if username else "N/A", 
                "registered"
            ],
            value_input_option="USER_ENTERED")
            return True
        except gspread.exceptions.SpreadsheetNotFound:
            logger.error("404 Error: Google Sheet not found. Ensure %s has 'Editor' access to sheet ID: %s", client_email, sheet_id)
            return False
        except gspread.exceptions.APIError as e:
            logger.error("API Error: %s. Check if %s has permission.", e, client_email)
            return False
        except Exception as e:
            logger.error("Unexpected error saving to Google Sheets: %s", e)
            return False

    return await asyncio.to_thread(_append)


async def save_feedback_to_sheet(user_id: int, name: str, rating: str = "N/A", comment: str = "N/A") -> bool:
    """Saves feedback data to a dedicated 'Feedback' worksheet."""
    if not GOOGLE_SHEET_ID:
        return False

    def _work():
        try:
            creds = load_google_credentials()
            if not creds:
                return False
            client = gspread.authorize(creds)
            
            sheet_id = GOOGLE_SHEET_ID
            if "spreadsheets/d/" in sheet_id:
                sheet_id = sheet_id.split("spreadsheets/d/")[1].split("/")[0]
            
            spreadsheet = client.open_by_key(sheet_id)
            
            # Try to find a tab named 'Feedback'. 
            # If not found, try to access the second worksheet (Sheet 2)
            try:
                worksheet = spreadsheet.worksheet("Feedback")
            except gspread.exceptions.WorksheetNotFound:
                try:
                    worksheet = spreadsheet.get_worksheet(1)  # Index 1 is the second sheet
                except Exception:
                    # Create it if it doesn't exist at all
                    worksheet = spreadsheet.add_worksheet(title="Feedback", rows="1000", cols="6")
                    worksheet.append_row(["Timestamp", "User ID", "Full Name", "Rating", "Comment"])
                    # Format the header
                    worksheet.format("A1:E1", {"textFormat": {"bold": True}, "backgroundColor": {"green": 0.8, "red": 0.2, "blue": 0.2}})

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            worksheet.append_row([
                timestamp,
                str(user_id),
                name,
                rating,
                comment
            ],
            value_input_option="USER_ENTERED")
            return True
        except Exception as e:
            logger.error("Error saving feedback: %s", e)
            return False

    return await asyncio.to_thread(_work)


async def get_total_registrations() -> int:
    if not GOOGLE_SHEET_ID:
        return 0

    def _read():
        try:
            creds = load_google_credentials()
            if not creds:
                return 0
            client = gspread.authorize(creds)
            
            sheet_id = GOOGLE_SHEET_ID
            if "spreadsheets/d/" in sheet_id:
                sheet_id = sheet_id.split("spreadsheets/d/")[1].split("/")[0]
            
            spreadsheet = client.open_by_key(sheet_id)
            sheet = spreadsheet.get_worksheet(0)
            # Subtract 1 for the header row
            data = sheet.get_all_values()
            return max(0, len(data) - 1)
        except Exception as e:
            logger.error("Error fetching stats: %s", e)
            return 0

    return await asyncio.to_thread(_read)


def summarize_message(message: Message) -> str:
    if message.text:
        return message.text
    if message.caption:
        return message.caption
    if message.photo:
        # Returns the file_id of the highest resolution version of the photo
        return f"PHOTO_ID:{message.photo[-1].file_id}"
    if message.video:
        return f"VIDEO_ID:{message.video.file_id}"
    if message.document:
        return f"DOC_ID:{message.document.file_id}"
    if message.audio:
        return f"Audio: {message.audio.file_name or 'audio'}"
    if message.voice:
        return "Voice note"
    if message.sticker:
        return "Sticker"
    if message.location:
        return "Location pin"
    if message.contact:
        return "Contact card"
    return "Media attachment"


def normalize_words(text: str) -> list[str]:
    cleaned = "".join(char.lower() if char.isalnum() else " " for char in text)
    return [word for word in cleaned.split() if word]


AI_GREETING_WORDS = {"hi", "hello", "hey", "sup", "bro", "broo", "brow"}
AI_THANKS_WORDS = {"thanks", "thank"}
AI_MEMORY_REFERENCES = {"it", "that", "this", "they", "there"}

def build_ai_answer(user_text: str, memory_summary: str = "") -> str:
    """Restored intelligent fallback that uses content.json to answer when AI is down."""
    text = " ".join(user_text.lower().split())
    words = set(normalize_words(user_text))

    if not text:
        return "Please send your question and I will help."

    # 1. GREETINGS
    if words & AI_GREETING_WORDS:
        return "Hello. Welcome to Vertex SACCO. I'm here to provide the financial insights you need. How may I assist you today?"

    # 2. DYNAMIC CONTENT LOOKUP (Search FAQs and Services)
    # This checks if the user's question matches any categories in content.json
    for category in ["faq", "services"]:
        cat_data = CONTENT.get(category, {})
        for key, data in cat_data.items():
            # Check if keyword is in the question
            title = data[0].lower()
            if any(word in text for word in title.split()) or key.split('_')[-1] in text:
                return f"<b>{data[0]}</b>\n\n{data[1]}"

    if any(term in text for term in ["join", "member", "register"]):
        join_info = CONTENT.get("faq", {}).get("faq_join", ["", ""])
        return join_info[1] if join_info[1] else "Visit any branch with your ID to join."

    # 3. IF ALL ELSE FAILS, USE THE OPTIMIZING MESSAGE
    fallback = CONTENT.get("ui_texts", {}).get("ai_fallback_message")
    return fallback if fallback else "I am currently optimizing my financial databases. Please try again in a moment."


async def groq_chat_completion(messages: list[dict[str, str]]) -> Optional[str]:
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("your_"):
        return None

    payload = json.dumps(
        {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 350,
        }
    ).encode("utf-8")

    req = request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "VertexSaccoBot/1.0",
            "Accept": "application/json",
        },
        method="POST",
    )

    def _send() -> Optional[str]:
        try:
            with request.urlopen(req, timeout=25) as response:
                data = json.loads(response.read().decode("utf-8"))
                choices = data.get("choices", [])
                if not choices:
                    return None

                reply = choices[0].get("message", {}).get("content", "").strip()
                if not reply:
                    return None
                
                # Log successful usage for debugging
                logger.info("Groq AI successfully generated a response (%d tokens).", data.get("usage", {}).get("total_tokens", 0))
                return reply
        except error.HTTPError as e:
            error_content = e.read().decode("utf-8")
            if e.code == 401:
                logger.error("Groq API Error: 401 Unauthorized. Verify your GROQ_API_KEY in environment variables.")
            elif e.code == 404:
                logger.error("Groq API Error: 404 Not Found. Check if the model '%s' is spelled correctly.", GROQ_MODEL)
            else:
                logger.error("Groq API Error (HTTP %s): %s", e.code, error_content)
            return None
        except error.URLError as e:
            logger.error("Groq Connection Error: %s. Ensure the bot environment has internet access.", e.reason)
            return None
        except json.JSONDecodeError:
            logger.error("Groq API returned an invalid JSON response.")
            return None
        except Exception as exc:
            logger.error("Unexpected error during Groq API call: %s (%s)", exc, type(exc).__name__)
            return None

    return await asyncio.to_thread(_send)


async def generate_ai_reply(context: ContextTypes.DEFAULT_TYPE, user_text: str) -> str:
    memory = list(get_chat_memory(context))
    system_prompt = CONTENT.get("system_prompt")
    if not system_prompt:
        system_prompt = "You are the Vertex Financial Persona, a confident and professional financial consultant for Vertex SACCO."
        logger.warning("system_prompt missing from content.json, using default.")

    messages = [{"role": "system", "content": system_prompt}]
    for item in memory[-20:]:
        role = "assistant" if item["role"] == "assistant" else "user"
        messages.append({"role": role, "content": item["text"]})
    messages.append({"role": "user", "content": user_text})

    ai_text = await groq_chat_completion(messages)
    if ai_text:
        return ai_text

    # Fallback/local AI
    return build_ai_answer(user_text)


async def safe_telegram_call(
    operation,
    description: str,
    retries: int = TELEGRAM_REQUEST_RETRIES,
):
    for attempt in range(retries + 1):
        try:
            return await operation()
        except TimedOut as exc:
            logger.warning(
                "Telegram request timed out while %s (attempt %s/%s): %s",
                description,
                attempt + 1,
                retries + 1,
                exc,
            )
            if attempt >= retries:
                return None
            await asyncio.sleep(TELEGRAM_RETRY_DELAY_SECONDS)


async def send_or_edit(
    update: Update,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    query = update.callback_query
    if query:
        await safe_telegram_call(lambda: query.answer(), "answering callback query")

        # Detect if the current message is a media message (photo or video).
        # Telegram does not allow editing a media message into a text message.
        is_media = bool(query.message and (query.message.photo or query.message.video))

        if is_media:
            # Delete the media message and send a fresh text message
            await safe_telegram_call(lambda: query.message.delete(), "deleting media message")
            await safe_telegram_call(
                lambda: update.effective_chat.send_message(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                ),
                "sending new message after media delete",
            )
        else:
            # Proceed with a standard text edit
            await safe_telegram_call(
                lambda: query.edit_message_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                ),
                "editing callback message",
            )
        return

    if update.effective_message:
        await safe_telegram_call(
            lambda: update.effective_message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            ),
            "sending reply message",
        )


async def show_typing(update: Update, context: ContextTypes.DEFAULT_TYPE, delay: float = 0.6) -> None:
    if update.effective_chat:
        await safe_telegram_call(
            lambda: context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING),
            "sending typing action",
        )
        await asyncio.sleep(delay)


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["state"] = STATE_REG_NAME
    welcome_text = (
        f"<b>{BRAND_EMOJI} Welcome to Vertex SACCO</b>\n\n"
        + CONTENT.get("ui_texts", {}).get("welcome_registration", "") + "\n\n"
        "Please enter your <b>Full Name</b> to begin:"
    )
    if update.effective_message:
        await safe_telegram_call(
            lambda: update.effective_message.reply_text(welcome_text, parse_mode=ParseMode.HTML),
            "starting registration",
        )


async def is_user_registered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if user and str(user.id) == ADMIN_ID:
        return True

    if context.user_data.get(IS_REGISTERED_KEY):
        return True
    
    state = context.user_data.get("state")
    if state in [STATE_REG_NAME, STATE_REG_PHONE]:
        return False

    await start_registration(update, context)
    return False


async def show_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["state"] = None
    clear_support_draft(context)

    welcome_text = (
        f"<b>{BRAND_EMOJI} Vertex SACCO Digital Assistant</b>\n"
        "<i>Professional • Trusted • Green</i>\n\n"
        + CONTENT.get("ui_texts", {}).get("welcome_home", "") + "\n\n"
        "How can we help you grow today?"
    )

    u_id = update.effective_user.id if update.effective_user else None
    if update.callback_query:
        await safe_telegram_call(
            lambda: update.callback_query.message.reply_text(
                text=welcome_text,
                reply_markup=home_keyboard(u_id),
                parse_mode=ParseMode.HTML,
            ),
            "sending home screen from callback",
        )
        await safe_telegram_call(lambda: update.callback_query.answer(), "answering home callback")
        return

    if update.effective_message:
        await safe_telegram_call(
            lambda: update.effective_message.reply_text(
                text=welcome_text,
                reply_markup=home_keyboard(u_id),
                parse_mode=ParseMode.HTML,
            ),
            "sending home screen",
        )


async def show_admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or str(user.id) != ADMIN_ID:
        if update.effective_message:
            await update.effective_message.reply_text("⛔ Access Denied. This area is for administrators only.")
        return

    text = (
        "<b>🛠 Vertex SACCO Admin Dashboard</b>\n\n"
        + CONTENT.get("ui_texts", {}).get("admin_dashboard_welcome", "") + "\n\n"
        "🟢 <b>Active Model:</b> <code>" + html.escape(GROQ_MODEL) + "</code>"
    )
    await send_or_edit(update, text, admin_dashboard_inline())


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Admin bypasses registration check
    await show_admin_dashboard(update, context)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_user_registered(update, context):
        return
    await show_home(update, context)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_user_registered(update, context):
        return
    await show_home(update, context)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_user_registered(update, context):
        return
    context.user_data.pop(CHAT_MEMORY_KEY, None)
    context.user_data["state"] = None
    u_id = update.effective_user.id if update.effective_user else None
    if update.effective_message:
        await update.effective_message.reply_text( # Changed from ♻️ to 🔄
            "🔄 Your AI conversation has been cleared. You can start a fresh chat now.",
            reply_markup=home_keyboard(u_id),
        )


async def show_ai_assistant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"<b>{BRAND_EMOJI} AI Assistant</b>\n\n"
        + CONTENT.get("ui_texts", {}).get("ai_assistant_intro", "") + "\n\n"
        "🟢 <b>Examples:</b>\n"
        "- How do I join?\n"
        "- What does SACCO mean?\n"
        "- Explain saving\n"
        "- What services do you offer?\n"
        "- Where is your office?"
    )
    await send_or_edit(update, text, back_home_inline())


async def show_faq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "<b>❓ Member FAQ Centre</b>\n\n" # Changed from 🍃 to ❓
        "Browse common questions and quick answers prepared for members."
    )
    await send_or_edit(update, text, faq_inline())


async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"<b>{BRAND_EMOJI} Services & Loans</b>\n\n"
        "Explore savings, credit, digital support, and core SACCO member services."
    )
    await send_or_edit(update, text, services_inline())


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"<b>{BRAND_EMOJI} Company Profile</b>\n\n"
        "Vertex SACCO is a member-centered financial cooperative committed to trusted service, disciplined growth, "
        "and long-term financial empowerment for individuals, families, and businesses.\n\n"
        "🟢 <b>Mission</b>\n"
        "To empower members through accessible savings, responsible credit, and dependable support that improves everyday financial life.\n\n"
        "🟢 <b>Vision</b>\n"
        "To be a trusted and forward-looking SACCO known for financial inclusion, service excellence, and sustainable member prosperity.\n\n"
        "🟢 <b>Goals</b>\n"
        "To grow member savings, expand access to fair financial services, strengthen trust through transparency, and support stable community development.\n\n"
        "🟢 <b>Core Values</b>\n"
        "Integrity, accountability, professionalism, innovation, and member prosperity."
    )
    await send_or_edit(update, text, back_home_inline())


async def show_branches(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"<b>{BRAND_EMOJI} Branch Locator</b>\n\n"
        "Select a branch to view address details, contact information, working hours, and a Google Maps link."
    )
    await send_or_edit(update, text, branches_inline())


async def show_admin_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["state"] = STATE_CONTACT_ADMIN
    clear_support_draft(context)
    text = (
        "<b>📞 Contact Admin</b>\n\n"
        "Write your support message first. You can also attach a photo, video, voice note, document, or link.\n\n"
        "After that, use <b>Send Message</b> to confirm or <b>Cancel Message</b> to discard the draft."
    )
    await send_or_edit(update, text, None)
    if update.effective_message:
        await safe_telegram_call(
            lambda: update.effective_message.reply_text(
                "Support draft mode is active. Prepare your message and use the keyboard below.",
                reply_markup=support_keyboard(),
            ),
            "sending support draft keyboard",
        )


async def show_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["state"] = STATE_FEEDBACK
    text = (
        "<b>⭐ Feedback Lounge</b>\n\n"
        "How was your experience with Vertex SACCO today?\n\n"
        "Choose a rating below or send a short comment."
    )
    await send_or_edit(update, text, feedback_inline())


async def forward_member_message_to_admin(
    user,
    summary: str,
    source_chat_id: int,
    source_message_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    if not ADMIN_ID:
        return False

    admin_chat_id = int(ADMIN_ID)
    reply_map = get_admin_reply_map(context)

    username_line = f"<b>Username:</b> @{html.escape(user.username)}\n" if user.username else ""
    header_text = (
        "<b>New Vertex SACCO support request</b>\n\n"
        f"<b>From:</b> {html.escape(user.full_name)}\n"
        f"<b>User ID:</b> <code>{user.id}</code>\n"
        f"{username_line}"
    )

    header_text += (
        f"<b>Type:</b> {html.escape(summary)}\n\n"
        "Reply to this message to answer the member."
    )

    header = await safe_telegram_call(
        lambda: context.bot.send_message(
            chat_id=admin_chat_id,
            text=header_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        ),
        "forwarding support header to admin",
    )
    if header is None:
        return False
    reply_map[header.message_id] = user.id

    copied = await safe_telegram_call(
        lambda: context.bot.copy_message(
            chat_id=admin_chat_id,
            from_chat_id=source_chat_id,
            message_id=source_message_id,
        ),
        "copying member support message to admin",
    )
    if copied is None:
        return False
    reply_map[copied.message_id] = user.id
    return True


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not ADMIN_ID:
        return False

    if str(user.id) != ADMIN_ID:
        return False

    if not message.reply_to_message:
        return False

    reply_map = get_admin_reply_map(context)
    target_user_id = reply_map.get(message.reply_to_message.message_id)
    if not target_user_id:
        return False

    try:
        banner = await safe_telegram_call(
            lambda: context.bot.send_message(
                chat_id=target_user_id,
                text="<b>📞 Vertex SACCO Support Reply</b>", # Changed from 🍏 to 📞
                parse_mode=ParseMode.HTML,
            ),
            "sending admin reply banner to member",
        )
        copied = await safe_telegram_call(
            lambda: context.bot.copy_message(
                chat_id=target_user_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
            ),
            "copying admin reply to member",
        )
        if banner is None or copied is None:
            await safe_telegram_call(
                lambda: message.reply_text("The reply timed out before reaching the member. Please try again."),
                "notifying admin about reply timeout",
            )
            return True

        await safe_telegram_call(
            lambda: message.reply_text("Reply delivered to the member."),
            "confirming admin reply delivery",
        )
        return True
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to deliver admin reply: %s", exc)
        await safe_telegram_call(
            lambda: message.reply_text("I could not deliver that reply to the member."),
            "notifying admin about reply failure",
        )
        return True


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_user_registered(update, context):
        if update.callback_query:
            await update.callback_query.answer("Please complete registration first.", show_alert=True)
        return

    query = update.callback_query
    data = query.data or ""
    if data == "nav_home":
        await show_home(update, context)
        return
    if data == "menu_ai":
        await show_ai_assistant(update, context)
        return
    if data == "admin_stats":
        await query.answer("Calculating registrations...")
        count = await get_total_registrations()
        await send_or_edit(
            update, 
            f"<b>📊 Vertex SACCO Statistics</b>\n\nTotal Registered Members: <b>{count}</b>\n\n<i>Data is synced live from Google Sheets.</i>", 
            admin_dashboard_inline())
        return
    if data == "admin_get_file_id":
        if str(query.from_user.id) != ADMIN_ID:
            await query.answer("⛔ Admin only.", show_alert=True)
            return
        context.user_data["state"] = STATE_GET_FILE_ID
        await send_or_edit(update, 
            "🆔 <b>File ID Tool Activated</b>\n\nPlease upload the photo, video, or document you want the ID for. I will reply with the specific Telegram File ID.",
            back_home_inline())
        return
    if data == "menu_faq":
        await show_faq(update, context)
        return
    if data == "menu_services":
        await show_services(update, context)
        return
    if data == "menu_profile":
        await show_profile(update, context)
        return
    if data == "menu_branches":
        await show_branches(update, context)
        return
    if data == "menu_admin":
        await show_admin_contact(update, context)
        return
    if data == "menu_feedback":
        await show_feedback(update, context)
        return

    faq_data = CONTENT.get("faq", {})
    if data in faq_data:
        question, answer = faq_data[data]
        await send_or_edit(update, f"<b>{question}</b>\n\n{answer}", back_home_inline())
        return

    service_data = CONTENT.get("services", {})
    if data in service_data:
        title, body = service_data[data]
        await send_or_edit(update, f"<b>{title}</b>\n\n{body}", home_and_contact_inline())
        return

    branch_data = CONTENT.get("branches", {})
    if data in branch_data:
        branch = branch_data[data]
        caption = (
            f"<b>{branch['name']}</b>\n\n"
            f"<b>Address:</b> {branch['address']}\n"
            f"<b>Phone:</b> {branch['phone']}\n"
            f"<b>Hours:</b> {branch['hours']}\n\n"
            "Tap the map button below for directions."
        )
        video_url = branch.get("video_url")
        image_url = branch.get("image_url")

        if video_url or image_url:
            # Answer query and delete the previous menu message
            await safe_telegram_call(lambda: query.answer(), "answering branch selection")
            await safe_telegram_call(lambda: query.message.delete(), "deleting branch menu")
            
            async def _send_branch_media():
                # Check if it's a local file in your assets folder
                base_path = os.path.dirname(os.path.abspath(__file__))
                media_path = video_url if video_url else image_url
                full_path = os.path.join(base_path, media_path)
                
                # Check for local file existence
                is_local = os.path.exists(full_path)
                media_file = open(full_path, "rb") if is_local else media_path

                try:
                    if video_url:
                        return await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=media_file,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                            reply_markup=branch_actions(data),
                            supports_streaming=True,
                            write_timeout=TELEGRAM_MEDIA_WRITE_TIMEOUT
                        )
                    else:
                        return await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=media_file,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                            reply_markup=branch_actions(data)
                        )
                finally:
                    if is_local and hasattr(media_file, 'close'):
                        media_file.close()

            await safe_telegram_call(_send_branch_media, "sending branch media")
        else:
            await send_or_edit(update, caption, branch_actions(data))
        return

    if data.startswith("feedback|"):
        score = data.split("|", 1)[1]
        user = update.effective_user
        context.user_data["state"] = None
        logger.info(
            "Feedback received | user_id=%s | score=%s",
            update.effective_user.id if update.effective_user else "unknown",
            score,
        )
        stars = "★ " * int(score) + "☆ " * (5 - int(score))
        
        # Save the rating to the new Feedback worksheet
        await save_feedback_to_sheet(user.id, user.full_name, rating=score)
        
        # Logic: Notify Admin if rating is low (<= 2)
        if int(score) <= 2 and ADMIN_ID:
            await context.bot.send_message(
                chat_id=int(ADMIN_ID),
                text=f"⚠️ <b>Low Rating Alert</b>\n\n<b>User:</b> {user.full_name}\n<b>Rating:</b> {score}/5\n<i>The user has been prompted for a comment to explain the issue.</i>",
                parse_mode=ParseMode.HTML
            )

        # Logic: Adjust response based on score
        if int(score) >= 4:
            final_text = (
                f"<b>✅ Feedback received</b>\n\n<b>{stars.strip()}</b>\n\n"
                f"Thank you for the {score}/5 rating! Since you're enjoying the service, "
                "<b>would you like to share a brief testimonial</b> about what you like most? "
                "Just type it below."
            )
        else:
            final_text = (
                f"<b>✅ Feedback received</b>\n\n<b>{stars.strip()}</b>\n\n"
                "Your rating has been recorded. Is there anything specific we can improve? "
                "Please let us know by typing a short comment below."
            )

        await send_or_edit(
            update,
            final_text,
            None # Leave it open for the user to type a comment
        )
        return

    await query.answer("This option is not available right now.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return
    
    if await handle_admin_reply(update, context):
        return

    state = context.user_data.get("state")
    text = (message.text or "").strip()

    # --- Registration Handling ---
    if state == STATE_REG_NAME:
        if not text or len(text) < 3:
            await message.reply_text("Please enter a valid full name.")
            return
        context.user_data[REG_DATA_NAME] = text
        context.user_data["state"] = STATE_REG_PHONE
        await message.reply_text(
            f"Thank you, {text}. Now, please share your contact number using the button below so we can verify your membership.",
            reply_markup=phone_registration_keyboard(),
        )
        return

    if state == STATE_REG_PHONE:
        if not message.contact:
            await message.reply_text(
                "Sharing your contact is required to use the Vertex SACCO bot. Please tap the 'Share Contact' button.",
                reply_markup=phone_registration_keyboard(),
            )
            return
        
        phone = message.contact.phone_number
        if context.user_data.get("is_processing_reg"):
            return
            
        context.user_data["is_processing_reg"] = True
        name = context.user_data.get(REG_DATA_NAME, "Unknown")
        
        # Save to Google Sheets
        await show_typing(update, context)
        success = await save_to_google_sheets(name, phone, user.id, user.username)
        
        if success:
            context.user_data.pop("is_processing_reg", None)
            context.user_data[IS_REGISTERED_KEY] = True
            context.user_data["state"] = None
            is_admin = str(user.id) == ADMIN_ID
            context.user_data.pop(REG_DATA_NAME, None)
            await message.reply_text(
                "✅ Registration complete! Your profile has been synchronized with the Vertex SACCO database.",
                reply_markup=home_keyboard(user.id)
            )
            if is_admin:
                await message.reply_text("Admin access confirmed.")
            
            await show_home(update, context)
        else:
            context.user_data.pop("is_processing_reg", None)
            await message.reply_text(
                "There was an issue saving your registration. Our team has been notified, but you can try again or contact support.",
                reply_markup=phone_registration_keyboard()
            )
        return

    # --- Admin File ID Tool Handling ---
    if state == STATE_GET_FILE_ID:
        if str(user.id) != ADMIN_ID:
            context.user_data["state"] = None
            return

        file_id = None
        m_type = "File"
        
        if message.photo:
            file_id, m_type = message.photo[-1].file_id, "Photo"
        elif message.video:
            file_id, m_type = message.video.file_id, "Video"
        elif message.document:
            file_id, m_type = message.document.file_id, "Document"
        elif message.audio:
            file_id, m_type = message.audio.file_id, "Audio"
        elif message.voice:
            file_id, m_type = message.voice.file_id, "Voice"

        if file_id:
            await message.reply_text(
                f"✅ <b>{m_type} ID Retrieved:</b>\n\n<code>{file_id}</code>\n\n"
                "Copy this ID into your <code>content.json</code>.",
                parse_mode=ParseMode.HTML,
                reply_markup=admin_dashboard_inline()
            )
        else:
            await message.reply_text("❌ No media detected. Please upload a photo, video, or document.")
        
        context.user_data["state"] = None
        return

    # --- Guard: Prevent use if not registered ---
    if not await is_user_registered(update, context):
        return
    # -----------------------------


    if message.text:
        if text == BTN_MAIN_MENU:
            await show_home(update, context)
            return
        if text == BTN_AI:
            await show_ai_assistant(update, context)
            return
        if text == BTN_FAQ:
            await show_faq(update, context)
            return
        if text == BTN_SERVICES:
            await show_services(update, context)
            return
        if text == BTN_PROFILE:
            await show_profile(update, context)
            return
        if text == BTN_BRANCHES:
            await show_branches(update, context)
            return
        if text == BTN_ADMIN:
            await show_admin_contact(update, context)
            return
        if text == BTN_FEEDBACK:
            await show_feedback(update, context)
            return
        if text == BTN_ADMIN_PANEL:
            await show_admin_dashboard(update, context)
            return

    if state == STATE_CONTACT_ADMIN:
        if text == BTN_SUPPORT_CANCEL:
            context.user_data["state"] = None
            clear_support_draft(context)
            await safe_telegram_call(
                lambda: message.reply_text(
                    "Your support draft has been canceled.",
                    reply_markup=home_keyboard(user.id),
                ),
                "canceling support draft",
            )
            return

        if text == BTN_SUPPORT_SEND:
            draft = get_support_draft(context)
            if not draft:
                await safe_telegram_call(
                    lambda: message.reply_text(
                        "There is no draft yet. Please type your message or attach a file first.",
                        reply_markup=support_keyboard(),
                    ),
                    "notifying user about missing support draft",
                )
                return

            logger.info("Support request | user_id=%s | summary=%s", user.id, draft["summary"])
            forwarded = await forward_member_message_to_admin(
                user,
                str(draft["summary"]),
                int(draft["chat_id"]),
                int(draft["message_id"]),
                context,
            )
            context.user_data["state"] = None
            clear_support_draft(context)
            remember_message(context, "user", str(draft["summary"]))
            response = (
                "Your message has been sent to the Vertex SACCO support desk. You will receive the admin reply here."
                if forwarded
                else "Your message was prepared, but I could not forward it to the support desk right now. Please try again shortly."
            )
            remember_message(context, "assistant", response)
            await safe_telegram_call(
                lambda: message.reply_text(
                    response,
                    reply_markup=home_keyboard(user.id),
                ),
                "sending support forwarding confirmation",
            )
            return

        draft = set_support_draft(context, message)
        preview = (
            "<b>Draft saved</b>\n\n"
            f"<b>Message:</b> {html.escape(str(draft['summary']))}\n\n"
            "Use <b>Send Message</b> to deliver it to support or <b>Cancel Message</b> to discard it."
        )
        await safe_telegram_call(
            lambda: message.reply_text(
                preview,
                reply_markup=support_keyboard(),
                parse_mode=ParseMode.HTML,
            ),
            "saving support draft preview",
        )
        return

    if state == STATE_FEEDBACK:
        context.user_data["state"] = None
        comment = summarize_message(message)
        logger.info("Written feedback | user_id=%s | feedback=%s", user.id, comment)
        
        # Save the comment to the worksheet
        await save_feedback_to_sheet(user.id, user.full_name, comment=comment)
        
        await safe_telegram_call(
            lambda: message.reply_text(
                "Thank you for your valuable feedback. It has been recorded and shared with our management team.",
                reply_markup=back_home_inline(),
            ),
            "sending written feedback confirmation",
        )
        return

    if message.text:
        remember_message(context, "user", text)
        await show_typing(update, context)
        ai_answer = await generate_ai_reply(context, text)
        remember_message(context, "assistant", ai_answer)
        await safe_telegram_call(
            lambda: message.reply_text(
                ai_answer,
                disable_web_page_preview=True,
            ),
            "sending AI reply",
        )
        return

    remember_message(context, "user", summarize_message(message))
    fallback_reply = (
        "I have received your file or attachment.\n\n"
        "If you want support with it, please open Contact Admin so the team can assist you directly."
    )
    remember_message(context, "assistant", fallback_reply)
    await safe_telegram_call(
        lambda: message.reply_text(
            fallback_reply,
            reply_markup=back_home_inline(),
        ),
        "sending attachment fallback reply",
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        await safe_telegram_call(
            lambda: update.effective_message.reply_text("An unexpected error occurred. Please try again."),
            "sending error notification",
        )


async def post_init(application: Application) -> None:
    logger.info("Vertex SACCO Bot started successfully.")
    if ADMIN_ID:
        try:
            await safe_telegram_call(
                lambda: application.bot.send_message(
                    chat_id=int(ADMIN_ID),
                    text=(
                        "<b>Vertex SACCO Bot is online</b>\n\n"
                        "The professional member support interface is active.\n"
                        "Reply to forwarded member requests and the bot will send your reply back to the user."
                    ),
                    parse_mode=ParseMode.HTML,
                ),
                "sending startup notification to admin",
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not notify admin on startup: %s", exc)


class HealthcheckHandler(BaseHTTPRequestHandler):
    def _send_health_response(self, include_body: bool) -> None:
        if self.path not in ("/", "/health"):
            self.send_error(404)
            return

        body = b"VertexBot is running"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def do_GET(self) -> None:  # pragma: no cover - tiny integration surface
        self._send_health_response(include_body=True)

    def do_HEAD(self) -> None:  # pragma: no cover - tiny integration surface
        self._send_health_response(include_body=False)

    def log_message(self, format: str, *args: object) -> None:
        return


def maybe_start_render_health_server() -> None:
    port_value = os.getenv("PORT", "").strip()
    if not port_value:
        return

    try:
        port = int(port_value)
    except ValueError:
        logger.warning("Ignoring invalid PORT value: %s", port_value)
        port = RENDER_DEFAULT_PORT

    server = ThreadingHTTPServer((RENDER_HOST, port), HealthcheckHandler)
    thread = threading.Thread(target=server.serve_forever, name="render-healthcheck", daemon=True)
    thread.start()
    logger.info("Render health server listening on %s:%s", RENDER_HOST, port)


def main() -> None:
    load_content()
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing. Set it in your .env file.")

    # Immediate visibility for Render logs
    key_present = bool(GROQ_API_KEY and not GROQ_API_KEY.startswith("your_"))
    key_status = "✅ CONFIGURED" if key_present else "❌ MISSING OR PLACEHOLDER"
    
    logger.info("=== Bot Initialization ===")
    logger.info("GROQ_API_KEY: %s", key_status)
    if key_present:
        logger.info("Key format check: Starts with 'gsk_'? %s", "Yes" if GROQ_API_KEY.startswith("gsk_") else "No")
    logger.info("GROQ_MODEL:   %s", GROQ_MODEL)
    logger.info("==========================")

    if GROQ_API_KEY:
        logger.info("Groq API key detected. Vertex SACCO AI brain is enabled with conversation memory.")
    else:
        logger.info("Groq API key not found. Using the local fallback assistant with conversation memory.")

    persistence = PicklePersistence(filepath="bot_persistence.pickle")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .persistence(persistence)
        .connect_timeout(TELEGRAM_CONNECT_TIMEOUT)
        .read_timeout(TELEGRAM_READ_TIMEOUT)
        .write_timeout(TELEGRAM_WRITE_TIMEOUT)
        .pool_timeout(TELEGRAM_POOL_TIMEOUT)
        .media_write_timeout(TELEGRAM_MEDIA_WRITE_TIMEOUT)
        .get_updates_connect_timeout(TELEGRAM_CONNECT_TIMEOUT)
        .get_updates_read_timeout(TELEGRAM_READ_TIMEOUT)
        .get_updates_write_timeout(TELEGRAM_WRITE_TIMEOUT)
        .get_updates_pool_timeout(TELEGRAM_POOL_TIMEOUT)
        .post_init(post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    maybe_start_render_health_server()
    application.run_polling(
        timeout=TELEGRAM_POLL_TIMEOUT, 
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error("Fatal error: %s", e)
