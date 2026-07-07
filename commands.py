import os
import json
from pathlib import Path
from datetime import timedelta

import discord
from discord.ext import commands
from dotenv import load_dotenv

# ---------- Setup ----------
load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CONFIG_FILE = DATA_DIR / "config.json"
WARNINGS_FILE = DATA_DIR / "warnings.json"

# ---------- Persistent Data ----------
default_config = {
    "whitelist": [],
    "antinuke": False,
    "antiraid": False,
    "antispam": False,
    "antibot": False
}

def load_json(path: Path, default):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return default
    return default

def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

config = load_json(CONFIG_FILE, default_config)
warnings = load_json(WARNINGS_FILE, {})

# Keep whitelist as a set in memory
config["whitelist"] = set(config.get("whitelist", []))

def save_config():
    serializable = dict(config)
    serializable["whitelist"] = list(config["whitelist"])
    save_json(CONFIG_FILE, serializable)

def save_warnings():
    save_json(WARNINGS_FILE, warnings)

# ---------- Checks ----------
def is_owner():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator or ctx.author == ctx.guild.owner
    return commands.check(predicate)

def is_whitelisted(member_id: int) -> bool:
    return member_id in config["whitelist"]

# ---------- Events ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} | ID: {bot.user.id}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    links = ("http://", "https://", "discord.gg")
    if any(link in message.content.lower() for link in links):
        if not message.author.guild_permissions.manage_messages and not is_whitelisted(message.author.id):
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            await message.channel.send(
                f"{message.author.mention}, links are not allowed.",
                delete_after=5
            )
            return

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You do not have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument provided.")
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        print(f"Error in command {ctx.command}: {error}")
        await ctx.send("❌ Something went wrong while running that command.")

# ---------- Moderation Helpers ----------
async def get_or_create_muted_role(guild: discord.Guild):
    role = discord.utils.get(guild.roles, name="Muted")
    if role is None:
        role = await guild.create_role(name="Muted", reason="Muted role created by bot")

        for channel in guild.channels:
            try:
                await channel.set_permissions(role, send_messages=False, speak=False, add_reactions=False)
            except discord.Forbidden:
                pass

    return role

# ---------- Commands ----------
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.kick(reason=reason)
    await ctx.send(f"✅ {member} has been kicked.\nReason: {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.ban(reason=reason)
    await ctx.send(f"✅ {member} has been banned.\nReason: {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    user = await bot.fetch_user(user_id)
    await ctx.guild.unban(user)
    await ctx.send(f"✅ Unbanned {user}")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason="No reason"):
    await member.timeout(timedelta(minutes=minutes), reason=reason)
    await ctx.send(f"⏳ {member.mention} timed out for {minutes} minutes.")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def untimeout(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"✅ Removed timeout from {member.mention}")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member):
    role = await get_or_create_muted_role(ctx.guild)
    await member.add_roles(role, reason=f"Muted by {ctx.author}")
    await ctx.send(f"🔇 {member.mention} muted.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if role:
        await member.remove_roles(role, reason=f"Unmuted by {ctx.author}")
        await ctx.send(f"🔊 {member.mention} unmuted.")
    else:
        await ctx.send("❌ Muted role not found.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔒 Channel locked.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔓 Channel unlocked.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🗑 Deleted {len(deleted) - 1} messages.", delete_after=3)

@bot.command()
@commands.has_permissions(kick_members=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    warnings.setdefault(str(member.id), [])
    warnings[str(member.id)].append(reason)
    save_warnings()

    await ctx.send(
        f"⚠️ {member.mention} warned.\n"
        f"Total Warnings: {len(warnings[str(member.id)])}"
    )

@bot.command()
async def warns(ctx, member: discord.Member):
    count = len(warnings.get(str(member.id), []))
    await ctx.send(f"{member.mention} has {count} warnings.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"🐢 Slowmode set to {seconds} seconds.")

@bot.command()
@commands.has_permissions(manage_nicknames=True)
async def nick(ctx, member: discord.Member, *, nickname):
    await member.edit(nick=nickname)
    await ctx.send(f"✏️ Nickname changed to {nickname}")

# ---------- Owner/Admin Settings ----------
@bot.command()
@is_owner()
async def whitelist(ctx, member: discord.Member):
    config["whitelist"].add(member.id)
    save_config()
    await ctx.send(f"✅ {member.mention} added to the whitelist.")

@bot.command()
@is_owner()
async def unwhitelist(ctx, member: discord.Member):
    config["whitelist"].discard(member.id)
    save_config()
    await ctx.send(f"❌ {member.mention} removed from the whitelist.")

@bot.command()
@is_owner()
async def whitelistlist(ctx):
    if not config["whitelist"]:
        return await ctx.send("Whitelist is empty.")

    names = []
    for uid in config["whitelist"]:
        user = ctx.guild.get_member(uid)
        names.append(user.mention if user else str(uid))

    await ctx.send("\n".join(names))

@bot.command()
@is_owner()
async def antinuke(ctx, state: str):
    config["antinuke"] = state.lower() == "on"
    save_config()
    await ctx.send(f"Anti Nuke: {'Enabled' if config['antinuke'] else 'Disabled'}")

@bot.command()
@is_owner()
async def antiraid(ctx, state: str):
    config["antiraid"] = state.lower() == "on"
    save_config()
    await ctx.send(f"Anti Raid: {'Enabled' if config['antiraid'] else 'Disabled'}")

@bot.command()
@is_owner()
async def antispam(ctx, state: str):
    config["antispam"] = state.lower() == "on"
    save_config()
    await ctx.send(f"Anti Spam: {'Enabled' if config['antispam'] else 'Disabled'}")

@bot.command()
@is_owner()
async def antibot(ctx, state: str):
    config["antibot"] = state.lower() == "on"
    save_config()
    await ctx.send(f"Anti Bot: {'Enabled' if config['antibot'] else 'Disabled'}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    links = ["http://", "https://", "discord.gg"]

    if any(link in message.content.lower() for link in links):
        if not message.author.guild_permissions.manage_messages:
            await message.delete()
            await message.channel.send(
                f"{message.author.mention}, links are not allowed.",
                delete_after=5
            )
            return

    await bot.process_commands(message)
# Run the bot instance
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TOKEN")
bot.run("MTUyNDAxNDk0MjU5OTExODg4OA.G8nthd.Sww19XtSfe48p2TlOc1mxZ_1bCQK09Z8MYLKv0")
print(repr(TOKEN))