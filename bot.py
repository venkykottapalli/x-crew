import os
import re
import time
import asyncio
import discord
from discord.ext import commands
import aiohttp
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)
# ==================== CONFIGURATION ====================
TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # Keep your token secure in environment variables

# Anti-Nuke Thresholds
NUKE_ACTION_LIMIT = 3       # Max destructive actions allowed...
NUKE_TIME_WINDOW = 5        # ...within this many seconds.

# Suspect Domain Patterns (Typosquatting/Phishing heuristics)
SUSPECT_KEYWORDS = ["nitro", "gift", "classic", "airdrop", "steam", "crypto"]
OFFICIAL_DOMAINS = ["discord.com", "discord.gg", "discord.media", "discordapp.com", "discordapp.net"]
# =======================================================

class SecurityBot(commands.Bot):
    def __init__(self):
        # Explicitly request required privileged intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.moderation = True
        
        super().__init__(command_prefix="!", intents=intents)
        
        # In-memory trackers
        self.action_history = {}  # Format: {user_id: [timestamp1, timestamp2, ...]}
        self.session = None

    async def setup_hook(self):
        # Initialize aiohttp session for non-blocking external URL evaluation
        self.session = aiohttp.ClientSession()
        print("Asynchronous HTTP session initialized.")

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

bot = SecurityBot()

@bot.event
async def on_ready():
    print(f"Logged in safely as {bot.user.name} (ID: {bot.user.id})")
    print("Security monitoring status: ACTIVE")

# ==================== EXTRACTION ENGINE (ANTI-PHISHING) ====================
@bot.event
async def on_message(message):
    # Ignore bot messages to avoid infinite feedback loops
    if message.author.bot or not message.guild:
        return

    # Extract all URLs using Regex
    urls = re.findall(r'(https?://[^\s]+)', message.content.lower())
    
    for url in urls:
        # Clean domain extraction
        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if not domain_match:
            continue
        domain = domain_match.group(1)

        # Check if the domain is a clever lookalike (Typosquatting)
        is_phishing = False
        if domain not in OFFICIAL_DOMAINS:
            for word in SUSPECT_KEYWORDS:
                if word in domain:
                    is_phishing = True
                    break

        if is_phishing:
            try:
                # 1. Instantly delete payload
                await message.delete()
                
                # 2. Quarantine compromised account
                await message.author.timeout(discord.utils.utcnow() + asyncio.timedelta(hours=24), reason="Suspicious phishing link detected.")
                
                # 3. Alert Server Owners/Logs
                alert_channel = discord.utils.get(message.guild.text_channels, name="security-alerts")
                if alert_channel:
                    await alert_channel.send(
                        f"🚨 **PHISHING ATTEMPT DETECTED** 🚨\n"
                        f"**User:** {message.author.mention} ({message.author.id})\n"
                        f"**Action:** Message deleted & user timed out for 24h.\n"
                        f"**Caught Domain:** `{domain}`"
                    )
                return  # Stop processing further links if one is malicious
            except discord.Forbidden:
                print(f"Missing permissions to moderate {message.author.name} in {message.guild.name}")
            except Exception as e:
                print(f"Error handling phishing: {e}")

    await bot.process_commands(message)

# ==================== VELOCITY ENGINE (ANTI-NUKE) ====================
@bot.event
async def on_audit_log_entry_create(entry):
    # Monitor destructive administrative actions
    destructive_actions = [
        discord.AuditLogAction.channel_delete,
        discord.AuditLogAction.member_ban,
        discord.AuditLogAction.member_kick,
        discord.AuditLogAction.role_delete
    ]

    if entry.action not in destructive_actions:
        return

    guild = entry.guild
    moderator = entry.user

    # Bypass if the system itself or the guild owner performs the action
    if moderator.id == bot.user.id or moderator.id == guild.owner_id:
        return

    current_time = time.time()
    user_id = moderator.id

    if user_id not in bot.action_history:
        bot.action_history[user_id] = []

    # Append current event and clear timestamps outside the monitoring window
    bot.action_history[user_id].append(current_time)
    bot.action_history[user_id] = [t for t in bot.action_history[user_id] if current_time - t <= NUKE_TIME_WINDOW]

    # Check if threshold is breached
    if len(bot.action_history[user_id]) >= NUKE_ACTION_LIMIT:
        await execute_quarantine_protocol(guild, moderator)

async def execute_quarantine_protocol(guild, member):
    print(f"⚠️ THRESHOLD BREACHED: Executing Guillotine Protocol on {member.name} ({member.id})")
    
    # 1. Strip all dangerous permissions/roles immediately
    for role in member.roles:
        if role.is_default():  # Skip @everyone
            continue
        try:
            await member.remove_roles(role, reason="Anti-Nuke Triggered: Velocity threshold breached.")
        except discord.Forbidden:
            print(f"Could not remove role {role.name} due to hierarchy limitations.")

    # 2. Isolate user entirely via Timeout
    try:
        await member.timeout(discord.utils.utcnow() + asyncio.timedelta(days=7), reason="Anti-Nuke Isolation.")
    except discord.Forbidden:
        print("Failed to timeout user due to permissions.")

    # 3. Log incident natively
    alert_channel = discord.utils.get(guild.text_channels, name="security-alerts")
    if alert_channel:
        await alert_channel.send(
            f"⛔ **ANTI-NUKE TRIGGERED** ⛔\n"
            f"**Target:** {member.mention} ({member.id})\n"
            f"**Status:** Stripped of roles and isolated for 7 days.\n"
            f"**Reason:** Exceeded {NUKE_ACTION_LIMIT} administrative deletions within {NUKE_TIME_WINDOW} seconds."
        )

# Run the bot instance
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TOKEN")
bot.run("MTUyNDAxNDk0MjU5OTExODg4OA.G8nthd.Sww19XtSfe48p2TlOc1mxZ_1bCQK09Z8MYLKv0")
print(repr(TOKEN))