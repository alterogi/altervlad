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
    format_update_message,
    format_update_prompt,
    get_fallback_update_message,
    message_too_long,
    should_announce_update,
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
MEMORY_FILE = os.getenv("MEMORY_FILE", "data/memory.json")
UPDATE_CHANNEL_ID = os.getenv("UPDATE_CHANNEL_ID")
DEPLOY_INFO_FILE = os.getenv("DEPLOY_INFO_FILE", "data/deployed_info.json")
DEPLOYED_SHA_FILE = os.getenv("DEPLOYED_SHA_FILE", "data/.deployed_sha")
LAST_ANNOUNCED_FILE = os.getenv("LAST_ANNOUNCED_FILE", "data/.last_announced_sha")

client_kwargs = {"api_key": API_KEY}
if BASE_URL:
    client_kwargs["base_url"] = BASE_URL
ai_client = AsyncOpenAI(**client_kwargs)

from collections import defaultdict, deque

try:
    with open(SOUL_FILE, "r", encoding="utf-8") as f:
        SOUL_PROMPT = f.read()
except FileNotFoundError:
    print(f"Warning: {SOUL_FILE} not found. Using default personality.")
    SOUL_PROMPT = "You are a helpful assistant."

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
_has_announced_update = False

# Dictionary storing conversation history by channel id (up to 10 latest messages)
conversation_history = defaultdict(lambda: deque(maxlen=10))


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


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"Error loading memory: {e}")
        return {}


def save_memory(memory):
    _ensure_parent(MEMORY_FILE)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=4)


def load_deployed_info() -> dict:
    for path in [DEPLOY_INFO_FILE, "/app/data/deployed_info.json", "data/deployed_info.json"]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("sha"):
                    return data
            except Exception as e:
                print(f"Error loading deploy info from {path}: {e}")

    for path in [DEPLOYED_SHA_FILE, "/app/data/.deployed_sha", "data/.deployed_sha"]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    sha = f.read().strip()
                if sha:
                    return {
                        "sha": sha,
                        "short_sha": sha[:7],
                        "message": "",
                        "author": "",
                    }
            except Exception as e:
                print(f"Error reading deployed SHA from {path}: {e}")

    try:
        import subprocess
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        msg = subprocess.check_output(["git", "log", "-1", "--pretty=%s"], text=True, stderr=subprocess.DEVNULL).strip()
        author = subprocess.check_output(["git", "log", "-1", "--pretty=%an"], text=True, stderr=subprocess.DEVNULL).strip()
        return {
            "sha": sha,
            "short_sha": sha[:7],
            "message": msg,
            "author": author,
        }
    except Exception:
        pass

    return {}


def load_last_announced_sha() -> str:
    for path in [LAST_ANNOUNCED_FILE, "/app/data/.last_announced_sha", "data/.last_announced_sha"]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception as e:
                print(f"Error reading last announced sha: {e}")
    return ""


def save_last_announced_sha(sha: str):
    _ensure_parent(LAST_ANNOUNCED_FILE)
    try:
        with open(LAST_ANNOUNCED_FILE, "w", encoding="utf-8") as f:
            f.write(sha.strip() + "\n")
    except Exception as e:
        print(f"Error saving last announced sha: {e}")


def find_update_channel(bot_instance: commands.Bot) -> discord.TextChannel | None:
    if UPDATE_CHANNEL_ID:
        try:
            cid = int(UPDATE_CHANNEL_ID.strip())
            channel = bot_instance.get_channel(cid)
            if channel and isinstance(channel, discord.TextChannel):
                return channel
        except ValueError:
            print(f"Invalid UPDATE_CHANNEL_ID: {UPDATE_CHANNEL_ID}")

    for guild in bot_instance.guilds:
        if guild.system_channel:
            perms = guild.system_channel.permissions_for(guild.me)
            if perms.send_messages:
                return guild.system_channel

        preferred_names = ("general", "chat", "main", "discussion", "bot-spam", "bots", "altervlad")
        text_channels = [ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages]

        for name in preferred_names:
            for ch in text_channels:
                if ch.name.lower() == name:
                    return ch

        if text_channels:
            return text_channels[0]

    return None


async def check_and_post_deployment_update():
    global _has_announced_update
    if _has_announced_update:
        return
    _has_announced_update = True

    deploy_info = load_deployed_info()
    current_sha = deploy_info.get("sha")
    last_announced = load_last_announced_sha()

    if not should_announce_update(current_sha, last_announced):
        return

    channel = find_update_channel(bot)
    if not channel:
        print(f"Deployment detected ({current_sha[:7] if current_sha else 'unknown'}), but no suitable channel was found to post.")
        if current_sha:
            save_last_announced_sha(current_sha)
        return

    print(f"Announcing deployment ({deploy_info.get('short_sha') or current_sha[:7]}) in #{channel.name} ({channel.guild.name})")

    ai_reaction = ""
    try:
        prompt = format_update_prompt(deploy_info)
        messages = [
            {"role": "system", "content": SOUL_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = await ai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=300,
        )
        ai_reaction = response.choices[0].message.content or ""
    except Exception as e:
        print(f"Error generating deployment reaction from AI: {e}")

    if ai_reaction.strip():
        final_message = format_update_message(ai_reaction, deploy_info)
    else:
        final_message = get_fallback_update_message(deploy_info)

    try:
        chunks = split_chunks(final_message, 2000)
        for chunk in chunks:
            await channel.send(chunk)
        if current_sha:
            save_last_announced_sha(current_sha)
    except Exception as e:
        print(f"Error sending deployment announcement: {e}")


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    await check_and_post_deployment_update()



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
                channel_id = str(message.channel.id)
                history = list(conversation_history[channel_id])

                system_prompt = SOUL_PROMPT
                memory = load_memory()
                if memory:
                    memory_str = "\n".join(f"- {k}: {v}" for k, v in memory.items())
                    system_prompt += f"\n\nHere are some things you should remember:\n{memory_str}"

                messages = [{"role": "system", "content": system_prompt}]
                for entry in history:
                    messages.append(entry)

                messages.append({"role": "user", "content": f"{message.author.display_name}: {user_message}"})

                response = await ai_client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    max_tokens=800,
                )

                ai_reply = response.choices[0].message.content or ""

                conversation_history[channel_id].append({"role": "user", "content": f"{message.author.display_name}: {user_message}"})
                conversation_history[channel_id].append({"role": "assistant", "content": ai_reply})

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


@bot.command(name="remember")
async def remember(ctx, key: str, *, value: str):
    """Store a piece of information in the bot's memory."""
    memory = load_memory()
    memory[key] = value
    save_memory(memory)
    await ctx.send(f"I will remember that {key} is {value}.")


@bot.command(name="forget")
async def forget(ctx, key: str):
    """Forget a piece of information from the bot's memory."""
    memory = load_memory()
    if key in memory:
        del memory[key]
        save_memory(memory)
        await ctx.send(f"I have forgotten {key}.")
    else:
        await ctx.send(f"I don't have any memory of {key}.")


@bot.command(name="memory")
async def show_memory(ctx):
    """Show the current contents of the bot's memory."""
    memory = load_memory()
    if not memory:
        await ctx.send("My memory is currently empty.")
    else:
        memory_str = "\n".join(f"**{k}**: {v}" for k, v in memory.items())
        await ctx.send(f"Here is what I remember:\n{memory_str}")


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
