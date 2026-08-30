import os
import discord
from discord.ext import commands
from openai import AsyncOpenAI
from dotenv import load_dotenv

import json

# Load environment variables
load_dotenv()

# Discord settings
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# AI API Settings (OpenAI compatible)
API_KEY = os.getenv('API_KEY', '')
BASE_URL = os.getenv('API_BASE_URL', '') # E.g., 'https://api.deepseek.com/v1' for Deepseek
MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-3.5-turbo')
SOUL_FILE = os.getenv('SOUL_FILE', 'soul.md')

# Initialize OpenAI Client (Asynchronous)
client_kwargs = {'api_key': API_KEY}
if BASE_URL:
    client_kwargs['base_url'] = BASE_URL
ai_client = AsyncOpenAI(**client_kwargs)

# Load Soul
try:
    with open(SOUL_FILE, 'r', encoding='utf-8') as f:
        SOUL_PROMPT = f.read()
except FileNotFoundError:
    print(f"Warning: {SOUL_FILE} not found. Using default personality.")
    SOUL_PROMPT = "You are a helpful assistant."

# Set up Discord Intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

PERMISSIONS_FILE = 'permissions.json'

def load_permissions():
    if not os.path.exists(PERMISSIONS_FILE):
        return {"allowlist": [], "denylist": []}
    try:
        with open(PERMISSIONS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading permissions: {e}")
        return {"allowlist": [], "denylist": []}

def save_permissions(perms):
    with open(PERMISSIONS_FILE, 'w') as f:
        json.dump(perms, f, indent=4)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.event
async def on_message(message):
    # Don't respond to ourselves
    if message.author == bot.user:
        return

    # Check if the bot is mentioned
    if bot.user in message.mentions:
        # Enforce Permissions
        perms = load_permissions()
        user_id = str(message.author.id)

        if user_id in perms.get('denylist', []):
            await message.reply("You do not have permission to talk to me.")
            return

        # If allowlist has entries, only allowed users can talk
        allowlist = perms.get('allowlist', [])
        if allowlist and user_id not in allowlist:
            await message.reply("You do not have permission to talk to me.")
            return

        # Remove the mention from the message to not confuse the AI
        user_message = message.content.replace(bot.user.mention, '').strip()

        # Enforce anti-spam / max character limit
        if len(user_message) > 1000:
            await message.reply("Your message is too long. Please keep it under 1000 characters.")
            return

        async with message.channel.typing():
            try:
                # Prepare messages list with the system prompt (soul)
                messages = [
                    {"role": "system", "content": SOUL_PROMPT},
                    {"role": "user", "content": f"{message.author.display_name}: {user_message}"}
                ]

                # Call the AI API
                response = await ai_client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    max_tokens=800, # Limit response size to prevent token wasting
                    # Optional: Add other parameters like temperature here if needed
                )

                # Get the response text
                ai_reply = response.choices[0].message.content

                # Discord has a 2000 character limit per message
                # If the response is longer, we should split it or truncate it
                if len(ai_reply) > 2000:
                    for i in range(0, len(ai_reply), 2000):
                        await message.channel.send(ai_reply[i:i+2000])
                else:
                    await message.reply(ai_reply)

            except Exception as e:
                print(f"Error calling AI API: {e}")
                await message.reply("Sorry, I encountered an error while thinking about that.")

    # Process commands if we add any later
    await bot.process_commands(message)

@bot.command(name="allow")
@commands.has_permissions(administrator=True)
async def allow_user(ctx, user: discord.User):
    perms = load_permissions()
    user_id = str(user.id)
    if user_id in perms.get('denylist', []):
        perms['denylist'].remove(user_id)
    if user_id not in perms.get('allowlist', []):
        perms.setdefault('allowlist', []).append(user_id)
    save_permissions(perms)
    await ctx.send(f"{user.display_name} has been added to the allowlist.")

@bot.command(name="deny")
@commands.has_permissions(administrator=True)
async def deny_user(ctx, user: discord.User):
    perms = load_permissions()
    user_id = str(user.id)
    if user_id in perms.get('allowlist', []):
        perms['allowlist'].remove(user_id)
    if user_id not in perms.get('denylist', []):
        perms.setdefault('denylist', []).append(user_id)
    save_permissions(perms)
    await ctx.send(f"{user.display_name} has been added to the denylist.")

@bot.command(name="clear_perm")
@commands.has_permissions(administrator=True)
async def clear_perm(ctx, user: discord.User):
    perms = load_permissions()
    user_id = str(user.id)
    removed = False
    if user_id in perms.get('allowlist', []):
        perms['allowlist'].remove(user_id)
        removed = True
    if user_id in perms.get('denylist', []):
        perms['denylist'].remove(user_id)
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

if __name__ == '__main__':
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set.")
    else:
        bot.run(DISCORD_TOKEN)
