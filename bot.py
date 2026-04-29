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

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("vertex_sacco_bot")


BRAND_EMOJI = "💚"

BTN_AI = "💡 AI Assistant"
BTN_FAQ = "❓ Member FAQ"
BTN_SERVICES = "🟢 Services"
BTN_PROFILE = "🏢 Sacco Profile"
BTN_BRANCHES = "📍 Branches"
BTN_ADMIN = "📞 Support"
BTN_FEEDBACK = "⭐ Feedback"
BTN_CLEAR = "🔄 Clear Chat"
BTN_SUPPORT_SEND = "✅ Send Message"
BTN_SUPPORT_CANCEL = "❌ Cancel Message"
BTN_MAIN_MENU = "🟢 Main Menu"

STATE_REG_NAME = "reg_name"
STATE_REG_PHONE = "reg_phone"
STATE_CONTACT_ADMIN = "contact_admin"
STATE_FEEDBACK = "feedback"
SUPPORT_DRAFT_KEY = "support_draft"
IS_REGISTERED_KEY = "is_registered"
REG_DATA_NAME = "reg_data_name"


FAQ_ITEMS = {
    "faq_join": (
        "How do I become a member?",
        "Joining Vertex SACCO is simple. Visit any branch with your national ID or passport, a passport photo, "
        "and your opening contribution. Our onboarding team will guide you through the registration form, "
        "member number setup, and account activation.",
    ),
    "faq_loan": (
        "How long does loan processing take?",
        "Standard loan applications are reviewed after document verification and guarantor confirmation. "
        "Emergency facilities are prioritized, while development loans may take longer depending on appraisal requirements.",
    ),
    "faq_savings": (
        "Can I save and borrow at the same time?",
        "Yes. Members can continue building savings while accessing eligible loan products. "
        "A healthy savings history improves your borrowing profile and strengthens your access to higher limits over time.",
    ),
    "faq_support": (
        "How do I get account help?",
        "Use the Contact Admin menu for account support, statement help, or document follow-up. "
        "Your request will be routed to the support desk for direct assistance.",
    ),
}

BRANCHES = {
    "branch_hq": {
        "name": "Addis Ababa Main Office",
        "address": "22 Area, Addis Ababa, Ethiopia",
        "phone": "+251 11 000 0000",
        "hours": "Mon-Fri 8:30 AM - 5:30 PM, Sat 8:30 AM - 12:30 PM",
        "maps_url": "https://www.google.com/maps/search/?api=1&query=22+Area+Addis+Ababa+Ethiopia",
    },
    "branch_westlands": {
        "name": "Member Service Desk",
        "address": "Addis Ababa, Ethiopia",
        "phone": "+251 11 000 0001",
        "hours": "Mon-Fri 8:30 AM - 5:30 PM",
        "maps_url": "https://www.google.com/maps/search/?api=1&query=Addis+Ababa+Ethiopia",
    },
    "branch_mombasa": {
        "name": "Verification Support Office",
        "address": "22 Area vicinity, Addis Ababa, Ethiopia",
        "phone": "+251 11 000 0002",
        "hours": "Mon-Fri 8:30 AM - 5:00 PM",
        "maps_url": "https://www.google.com/maps/search/?api=1&query=22+Area+Addis+Ababa",
    },
}

