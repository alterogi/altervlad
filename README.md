# Discord AI Chatbot with Soul

A lightweight Discord chatbot that uses an AI language model to respond to messages where it's mentioned. It defines its personality through a `soul.md` file and supports any OpenAI-compatible API provider (e.g., OpenAI, Deepseek, local LLMs).

## Features

- **Customizable Personality**: Edit the `soul.md` file to completely change how the bot behaves and responds.
- **Provider Agnostic**: Connect to any AI provider that supports the OpenAI Python client by changing the `API_BASE_URL` (Deepseek, Groq, Together AI, local models via LM Studio/Ollama, etc.).
- **Lightweight**: Minimal dependencies, easy to run anywhere.

## Setup

1. **Install Dependencies**
   Make sure you have Python 3.8+ installed.
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure the Environment**
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   Edit the `.env` file with your details:
   - `DISCORD_TOKEN`: Your bot token from the [Discord Developer Portal](https://discord.com/developers/applications). Make sure to enable the "Message Content Intent" in the Bot settings on the portal.
   - `API_KEY`: The API key from your chosen provider.
   - `API_BASE_URL`: The base URL of the API (e.g., `https://api.deepseek.com/v1` for Deepseek, leave blank for OpenAI).
   - `MODEL_NAME`: The model to use (e.g., `gpt-3.5-turbo`, `deepseek-chat`).

3. **Define the Soul**
   Edit `soul.md` to define the AI's system prompt. This acts as the core personality and instructions for the bot.

## Running the Bot

Run the bot script:

```bash
python bot.py
```

## Usage

In your Discord server, simply mention the bot to talk to it:

`@YourBotName hello there!`

The bot will process your message using the defined `soul.md` personality and respond in the same channel.

### Permissions & Anti-Spam
To prevent abuse and token wasting:
- **Character Limit:** Users can only send messages up to 1000 characters.
- **Max Response Tokens:** The bot will respond with a maximum of 800 tokens.
- **Usage Cooldown:** If a user consumes more than a set limit (e.g., 5000 tokens) across multiple messages, they will be placed on a cooldown (e.g., 1 hour). These can be customized via `.env` (`TOKEN_LIMIT`, `COOLDOWN_DURATION`).
- **Permissions System:** Server Administrators can restrict who talks to the bot using commands:
  - `!allow @user`: Adds a user to the allowlist. (If the allowlist is not empty, *only* allowed users can talk to the bot).
  - `!deny @user`: Adds a user to the denylist.
  - `!clear_perm @user`: Removes a user from both lists.

### Deployment & Update Announcements
Whenever new code is pushed to `main` and deployed, the bot will automatically post an update announcement upon reconnecting:
- **In-Character Commentary:** Vlad generates a sarcastic, cynical reaction to the update and Auggie's code changes.
- **Commit Details:** Shows the deployed commit hash, message, and author.
- **Target Channel:** Configure `UPDATE_CHANNEL_ID` in `.env` to pin announcements to a specific channel. If left blank, the bot automatically selects the server's system channel or default general/chat channel.
- **Deduplication:** State is recorded in persistent `./data` so announcements only trigger once per commit and never spam during routine restarts.


## Deploy (Docker)

This repo is **public**. Do not put tokens, API keys, or SSH keys in git.

- App secrets (`DISCORD_TOKEN`, `API_KEY`, …) live in a host-only `.env` (see `.env.example`).
- Allow/deny + usage JSON persist in `./data` on the host.
- A host timer pulls `main` about once a minute, runs pytest, then `docker compose up -d --build`.

```bash
cp .env.example .env   # fill real values, chmod 600
mkdir -p data
docker compose up -d --build
```
