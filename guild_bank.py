import discord
from discord import app_commands
from discord.ext import commands
import json
import asyncio
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID"))

GUILD_BANK_FILE = "guild_bank.json"

intents = discord.Intents.default()
intents.messages = True  # Ensure the bot can read messages
intents.guilds = True  # Allow interaction with guild information
intents.message_content = True  # Required for processing user commands

# Load or initialize guild bank data
def load_guild_bank():
    try:
        with open(GUILD_BANK_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"mesos": 0, "items": {}, "history": [], "contributions": {}}

def save_guild_bank(data):
    with open(GUILD_BANK_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

bank = load_guild_bank()

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
admin_role = "Goddess"  # Change to your actual admin role

@bot.event
async def on_ready():
    await tree.sync()
    print(f'Logged in as {bot.user}')

@tree.command(name="deposit", description="Deposit mesos into the guild bank")
async def deposit(interaction: discord.Interaction, amount: int):
    user = str(interaction.user.id)
    timestamp = get_timestamp()
    
    bank["mesos"] += amount
    bank["contributions"].setdefault(user, 0)
    bank["contributions"][user] += amount
    bank["history"].append(f"[{timestamp}] {interaction.user.name} deposited {amount} mesos.")
    save_guild_bank(bank)
    
    await interaction.response.send_message(f"✅ {interaction.user.name} deposited {amount} mesos into the Guild Bank!")

@tree.command(name="deposit_item", description="Deposit an item into the guild bank")
async def deposit_item(interaction: discord.Interaction, item: str, quantity: int):
    user = str(interaction.user.id)
    timestamp = get_timestamp()

    if item in bank["items"]:
        bank["items"][item] += quantity
    else:
        bank["items"][item] = quantity
    
    bank["history"].append(f"[{timestamp}] {interaction.user.name} deposited {quantity} {item}(s).")
    save_guild_bank(bank)
    
    await interaction.response.send_message(f"✅ {interaction.user.name} deposited {quantity} {item}(s) into the Guild Bank!")

@tree.command(name="bank_history", description="View the bank transaction history (Admins only)")
async def bank_history(interaction: discord.Interaction):
    history = "\n".join(bank["history"][-10:])  # Show last 10 transactions
    await interaction.response.send_message(f"📜 **Guild Bank History:**\n```{history}```")

@tree.command(name="request_withdraw", description="Request to withdraw mesos from the guild bank")
async def request_withdraw(interaction: discord.Interaction, amount: int):
    timestamp = get_timestamp()

    if bank["mesos"] < amount:
        await interaction.response.send_message("❌ Not enough mesos in the bank.")
        return
    
    bank["history"].append(f"[{timestamp}] {interaction.user.name} requested to withdraw {amount} mesos.")
    save_guild_bank(bank)

    await interaction.response.send_message(f"⚠️ {interaction.user.name} requested to withdraw {amount} mesos. An admin needs to approve.")

@tree.command(name="approve_withdraw", description="Approve a mesos withdrawal request (Admins only)")
async def approve_withdraw(interaction: discord.Interaction, user: discord.Member, amount: int):
    timestamp = get_timestamp()

    if bank["mesos"] < amount:
        await interaction.response.send_message("❌ Not enough mesos in the bank.")
        return
    
    bank["mesos"] -= amount
    bank["history"].append(f"[{timestamp}] {user.name} withdrew {amount} mesos, approved by {interaction.user.name}.")
    save_guild_bank(bank)
    
    await interaction.response.send_message(f"✅ {amount} mesos withdrawn by {user.name}, approved by {interaction.user.name}.")

@tree.command(name="check_bank", description="Check the current bank balance and stored items.")
async def check_bank(interaction: discord.Interaction):
    """Displays the mesos and items stored in the bank."""
    mesos = bank["mesos"]
    items = "\n".join([f"{item}: {amount}" for item, amount in bank["items"].items()]) or "No items stored."
    
    await interaction.response.send_message(f"🏦 **Guild Bank:**\n💰 Mesos: {mesos}\n📦 Items:\n{items}")

@tree.command(name="erase_history", description="Erase the bank transaction history (Admins only)")
async def erase_history(interaction: discord.Interaction):
    """Prompt to erase the bank history"""
    if interaction.user.id != interaction.guild.owner_id and interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ Only the server owner or the bot owner can erase history.", ephemeral=True)
        return

    view = discord.ui.View()

    async def confirm_callback(interaction: discord.Interaction):
        bank["history"] = []
        save_guild_bank(bank)
        await interaction.response.edit_message(content="✅ Bank history erased.", view=None)
    
    async def cancel_callback(interaction: discord.Interaction):
        await interaction.response.edit_message(content="❌ Bank history deletion canceled.", view=None)
    
    confirm_button = discord.ui.Button(style=discord.ButtonStyle.green, emoji="✅")
    confirm_button.callback = confirm_callback

    cancel_button = discord.ui.Button(style=discord.ButtonStyle.red, emoji="❌")
    cancel_button.callback = cancel_callback
    
    view.add_item(confirm_button)
    view.add_item(cancel_button)
    
    await interaction.response.send_message("⚠️ Are you sure you want to erase the bank history?", view=view)
    
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ ERROR: Bot token not found. Set it in the .env file.")