SERVICES_CONTENT = {
    "service_savings": (
        "Savings Services",
        "Build your financial future through regular deposits, goal-based saving, children's plans, "
        "and long-term member wealth programs. Members benefit from disciplined saving, easier access to credit, "
        "and stronger dividend potential.",
    ),
    "service_loans": (
        "Loan Services",
        "Vertex SACCO offers salary advances, emergency loans, school fees support, development financing, "
        "and business growth facilities. Loan options are structured around repayment ability, savings profile, "
        "and member standing.\n\n"
        "What goes into financing:\n"
        "• Member eligibility based on savings history and repayment track record\n"
        "• Loan amount determined by savings balance and income verification\n"
        "• Interest rates starting from competitive SACCO rates\n"
        "• Repayment terms from 3-36 months depending on loan type\n"
        "• Guarantor requirements for larger loans\n"
        "• Document verification including ID, payslips, and business plans\n"
        "• Credit scoring based on member standing and financial discipline",
    ),
    "service_digital": (
        "Digital Services",
        "Members can use digital support channels for balance requests, product inquiries, branch guidance, "
        "and follow-up on applications. This bot acts as the first support layer for quick assistance.",
    ),
    "service_support": (
        "Member Support",
        "For account issues, document clarification, application follow-up, or one-on-one assistance, "
        "use the Contact Admin section and our support team will respond directly.",
    ),
}

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
VERTEX_AI_SYSTEM_PROMPT = """You are Vertex SACCO AI, the official digital assistant for Vertex SACCO Ltd in Ethiopia.
Vertex SACCO branding is professional green.

You should sound like a real professional customer care agent, embodying the Vertex "Green Brand":
- warm
- calm
- intelligent
- natural
- trustworthy

Your job is to understand the user's real intent and respond like a helpful human assistant, not like a scripted bot.

Main behavior:
- answer naturally
- keep answers clear and useful
- do not repeat generic SACCO descriptions unless the user truly asks for them
- do not answer with meta phrases like "I can help with..." unless the user is asking what you can do
- if the user is casual, respond naturally but still professionally
- if the user asks a broad question, try to give the most helpful answer you can
- if the user is unclear, ask one short follow-up question

Knowledge areas:
- membership
- savings
- loans
- SACCO accounts
- office location
- contact information
- general SACCO education

Important accuracy rules:
- do not invent interest rates, approval guarantees, or hidden policies
- if exact details are not known, say: "For accurate details, please contact the office directly."
- do not overpromise

Official contact details:
- 0991 44 44 11
- 0991 44 44 22
- 0991 44 44 88
- 0991 44 44 99

Office:
- Addis Ababa, 22 Area
- near Golagul Building
- Getfam Hotel road
- around New Bata Complex
- same building as Zemen Bank

Trust approach:
- if asked about safety or legitimacy, answer calmly and transparently
- encourage office visit or direct contact for verification when appropriate

Language:
- default to English
- if the user speaks Amharic, respond naturally in Amharic

You are not a menu bot.
You are not a repeating script.
You are a real assistant representing Vertex SACCO.

Answer based on meaning, context, and customer intent."""


def home_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [BTN_AI, BTN_FAQ],
            [BTN_SERVICES, BTN_BRANCHES],
            [BTN_PROFILE, BTN_ADMIN],
            [BTN_FEEDBACK],
        ],
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
    for key, (question, _) in FAQ_ITEMS.items():
        rows.append([InlineKeyboardButton(f"🧾 {question}", callback_data=key)])
    rows.append([InlineKeyboardButton("🟢 Main Menu", callback_data="nav_home")])
    return InlineKeyboardMarkup(rows)


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
    branch = BRANCHES[branch_key]
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


async def save_to_google_sheets(name: str, phone: str, user_id: int, username: str) -> bool:
    json_str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not GOOGLE_SHEET_ID or not json_str:
        logger.warning("Google Sheets configuration missing (ID or JSON env var).")
        return False

    def _append():
        try:
            service_account_info = json.loads(json_str)
            client_email = service_account_info.get("client_email", "unknown email")
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
            client = gspread.authorize(creds)
            
            sheet_id = GOOGLE_SHEET_ID
            if "spreadsheets/d/" in sheet_id:
                sheet_id = sheet_id.split("spreadsheets/d/")[1].split("/")[0]
            
            logger.info("Attempting to save registration for %s to sheet %s", user_id, sheet_id)
            # Use open_by_key and get the first sheet
            spreadsheet = client.open_by_key(sheet_id)
            sheet = spreadsheet.get_worksheet(0)
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Matches your headers: timestamp | telegram_user_id | full_name | phone_number | telegram_username | registration_status
            sheet.append_row([
                timestamp, 
                str(user_id), 
                name, 
                phone, 
                f"@{username}" if username else "N/A", 
                "registered"
            ])
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


def summarize_message(message: Message) -> str:
    if message.text:
        return message.text
    if message.caption:
        return message.caption
    if message.photo:
        return "Photo attachment"
    if message.video:
        return "Video attachment"
    if message.document:
        return f"Document: {message.document.file_name or 'file'}"
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

