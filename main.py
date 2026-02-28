import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
import google.generativeai as genai

# ===== WEBKEEP ALIVE PARA SA RENDER =====
app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is online and scanning!"

def run_flask():
    # Render uses the PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

def keep_alive():
    # Inayos ang threading call para hindi mag-NameError
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
  
# --- TELEGRAM BOT LOGIC ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Setup Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
# In-update sa 'latest' para iwas 404 error
model = genai.GenerativeModel('gemini-1.5-flash-latest')

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

# 2. Image Handler (Dito binabasa ang screenshot)
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("🔍 Sinasilip ko na yung account... wait lang paps.")
    
    # Download yung image
    photo_file = await update.message.photo[-1].get_file()
    photo_path = "temp_ss.jpg"
    await photo_file.download_to_drive(photo_path)

    try:
        # I-upload sa Gemini
        sample_file = genai.upload_file(path=photo_path)
        
        # Mas malinaw na prompt para sa AI
        prompt = (
            "Analyze this CODM screenshot carefully. Extract these details:\n"
            "1. IGN (Username)\n"
            "2. Player Level\n"
            "3. Total Likes\n"
            "4. Current MP Rank (Look at the Roman Numerals/Icons)\n"
            "5. Current BR Rank (Look at the Icons)\n\n"
            "Format the response exactly like this:\n"
            "👤 **IGN:** [Username]\n"
            "🆙 **Level:** [Level]\n"
            "❤️ **Likes:** [Likes]\n"
            "🎮 **MP Rank:** [Rank]\n"
            "🏆 **BR Rank:** [Rank]\n\n"
            "⭐ **Bot Comment:** [1 short funny comment about the account]"
        )
        
        response = model.generate_content([sample_file, prompt])
        
        # Send ang result
        await update.message.reply_text(response.text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"Error paps: {str(e)}")
    finally:
        # I-delete ang temporary file
        if os.path.exists(photo_path):
            os.remove(photo_path)
        # I-delete yung "Sinasilip ko..." na message
        await status_msg.delete()

# 3. Text Handler
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Paps, screenshot ng profile ang i-send mo, hindi text. Hehe!")

def main():
    if not TELEGRAM_TOKEN:
        print("Error: Walang TELEGRAM_TOKEN!")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
