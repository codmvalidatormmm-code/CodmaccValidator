import os
import threading # Ginagamit natin ito para sa keep_alive
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
import google.generativeai as genai

# ===== WEBKEEP ALIVE =====
app_web = Flask(__name__)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

@app_web.route("/")
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    # Dito natin inayos: threading.Thread na dapat ang gamit
    threading.Thread(target=lambda: app_web.run(host="0.0.0.0", port=port), daemon=True).start()
  
# --- TELEGRAM BOT LOGIC ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# 1. Welcome Message
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🔥 **CODM Account Scanner Bot** 🔥\n\n"
        "Yow paps! Ako ang bot na magbabasa ng CODM stats mo.\n\n"
        "**Paano gamitin?**\n"
        "1. I-screenshot ang iyong **Player Profile** sa CODM.\n"
        "2. I-send ang image dito sa chat.\n"
        "3. Hintayin ang report ko!\n\n"
        "Try mo na, send na ng SS!"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

# 2. Image Handler
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Sinasilip ko na yung account... wait lang paps.")
    
    photo_file = await update.message.photo[-1].get_file()
    photo_path = "temp_ss.jpg"
    await photo_file.download_to_drive(photo_path)

    try:
        sample_file = genai.upload_file(path=photo_path)
        prompt = (
            "From this CODM screenshot, extract and format strictly like this: "
            "👤 **IGN:** [Username]\n"
            "🆙 **Level:** [Level]\n"
            "❤️ **Likes:** [Total Likes]\n"
            "🎮 **MP Rank:** [Current Rank]\n"
            "🏆 **BR Rank:** [Current Rank]\n"
            "⭐ **Note:** [Give a 1-sentence compliment about the account]"
        )
        response = model.generate_content([sample_file, prompt])
        await update.message.reply_text(response.text, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"Error paps! {str(e)}")
    finally:
        if os.path.exists(photo_path):
            os.remove(photo_path)

# 3. Text Handler
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Paps, screenshot ng profile ang i-send mo, hindi text. Hehe!")

def main():
    # Make sure na may value ang TOKEN para hindi mag-crash
    if not TELEGRAM_TOKEN:
        print("Error: Walang TELEGRAM_TOKEN sa Env Vars!")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
