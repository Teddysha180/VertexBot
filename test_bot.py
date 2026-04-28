#!/usr/bin/env python3
"""
Basic configuration test for the Vertex SACCO bot.
"""

import os
import sys
import json


def test_config() -> bool:
    print("Testing Vertex SACCO Bot configuration...\n")

    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")

    if not os.path.exists(".env"):
        print(".env file not found.")
        print("\nCreate a .env file with:")
        print("BOT_TOKEN=your_telegram_bot_token")
        print("ADMIN_ID=your_telegram_user_id")
        print("GROQ_API_KEY=your_groq_api_key")
        return False

    print(".env file found")

    from dotenv import load_dotenv

    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token or bot_token == "your_telegram_bot_token":
        print("BOT_TOKEN is missing or still set to the placeholder value.")
        return False
    print(f"BOT_TOKEN configured (length: {len(bot_token)})")

    admin_id = os.getenv("ADMIN_ID")
    if admin_id:
        print(f"ADMIN_ID configured: {admin_id}")
    else:
        print("ADMIN_ID not set. Contact Admin forwarding will stay local only.")

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        print(f"GROQ_API_KEY configured (length: {len(groq_key)})")
    else:
        print("GROQ_API_KEY not set. AI fallback logic will be used.")

    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if sheet_id:
        if "spreadsheets/d/" in sheet_id:
            clean_id = sheet_id.split("spreadsheets/d/")[1].split("/")[0]
            print(f"GOOGLE_SHEET_ID configured (URL detected, extracted ID: {clean_id})")
        else:
            print(f"GOOGLE_SHEET_ID configured: {sheet_id}")
    else:
        print("GOOGLE_SHEET_ID not set. Registrations will not be saved to Sheets.")

    gs_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if gs_json:
        try:
            info = json.loads(gs_json)
            client_email = info.get('client_email')
            print(f"GOOGLE_SERVICE_ACCOUNT_JSON is valid.")
            print(f"👉 SHARE YOUR SHEET WITH THIS EMAIL: {client_email}")
        except json.JSONDecodeError:
            print("ERROR: GOOGLE_SERVICE_ACCOUNT_JSON is detected but is NOT valid JSON.")
            return False

    groq_model = os.getenv("GROQ_MODEL")
    if groq_model:
        print(f"GROQ_MODEL configured: {groq_model}")

    required_packages = ["telegram", "dotenv", "gspread", "google.oauth2"]
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
            print(f"{package} installed")
        except ImportError:
            missing_packages.append(package)
            print(f"{package} NOT installed")

    if missing_packages:
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False

    print("\nConfiguration looks good.")
    print("Run the bot with: python bot.py")
    return True


if __name__ == "__main__":
    test_config()
