import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# Run the bot instance
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TOKEN")
bot.run("MTUyNDAxNDk0MjU5OTExODg4OA.G8nthd.Sww19XtSfe48p2TlOc1mxZ_1bCQK09Z8MYLKv0")
print(repr(TOKEN))