AI_DIRECT_PATTERNS = [
    (
        {"bank", "sacco"},
        {
            "difference",
            "different",
            "similar",
            "similarity",
            "compare",
            "comparison",
            "vs",
            "versus",
        },
        "A bank and a SACCO are both financial institutions, but they work differently. "
        "A bank serves the general public as a commercial institution, while a SACCO is member-owned and mainly serves its members. "
        "Both help people save money and access loans.",
    ),
    (
        {"rate", "rates", "interest", "fees", "charges"},
        set(),
        "For exact rates, fees, or charges, please contact the office directly for current official information.",
    ),
    (
        {"contact", "phone", "call", "number"},
        set(),
        "You can contact Vertex SACCO on 0991 44 44 11, 0991 44 44 22, 0991 44 44 88, or 0991 44 44 99.",
    ),
    (
        {"office", "branch", "location", "address", "map", "where"},
        set(),
        "Vertex SACCO is located in Addis Ababa, 22 Area, near Golagul Building on the Getfam Hotel road, around New Bata Complex.",
    ),
]

AI_TOPIC_KNOWLEDGE = [
    {
        "name": "capabilities",
        "keywords": {"help", "assist", "faq"},
        "phrases": {"what can you do", "what can i ask", "how can you help", "what do you know"},
        "answer": "I can help explain Vertex SACCO membership, savings, loans, account opening, office location, and contact details. "
        "You can ask in a natural way, and I will do my best to answer clearly.",
    },
    {
        "name": "services",
        "keywords": {"service", "services", "support"},
        "phrases": {"explain service", "explain services", "what services do you offer", "tell me about services"},
        "answer": "Vertex SACCO services generally include membership registration, savings services, loan support, SACCO account guidance, office assistance, and member follow-up support.",
    },
    {
        "name": "sacco",
        "keywords": {"cooperative"},
        "phrases": {"what is sacco", "meaning of sacco", "define sacco"},
        "answer": "A SACCO is a Savings and Credit Cooperative Organization that helps members save and access financial services through a cooperative system.",
    },
    {
        "name": "bank",
        "keywords": {"bank"},
        "phrases": {"what is bank", "meaning of bank", "define bank"},
        "answer": "A bank is a licensed financial institution that offers public services such as accounts, loans, transfers, and money management.",
    },
    {
        "name": "saving",
        "keywords": {"saving", "savings", "save", "deposit", "shares"},
        "phrases": {"what is saving", "meaning of saving", "define saving"},
        "answer": "Saving means putting money aside regularly. In a SACCO, savings help build financial discipline and may strengthen access to other services such as loans.",
    },
    {
        "name": "saving_benefit",
        "keywords": {"saving", "savings", "save", "use", "benefit", "importance"},
        "phrases": {"use of saving", "benefit of saving", "why save", "importance of saving", "why is saving important"},
        "answer": "The main use of saving in a SACCO is to build financial discipline, grow your funds over time, and strengthen your access to services such as loans. It also helps create a stronger financial base for future needs.",
    },
    {
        "name": "loan",
        "keywords": {"loan", "loans", "borrow", "credit", "repay"},
        "phrases": {"what is loan", "define loan", "loan process"},
        "answer": "A loan is money given to a member to be repaid over time. In general, loan access depends on membership standing, savings history, and the normal review process.",
    },
    {
        "name": "membership",
        "keywords": {"member", "membership", "join", "register"},
        "phrases": {"how to join", "become a member", "open membership"},
        "answer": "Membership usually starts by visiting the office, registering, and beginning a savings plan. Once registered, a member may become eligible for more SACCO services.",
    },
    {
        "name": "account",
        "keywords": {"account", "accounts", "open", "create"},
        "phrases": {"open account", "create account"},
        "answer": "A SACCO account is part of your member relationship with the organization. Usually, a person registers first and then the account is opened and activated.",
    },
    {
        "name": "benefits",
        "keywords": {"benefit", "benefits", "advantage", "advantages"},
        "phrases": {"why join", "why save"},
        "answer": "Common benefits include building a saving culture, improving access to loans, and receiving member-focused financial support.",
    },
    {
        "name": "trust",
        "keywords": {"safe", "trusted", "trust", "real", "legit"},
        "phrases": {"is it safe", "can i trust"},
        "answer": "Vertex SACCO is designed to serve its members through cooperative financial services. For full confidence, it is always good to verify official documents and office information directly.",
    },
]


