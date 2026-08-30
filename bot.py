import json
import os
import time

import discord
from discord.ext import commands
from dotenv import load_dotenv
from openai import AsyncOpenAI

from logic import (
    apply_usage,
    can_talk,
    cooldown_remaining,
    empty_permissions,
    message_too_long,
    split_chunks,
    strip_mention,
)

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

API_KEY = os.getenv("API_KEY", "")
BASE_URL = os.getenv("API_BASE_URL", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-3.5-turbo")
SOUL_FILE = os.getenv("SOUL_FILE", "soul.md")

TOKEN_LIMIT = int(os.getenv("TOKEN_LIMIT", "5000"))
COOLDOWN_DURATION = int(os.getenv("COOLDOWN_DURATION", "3600"))

PERMISSIONS_FILE = os.getenv("PERMISSIONS_FILE", "permissions.json")
USAGE_FILE = os.getenv("USAGE_FILE", "usage.json")

client_kwargs = {"api_key": API_KEY}
if BASE_URL:
    client_kwargs["base_url"] = BASE_URL
ai_client = AsyncOpenAI(**client_kwargs)

try:
    with open(SOUL_FILE, "r", encoding="utf-8") as f:
        SOUL_PROMPT = f.read()
except FileNotFoundError:
    print(f"Warning: {SOUL_FILE} not found. Using default personality.")
    SOUL_PROMPT = "You are a helpful assistant."

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def _ensure_parent(path):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def load_permissions():
    if not os.path.exists(PERMISSIONS_FILE):
        return empty_permissions()
    try:
        with open(PERMISSIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return empty_permissions()
        data.setdefault("allowlist", [])
        data.setdefault("denylist", [])
        return data
    except Exception as e:
        print(f"Error loading permissions: {e}")
        return empty_permissions()


def save_permissions(perms):
    _ensure_parent(PERMISSIONS_FILE)
    with open(PERMISSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(perms, f, indent=4)


def load_usage():
    if not os.path.exists(USAGE_FILE):
        return {}
    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"Error loading usage: {e}")
        return {}


def save_usage(usage):
    _ensure_parent(USAGE_FILE)
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(usage, f, indent=4)


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")


@bot.event
async def on_message(message):
    me = bot.user
    if me is None or message.author == me:
        return

    if me in message.mentions:
        perms = load_permissions()
        user_id = str(message.author.id)

        if not can_talk(user_id, perms):
            await message.reply("You do not have permission to talk to me.")
            return

        user_message = strip_mention(message.content, me.mention)

        if message_too_long(user_message):
            await message.reply("Your message is too long. Please keep it under 1000 characters.")
            return

        usage_data = load_usage()
        user_usage = usage_data.get(user_id, {"tokens": 0, "cooldown_until": 0})
        current_time = time.time()
        remaining = cooldown_remaining(user_usage, current_time)
        if remaining:
            minutes, seconds = divmod(remaining, 60)
            await message.reply(
                f"You are on a cooldown. Please wait {minutes}m {seconds}s before talking to me again."
            )
            return

        async with message.channel.typing():
            try:
                messages = [
                    {"role": "system", "content": SOUL_PROMPT},
                    {"role": "user", "content": f"{message.author.display_name}: {user_message}"},
                ]

                response = await ai_client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    max_tokens=800,
                )

                ai_reply = response.choices[0].message.content or ""
                chunks = split_chunks(ai_reply, 2000)
                if len(chunks) == 1:
                    await message.reply(chunks[0])
                else:
                    for chunk in chunks:
                        await message.channel.send(chunk)

                tokens_used = response.usage.total_tokens if response.usage else 0
                usage_data[user_id] = apply_usage(
                    user_usage,
                    tokens_used,
                    current_time,
                    TOKEN_LIMIT,
                    COOLDOWN_DURATION,
                )
                save_usage(usage_data)

            except Exception as e:
                print(f"Error calling AI API: {e}")
                await message.reply("Sorry, I encountered an error while thinking about that.")

    await bot.process_commands(message)


@bot.command(name="allow")
@commands.has_permissions(administrator=True)
async def allow_user(ctx, user: discord.User):
    perms = load_permissions()
    user_id = str(user.id)
    if user_id in perms.get("denylist", []):
        perms["denylist"].remove(user_id)
    if user_id not in perms.get("allowlist", []):
        perms.setdefault("allowlist", []).append(user_id)
    save_permissions(perms)
    await ctx.send(f"{user.display_name} has been added to the allowlist.")


@bot.command(name="deny")
@commands.has_permissions(administrator=True)
async def deny_user(ctx, user: discord.User):
    perms = load_permissions()
    user_id = str(user.id)
    if user_id in perms.get("allowlist", []):
        perms["allowlist"].remove(user_id)
    if user_id not in perms.get("denylist", []):
        perms.setdefault("denylist", []).append(user_id)
    save_permissions(perms)
    await ctx.send(f"{user.display_name} has been added to the denylist.")


@bot.command(name="clear_perm")
@commands.has_permissions(administrator=True)
async def clear_perm(ctx, user: discord.User):
    perms = load_permissions()
    user_id = str(user.id)
    removed = False
    if user_id in perms.get("allowlist", []):
        perms["allowlist"].remove(user_id)
        removed = True
    if user_id in perms.get("denylist", []):
        perms["denylist"].remove(user_id)
        removed = True

    if removed:
        save_permissions(perms)
        await ctx.send(f"Permissions cleared for {user.display_name}.")
    else:
        await ctx.send(f"{user.display_name} is not in any list.")


@allow_user.error
@deny_user.error
@clear_perm.error
async def perm_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need administrator permissions to use this command.")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set.")
    else:
        bot.run(DISCORD_TOKEN)
