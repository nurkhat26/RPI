import json
import os
import time
import meshtastic.serial_interface
from pubsub import pub
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
import asyncio

# ================= CONFIG =================
BOT_TOKEN = "8189587706:AAFAseLVM15EmQwyBcSBIBIurmsVi2lvEcY"  # Telegram bot token
CHAT_FILE = "chats.json"
SERIAL_PORT = None  # e.g., "/dev/ttyUSB0" or None for auto-detect
# ==========================================

# -------- Load chats --------
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
if SERIAL_PORT:
    interface = meshtastic.serial_interface.SerialInterface(SERIAL_PORT)
else:
    interface = meshtastic.serial_interface.SerialInterface()
time.sleep(1)
print("Connected to Meshtastic")


# -------- Telegram Application --------
telegram_app = None  # will be set in main()


# -------- MESHTASTIC → TELEGRAM --------
def on_receive(packet, interface):
    try:
        if "decoded" not in packet:
            return
        decoded = packet["decoded"]
        if "text" not in decoded:
            return

        text = decoded["text"]
        if text.startswith("[TG] "):
            return
        sender = packet.get("fromId", "Unknown")
        message = f"📡 {sender}:\n{text}"

        for chat_id in known_chats:
            asyncio.run_coroutine_threadsafe(
                telegram_app.bot.send_message(chat_id=chat_id, text=message),
                asyncio.get_event_loop()
            )

    except Exception as e:
        print("Meshtastic receive error:", e)


pub.subscribe(on_receive, "meshtastic.receive")


# -------- TELEGRAM → MESHTASTIC --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

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


# -------- MAIN --------
async def main():
    global telegram_app

    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bridge running...")
    await telegram_app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