def score_topic(words: set[str], text: str, topic: dict[str, object]) -> int:
    keyword_hits = sum(1 for keyword in topic["keywords"] if keyword in words)
    phrase_hits = sum(3 for phrase in topic["phrases"] if phrase in text)
    return keyword_hits + phrase_hits


def build_ai_answer(user_text: str, memory_summary: str = "") -> str:
    text = user_text.lower().strip()
    words = set(normalize_words(user_text))
    memory_lower = memory_summary.lower()

    if words & AI_GREETING_WORDS:
        return "Hello. Welcome to Vertex SACCO. How may I assist you today?"

    if any(phrase in text for phrase in ["how are you", "how about you", "and you", "you?", "i'm good", "im good"]):
        return "I am doing well, thank you. How may I assist you with Vertex SACCO today?"

    if words & AI_THANKS_WORDS:
        return "You are welcome. If you need anything else, I am here to help."

    direct_match = next(
        (
            answer
            for primary, secondary, answer in AI_DIRECT_PATTERNS
            if primary & words and (not secondary or secondary & words or any(token in text for token in secondary))
        ),
        None,
    )
    if direct_match:
        return direct_match

    scored_topics = sorted(
        ((score_topic(words, text, topic), topic) for topic in AI_TOPIC_KNOWLEDGE),
        key=lambda item: item[0],
        reverse=True,
    )
    matched_topics = [topic for score, topic in scored_topics if score > 0][:2]

    if matched_topics:
        primary = matched_topics[0]["answer"]
        secondary = matched_topics[1]["answer"] if len(matched_topics) > 1 else ""

        if matched_topics[0]["name"] == "services":
            return primary

        if matched_topics[0]["name"] == "saving_benefit":
            return primary

        reply = primary
        if secondary and matched_topics[0]["name"] not in {"sacco", "bank"}:
            reply = f"{primary} {secondary}"
        if words & AI_MEMORY_REFERENCES and memory_lower:
            return reply + " If you want, I can explain the same topic in a simpler way."
        return reply

    return (
        "I am here to help with Vertex SACCO membership, savings, loans, accounts, office guidance, and general SACCO questions. "
        "Tell me what you want to know, and I will explain it as clearly as I can."
    )


async def groq_chat_completion(messages: list[dict[str, str]]) -> Optional[str]:
    if not GROQ_API_KEY:
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
        },
        method="POST",
    )

    def _send() -> Optional[str]:
        try:
            with request.urlopen(req, timeout=25) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except (error.URLError, error.HTTPError, KeyError, IndexError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("Groq request failed: %s", exc)
            return None

    return await asyncio.to_thread(_send)


async def generate_ai_reply(context: ContextTypes.DEFAULT_TYPE, user_text: str) -> str:
    memory = list(get_chat_memory(context))
    messages = [{"role": "system", "content": VERTEX_AI_SYSTEM_PROMPT}]
    for item in memory[-20:]:
        role = "assistant" if item["role"] == "assistant" else "user"
        messages.append({"role": role, "content": item["text"]})
    messages.append({"role": "user", "content": user_text})

    ai_text = await groq_chat_completion(messages)
    if ai_text:
        # Add a natural, warm touch
        if any(word in user_text.lower() for word in ["thank", "thanks"]):
            return ai_text + "\n\nIf you have more questions, feel free to ask!"
        return ai_text

    # Fallback/local AI
    answer = build_ai_answer(user_text, memory_text(get_chat_memory(context)))
    # Add a natural, warm touch
    if any(word in user_text.lower() for word in ["thank", "thanks"]):
        return answer + "\n\nIf you have more questions, feel free to ask!"
    return answer


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
        "To provide you with secure and personalized financial services, we need to register your profile.\n\n"
        "Please enter your <b>Full Name</b> to begin:"
    )
    if update.effective_message:
        await safe_telegram_call(
            lambda: update.effective_message.reply_text(welcome_text, parse_mode=ParseMode.HTML),
            "starting registration",
        )


