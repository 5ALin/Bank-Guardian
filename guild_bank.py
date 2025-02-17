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
GUILD_ID =   # Replace with your Discord server's ID

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
admin_role = ""  # Change to your actual admin role

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    try:
        await bot.tree.sync(guild=guild)  # Sync only to this server
        print(f'Synced slash commands to guild {GUILD_ID}')
    except discord.errors.Forbidden:
        print("❌ ERROR: Missing permissions to sync commands. Check bot permissions.")
    except Exception as e:
        print(f"❌ ERROR: {e}")

@tree.command(name="deposit", description="Deposit mesos into the guild bank")
async def deposit(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be a positive whole number.", ephemeral=True)
        return
    
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
    if quantity <= 0:
        await interaction.response.send_message("❌ Quantity must be a positive whole number.", ephemeral=True)
        return

    user = str(interaction.user.id)
    timestamp = get_timestamp()

    item_lower = item.lower()  # Convert item name to lowercase

    if item_lower in bank["items"]:
        bank["items"][item_lower]["quantity"] += quantity
    else:
        bank["items"][item_lower] = {"original_name": item, "quantity": quantity}

    bank["history"].append(f"[{timestamp}] {interaction.user.name} deposited {quantity} {item}(s).")
    save_guild_bank(bank)

    await interaction.response.send_message(f"✅ {interaction.user.name} deposited {quantity} {item}(s) into the Guild Bank!")

@tree.command(name="bank_history", description="View the bank transaction history (Admins only)")
async def bank_history(interaction: discord.Interaction):
    history = "\n".join(bank["history"][-10:]) if bank["history"] else "No transactions recorded."
    await interaction.response.send_message(f"📜 **Guild Bank History:**\n```{history}```")

@tree.command(name="request_withdraw", description="Request to withdraw mesos from the guild bank")
async def request_withdraw(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be a positive whole number.", ephemeral=True)
        return

    timestamp = get_timestamp()

    if bank["mesos"] < amount:
        await interaction.response.send_message("❌ Not enough mesos in the bank.")
        return
    
    bank["history"].append(f"[{timestamp}] {interaction.user.name} requested to withdraw {amount} mesos.")
    save_guild_bank(bank)

    await interaction.response.send_message(f"⚠️ {interaction.user.name} requested to withdraw {amount} mesos. An admin needs to approve.")


@tree.command(name="approve_withdraw", description="Approve a mesos withdrawal request (Admins only)")
async def approve_withdraw(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be a positive whole number.", ephemeral=True)
        return

    timestamp = get_timestamp()
    user = interaction.user

    admin_role = discord.utils.get(interaction.guild.roles, name="")
    if admin_role not in user.roles and user.id != interaction.guild.owner_id and user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ Only admins, the server owner, or the bot owner can approve withdrawals.", ephemeral=True)
        return

    request_found = None
    for entry in reversed(bank["history"]):
        if f"requested to withdraw {amount} mesos" in entry:
            request_found = entry
            break

    if not request_found:
        await interaction.response.send_message("❌ No matching withdrawal request found in history.", ephemeral=True)
        return

    if bank["mesos"] < amount:
        await interaction.response.send_message(f"❌ Not enough mesos in the bank. Available: {bank['mesos']}.", ephemeral=True)
        return

    bank["mesos"] -= amount
    bank["history"].append(f"[{timestamp}] {user.name} withdrew {amount} mesos, approved by {interaction.user.name}.")
    save_guild_bank(bank)

    await interaction.response.send_message(f"✅ {user.name} withdrew {amount} mesos, approved by {interaction.user.name}.")


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

@tree.command(name="delete_item", description="Delete a specific item from the bank (Guild Owner/Bot Owner only)")
async def delete_item(interaction: discord.Interaction, item_name: str, quantity: int):
    if interaction.user.id != interaction.guild.owner_id and interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ Only the server owner or the bot owner can delete inventory.", ephemeral=True)
        return

    if quantity <= 0:
        await interaction.response.send_message("❌ Quantity must be a positive whole number.", ephemeral=True)
        return

    item_lower = item_name.lower()  # Convert to lowercase for lookup

    if item_lower not in bank["items"]:
        await interaction.response.send_message("❌ Item not found in the bank.", ephemeral=True)
        return

    if quantity > bank["items"][item_lower]["quantity"]:
        await interaction.response.send_message(f"❌ Cannot delete {quantity} {bank['items'][item_lower]['original_name']}(s), only {bank['items'][item_lower]['quantity']} available in the bank.", ephemeral=True)
        return

    if quantity == bank["items"][item_lower]["quantity"]:
        del bank["items"][item_lower]
        message = f"✅ Deleted all {bank['items'][item_lower]['original_name']} from the bank."
    else:
        bank["items"][item_lower]["quantity"] -= quantity
        message = f"✅ Deleted {quantity} of {bank['items'][item_lower]['original_name']} from the bank."

    save_guild_bank(bank)
    await interaction.response.send_message(message)


@tree.command(name="delete_mesos", description="Delete an amount of mesos from the bank (Guild Owner/Bot Owner only)")
async def delete_mesos(interaction: discord.Interaction, amount: int):
    if interaction.user.id != interaction.guild.owner_id and interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ Only the server owner or the bot owner can delete mesos.", ephemeral=True)
        return
    
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be greater than zero.", ephemeral=True)
        return
    
    if amount > bank["mesos"]:
        await interaction.response.send_message(f"❌ Cannot delete {amount} mesos, only {bank['mesos']} available in the bank.", ephemeral=True)
        return
    
    bank["mesos"] -= amount
    message = f"✅ Deleted {amount} mesos from the bank."
    
    save_guild_bank(bank)
    await interaction.response.send_message(message)

@tree.command(name="check_bank", description="Check the current bank balance and stored items.")
async def check_bank(interaction: discord.Interaction):
    mesos = bank["mesos"]

    # Convert old item structure (int) to new structure (dict)
    for item, value in bank["items"].items():
        if isinstance(value, int):  # Old format (only quantity stored)
            bank["items"][item] = {"original_name": item, "quantity": value}

    # Generate item list with correct format
    items_list = [f"{data['original_name']}: {data['quantity']}" for data in bank["items"].values()]
    items = "\n".join(items_list) if items_list else "No items stored."

    save_guild_bank(bank)  # Save the converted format

    await interaction.response.send_message(f"🏦 **Guild Bank:**\n💰 Mesos: {mesos}\n📦 Items:\n{items}")


    
@bot.command()
async def clear_commands(ctx):
    try:
        bot.tree.clear_commands(guild=discord.Object(id=GUILD_ID))
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        await ctx.send("✅ All slash commands have been cleared and re-synced.")
    except discord.errors.Forbidden:
        await ctx.send("❌ Bot lacks permissions to clear commands.")
    except Exception as e:
        await ctx.send(f"❌ ERROR: {e}")

@tree.command(name="request_withdraw_item", description="Request to withdraw an item from the guild bank")
async def request_withdraw_item(interaction: discord.Interaction, item_name: str, quantity: int):
    if quantity <= 0:
        await interaction.response.send_message("❌ Quantity must be a positive whole number.", ephemeral=True)
        return

    timestamp = get_timestamp()

    item_lower = item_name.lower()  # Convert to lowercase for lookup

    if item_lower not in bank["items"]:
        await interaction.response.send_message("❌ Item not found in the bank.", ephemeral=True)
        return

    if quantity > bank["items"][item_lower]["quantity"]:
        await interaction.response.send_message(f"❌ Cannot request {quantity} {bank['items'][item_lower]['original_name']}(s), only {bank['items'][item_lower]['quantity']} available.", ephemeral=True)
        return

    bank["history"].append(f"[{timestamp}] {interaction.user.name} requested to withdraw {quantity} {bank['items'][item_lower]['original_name']}(s).")
    save_guild_bank(bank)

    await interaction.response.send_message(f"⚠️ {interaction.user.name} requested to withdraw {quantity} {bank['items'][item_lower]['original_name']}(s). An admin needs to approve.")

@tree.command(name="approve_withdraw_item", description="Approve an item withdrawal request (Admins only)")
async def approve_withdraw_item(interaction: discord.Interaction, item_name: str, quantity: int):
    if quantity <= 0:
        await interaction.response.send_message("❌ Quantity must be a positive whole number.", ephemeral=True)
        return

    timestamp = get_timestamp()
    user = interaction.user

    admin_role = discord.utils.get(interaction.guild.roles, name="")
    if admin_role not in user.roles and user.id != interaction.guild.owner_id and user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ Only admins, the server owner, or the bot owner can approve withdrawals.", ephemeral=True)
        return

    item_lower = item_name.lower()  # Convert to lowercase for lookup

    request_found = None
    for entry in reversed(bank["history"]):
        if f"requested to withdraw {quantity} {bank['items'].get(item_lower, {}).get('original_name', item_name)}" in entry:
            request_found = entry
            break

    if not request_found:
        await interaction.response.send_message("❌ No matching withdrawal request found in history.", ephemeral=True)
        return

    if item_lower not in bank["items"]:
        await interaction.response.send_message("❌ Item not found in the bank.", ephemeral=True)
        return

    if quantity > bank["items"][item_lower]["quantity"]:
        await interaction.response.send_message(f"❌ Cannot approve {quantity} {bank['items'][item_lower]['original_name']}(s), only {bank['items'][item_lower]['quantity']} available.", ephemeral=True)
        return

    if quantity == bank["items"][item_lower]["quantity"]:
        del bank["items"][item_lower]
        message = f"✅ {user.name} withdrew all {bank['items'][item_lower]['original_name']}(s), approved by {interaction.user.name}."
    else:
        bank["items"][item_lower]["quantity"] -= quantity
        message = f"✅ {user.name} withdrew {quantity} {bank['items'][item_lower]['original_name']}(s), approved by {interaction.user.name}."

    bank["history"].append(f"[{timestamp}] {user.name} withdrew {quantity} {bank['items'][item_lower]['original_name']}(s), approved by {interaction.user.name}.")
    save_guild_bank(bank)

    await interaction.response.send_message(message)


############################################################################################################################################

@bot.command()
async def sync_global(ctx):
    await bot.tree.sync()
    await ctx.send("✅ Global slash commands have been re-synced.")

@bot.command()
async def sync_server(ctx):
    guild = discord.Object(id=GUILD_ID)  # Replace with your actual server ID
    await bot.tree.sync(guild=guild)
    await ctx.send(f"✅ Slash commands have been re-synced for this server.")

@bot.command()
async def clear_and_sync(ctx):
    try:
        bot.tree.clear_commands(guild=discord.Object(id=GUILD_ID))  # Clears commands
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))  # Re-syncs fresh ones
        await ctx.send("✅ All slash commands have been cleared and re-synced.")
    except Exception as e:
        await ctx.send(f"❌ ERROR: {e}")

@bot.command()
async def force_reset(ctx):
    """Completely clear all slash commands and re-sync"""
    try:
        await bot.tree.sync()
        bot.tree.clear_commands()
        await bot.tree.sync()
        await ctx.send("✅ All slash commands have been forcefully cleared and re-synced.")
    except Exception as e:
        await ctx.send(f"❌ ERROR: {e}")

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ ERROR: Bot token not found. Set it in the .env file.")
