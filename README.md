# Gabay AI Assistant

Gabay is a self-hosted, Docker-based AI assistant designed as a Telegram-first productivity tool. It acts as a unified gateway allowing users to manage Gmail, Google Drive, Notion, and Meta (Facebook/Instagram) properties autonomously.

## Features

- **Daily Briefing (`/brief`)**: Scans unread emails and Facebook/Instagram notifications to provide a prioritized, LLM-summarized update.
- **Content Reading (`/read`)**: Fetches unread emails and recent Notion pages (try "read my emails" or "what's new in Notion?").
- **Universal Search (`/search`)**: Deep-search across Google Drive and Notion directly from Telegram.
- **Seamless Saving**: Reply to any file or PDF with `/save` to upload it to Drive or save to Notion.
- **Agentic Intent**: Leverages Groq (Llama 3) to understand natural language requests.

## Quick Install

Gabay is now available as a Python package. You can install it directly via pip:

```bash
pip install gabay
```

Then run the setup wizard:
```bash
gabay config
```

## Setup Instructions (Docker)
Gabay uses both a **Bot** (commands) and a **Userbot** (acting as you).
1.  **Bot**: Create a bot via [@BotFather](https://t.me/botfather) to get your `TELEGRAM_BOT_TOKEN`.
2.  **API Credentials**: Go to [my.telegram.org](https://my.telegram.org/auth), log in, and create an "App" to get your `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`.
3.  **Phone Number**: Your `TELEGRAM_PHONE` is required to authenticate the Userbot session.

### 2. Google Cloud Setup (Gmail/Drive)
1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  **Enable APIs**: Enable both the **Gmail API** and **Google Drive API**.
3.  **OAuth Consent Screen**: 
    - Set up an "External" consent screen.
    - Under **Test Users**, add your own email address.
4.  **Create Credentials**: 
    - Create an **OAuth client ID** (Web application).
    - Add `http://localhost:8000/auth/google/callback` to **Authorized redirect URIs**.
5.  Get your **Client ID** and **Client Secret**.

### 3. Notion Setup
1.  Create an **Internal Integration**: Go to [Notion My Integrations](https://www.notion.com/my-integrations).
2.  Get your `NOTION_API_KEY`.
3.  **Share Database**: Open your Notion database, click "..." -> **Connect to**, and find your integration.
4.  Copy the **Database ID** from the URL (the string after the `/` and before the `?`).

### 4. Environment Variables
Create a `.env` file in the root directory:
```env
# Telegram
TELEGRAM_BOT_TOKEN="your_token"
TELEGRAM_API_ID=12345
TELEGRAM_API_HASH="your_hash"
TELEGRAM_PHONE="+123456789"

# LLM
GROQ_API_KEY="your_groq_key"

# Google OAuth
GOOGLE_CLIENT_ID="your_google_id"
GOOGLE_CLIENT_SECRET="your_google_secret"

# Notion
NOTION_API_KEY="your_notion_key"
NOTION_DATABASE_ID="your_database_id"
```

### 5. Running and Connecting
1.  **Start**: `docker-compose up -d --build`
2.  **Dashboard**: Send `/auth` to your bot on Telegram.
3.  **Login**: Open the link and click **Connect Account** for each service.

## Use Cases
- "Give me a briefing on my emails today."
- "Read my latest Notion notes."
- "Search for 'Project Alpha' on Drive."
- "Send an email to john@example.com saying I'll be late."