async def is_user_registered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
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
        "Welcome to our official digital portal. Experience the <b>Vertex Green Brand</b> through simplified member services and financial growth.\n\n"
        "How can we help you grow today?"
    )

    if update.callback_query:
        await safe_telegram_call(
            lambda: update.callback_query.message.reply_text(
                text=welcome_text,
                reply_markup=home_keyboard(),
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
                reply_markup=home_keyboard(),
                parse_mode=ParseMode.HTML,
            ),
            "sending home screen",
        )


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
    if update.effective_message:
        await update.effective_message.reply_text( # Changed from ♻️ to 🔄
            "🔄 Your AI conversation has been cleared. You can start a fresh chat now.",
            reply_markup=home_keyboard(),
        )


async def show_ai_assistant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"<b>{BRAND_EMOJI} AI Assistant</b>\n\n"
        "Ask any question in your own words. The assistant will reply naturally using Vertex SACCO knowledge about membership, savings, loans, office details, and general SACCO guidance.\n\n"
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

    if data in FAQ_ITEMS:
        question, answer = FAQ_ITEMS[data]
        await send_or_edit(update, f"<b>{question}</b>\n\n{answer}", back_home_inline())
        return

    if data in SERVICES_CONTENT:
        title, body = SERVICES_CONTENT[data]
        await send_or_edit(update, f"<b>{title}</b>\n\n{body}", home_and_contact_inline())
        return

    if data in BRANCHES:
        branch = BRANCHES[data]
        await send_or_edit(
            update,
            (
                f"<b>{branch['name']}</b>\n\n"
                f"<b>Address:</b> {branch['address']}\n"
                f"<b>Phone:</b> {branch['phone']}\n"
                f"<b>Hours:</b> {branch['hours']}\n\n"
                "Tap the map button below for directions."
            ),
            branch_actions(data),
        )
        return

    if data.startswith("feedback|"):
        score = data.split("|", 1)[1]
        context.user_data["state"] = None
        logger.info(
            "Feedback received | user_id=%s | score=%s",
            update.effective_user.id if update.effective_user else "unknown",
            score,
        )
        stars = "★ " * int(score) + "☆ " * (5 - int(score))
        frames = [
            "<b>Recording your feedback</b>",
            f"<b>{stars.strip()}</b>",
            f"<b>Thank you for rating us {score}/5</b>",
        ]
        for frame in frames:
            try:
                await send_or_edit(
                    update,
                    frame,
                    None,
                )
                await asyncio.sleep(0.35)
            except Exception:
                break
        await send_or_edit(
            update,
            f"<b>✅ Feedback received</b>\n\n<b>{stars.strip()}</b>\n\nYour overall rating of <b>{score}/5</b> has been recorded. Thank you for helping us improve.",
            back_home_inline(),
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
        name = context.user_data.get(REG_DATA_NAME, "Unknown")
        
        # Save to Google Sheets
        await show_typing(update, context)
        success = await save_to_google_sheets(name, phone, user.id, user.username)
        
        if success:
            context.user_data[IS_REGISTERED_KEY] = True
            context.user_data["state"] = None
            context.user_data.pop(REG_DATA_NAME, None)
            await message.reply_text(
                "✅ Registration complete! Your profile has been synchronized with the Vertex SACCO database.",
            )
            await show_home(update, context)
        else:
            await message.reply_text(
                "There was an issue saving your registration. Our team has been notified, but you can try again or contact support.",
                reply_markup=phone_registration_keyboard()
            )
        return

    # --- Guard: Prevent use if not registered ---
    if not context.user_data.get(IS_REGISTERED_KEY):
        await start_registration(update, context)
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

    if state == STATE_CONTACT_ADMIN:
        if text == BTN_SUPPORT_CANCEL:
            context.user_data["state"] = None
            clear_support_draft(context)
            await safe_telegram_call(
                lambda: message.reply_text(
                    "Your support draft has been canceled.",
                    reply_markup=home_keyboard(),
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
                    reply_markup=home_keyboard(),
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
        logger.info("Written feedback | user_id=%s | feedback=%s", user.id, summarize_message(message))
        remember_message(context, "user", summarize_message(message))
        remember_message(context, "assistant", "Thank you for sharing your feedback. Your comment has been recorded.")
        await safe_telegram_call(
            lambda: message.reply_text(
                "Thank you for sharing your feedback. Your comment has been recorded.",
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
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing. Set it in your .env file.")

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
    main()
