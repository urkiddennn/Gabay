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

## 🚀 Deployment & Setup

Gabay uses a **Bot** for commands and a **Userbot** for acting on your behalf. Follow these steps for a complete setup.

### 1. Telegram API Configuration
1.  **Create a Bot**: Find [@BotFather](https://t.me/botfather) on Telegram.
    -   Type `/newbot` and follow the instructions.
    -   Save your **Bot Token** (e.g., `123456:ABC-DEF...`).
2.  **Get API Credentials**:
    -   Log in to [my.telegram.org](https://my.telegram.org/auth).
    -   Go to **API development tools**.
    -   Create a new application (title/short name don't matter).
    -   Save your `App api_id` and `App api_hash`.
3.  **Authentication**: Your `TELEGRAM_PHONE` (with country code, e.g., `+123456789`) is required for the initial Userbot session login.

### 2. Google Cloud Integration (Workspace Management)
Gabay requires access to Gmail, Drive, Docs, Slides, and Sheets.

1.  **Create Project**: Go to [Google Cloud Console](https://console.cloud.google.com/) and create a new project named "Gabay".
2.  **Enable APIs**: Navigate to **APIs & Services > Library** and enable:
    -   `Gmail API`
    -   `Google Drive API`
    -   `Google Docs API`
    -   `Google Slides API`
    -   `Google Sheets API`
3.  **OAuth Consent Screen**:
    -   User Type: **External**.
    -   App Information: Set "Gabay".
    -   **Scopes**: Add `https://www.googleapis.com/auth/gmail.modify`, `https://www.googleapis.com/auth/drive`, `https://www.googleapis.com/auth/calendar.readonly`. 
    -   **Test Users**: Add your own Gmail address (Gabay will only work for these users in testing mode).
4.  **Create Credentials**:
    -   Go to **Credentials > Create Credentials > OAuth client ID**.
    -   Application type: **Web application**.
    -   Name: "Gabay Web Client".
    -   Authorized redirect URIs: `http://localhost:8000/auth/google/callback`.
    -   Save the **Client ID** and **Client Secret**.

### 3. Notion Integration
1.  **Create Integration**: Go to [Notion My Integrations](https://www.notion.com/my-integrations).
    -   Click **+ New integration**.
    -   Type: **Internal**.
    -   Save your **Internal Integration Secret**.
2.  **Permissions**: Ensure "Read content", "Update content", and "Insert content" are checked.
3.  **Connect Database**:
    -   Open your target Notion database/page.
    -   Click `...` (top right) > **Connect to** > Search for your integration name.
4.  **Retrieve IDs**:
    -   `NOTION_API_KEY`: The secret from step 1.
    -   `NOTION_DATABASE_ID`: The ID from your database URL (the part after `notion.so/` and before the next `/` or `?`).

### 4. Environment Configuration
Create a `.env` file in the root directory:
```env
# Telegram
TELEGRAM_BOT_TOKEN="your_token"
TELEGRAM_API_ID=12345
TELEGRAM_API_HASH="your_hash"
TELEGRAM_PHONE="+123456789"

# LLM Intelligence
GROQ_API_KEY="your_groq_key"

# Google OAuth
GOOGLE_CLIENT_ID="your_google_id"
GOOGLE_CLIENT_SECRET="your_google_secret"

# Notion
NOTION_API_KEY="your_notion_key"
NOTION_DATABASE_ID="your_database_id"
```

### 5. Launching Gabay
1.  **Start Services**: `docker-compose up -d --build`
2.  **Initial Connection**: 
    -   Go to your Telegram bot and type `/auth`.
    -   Open the provided dashboard link (`http://localhost:8000/setup`).
    -   Click **Connect Google** and **Connect Notion** to authorize Gabay.

## 🧠 Brain & Memory
Gabay is powered by **Groq (Llama 3)** and features:
- **Extended Memory**: Remembers up to 20 messages for deep context.
- **Natural Language Parsing**: "Research AI and email it to my boss" works in one go.
- **Short-term Recurrence**: "Remind me to check the oven every minute for 5 times."

## 📚 Use Cases & Examples
- **Daily Recap**: `/brief` (Summarizes unread emails and Meta notifications).
- **Researcher**: "Research the history of Mars, save it to a Doc, and make it public."
- **Analyst**: "Create a spreadsheet about the top 10 EV companies in 2025."
- **Presenter**: "Make a professional deck about space exploration and invite partner@example.com."
