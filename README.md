# Vertex SACCO Bot

A Telegram support bot for Vertex SACCO.

## Deployment

1. Create a GitHub repository and push this project.
2. Create a Render account and connect the GitHub repository.
3. In Render, create a new Python service using this repo.
4. Set the environment variables in Render:
   - `BOT_TOKEN`
   - `ADMIN_ID`
   - `GROQ_API_KEY` (optional)
   - `GROQ_MODEL` (optional)
5. Render will install dependencies from `requirements.txt` and start the bot with `python bot.py`.

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
