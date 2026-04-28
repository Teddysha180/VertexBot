# Vertex SACCO Bot

A Telegram support bot for Vertex SACCO.

## Deployment on Render Web Service

1. Push this project to GitHub.
2. In Render, click `New +` -> `Web Service`.
3. Connect the `VertexBot` repository.
4. Use these settings:
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
5. Set the environment variables in Render:
   - `BOT_TOKEN`
   - `ADMIN_ID`
   - `GROQ_API_KEY` (optional)
   - `GROQ_MODEL` (optional)
   - `GOOGLE_SHEET_ID`
   - `GOOGLE_SERVICE_ACCOUNT_JSON`
6. Deploy the service.

The bot now starts a lightweight HTTP health server automatically when Render provides a `PORT`, so it can run as a `Web Service` while still using Telegram polling. Use `/health` as the Render and UptimeRobot health check path.

## Member registration

New users must register before using the bot:

1. Enter full name.
2. Share contact using Telegram's contact button.
3. The bot saves the registration to Google Sheets.

Recommended Google Sheet columns:

`timestamp | telegram_user_id | full_name | phone_number | telegram_username | registration_status`

Supported Google credentials:

- `GOOGLE_SERVICE_ACCOUNT_JSON`: full service account JSON in one environment variable
- `GOOGLE_SERVICE_ACCOUNT_FILE`: optional local JSON file path for local development

## Local setup

1. Create a `.env` file with the required secrets.
2. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Run locally:
   ```bash
   python bot.py
   ```

## Notes

- Do not commit `.env` to GitHub.
- If you want webhooks instead of polling, update the bot implementation and Render service type accordingly.
