import json
import os
import threading
import meshtastic.serial_interface
from pubsub import pub
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)
import asyncio

# ================= CONFIG =================
BOT_TOKEN = "8189587706:AAFAseLVM15EmQwyBcSBIBIurmsVi2lvEcY"  # Replace with your Telegram bot token
CHAT_FILE = "chats.json"
# ==========================================

# -------- Chat Storage --------
if os.path.exists(CHAT_FILE):
    with open(CHAT_FILE, "r") as f:
        known_chats = set(json.load(f))
else:
    known_chats = set()


def save_chats():
    with open(CHAT_FILE, "w") as f:
        json.dump(list(known_chats), f)


# -------- Connect to Meshtastic --------
print("Connecting to Meshtastic...")
interface = meshtastic.serial_interface.SerialInterface()
print("Connected to Meshtastic")

# -------- Global Asyncio Loop --------
async_loop = asyncio.new_event_loop()
asyncio.set_event_loop(async_loop)


# -------- MESHTASTIC → TELEGRAM --------
def on_receive(packet, interface):
    try:
        if "decoded" not in packet:
            return
        decoded = packet["decoded"]
        if "text" not in decoded:
            return

        text = decoded["text"]
        sender = packet.get("fromId", "Unknown")

        # Prevent loops
        if text.startswith("[TG] "):
            return

        message = f"📡 {sender}:\n{text}"

        # Schedule sending to all chats in main asyncio loop
        for chat_id in known_chats:
            asyncio.run_coroutine_threadsafe(
                telegram_app.bot.send_message(chat_id=chat_id, text=message),
                async_loop,
            )

    except Exception as e:
        print("Meshtastic receive error:", e)


pub.subscribe(on_receive, "meshtastic.receive")


# -------- TELEGRAM → MESHTASTIC --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    # Save new chat automatically
    if chat_id not in known_chats:
        known_chats.add(chat_id)
        save_chats()

    try:
        interface.sendText("[TG] " + text, wantAck=False)
        await update.message.reply_text("Sent to mesh ✅")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in known_chats:
        known_chats.add(chat_id)
        save_chats()
    await update.message.reply_text("Meshtastic bridge connected ✅")


# -------- RUN TELEGRAM APP --------
def run_telegram():
    global telegram_app
    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Telegram bridge running...")
    telegram_app.run_polling()


# -------- MAIN --------
if __name__ == "__main__":
    # Start Telegram in main thread
    threading.Thread(target=run_telegram, daemon=True).start()

    # Run asyncio loop forever to schedule Meshtastic tasks
    try:
        async_loop.run_forever()
    except KeyboardInterrupt:
        print("Shutting down...")
