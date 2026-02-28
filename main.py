import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
import google.generativeai as genai

# ===== WEBKEEP ALIVE =====
app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is online with Gemini Pro!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

def keep_alive():
    threading.Thread(target=run_flask, daemon=True).start()
  
# --- TELEGRAM BOT LOGIC ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Setup Gemini AI using Gemini 1.5 Pro
genai.configure(api_key=GEMINI_API_KEY)
# Gagamitin natin ang specific version string para iwas 404
model = genai.GenerativeModel(model_name='gemini-1.5-pro') 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 **CODM Pro Scanner Active!** 🔥\n\n"
        "Send mo na yung screenshot ng Profile mo paps, hihimayin ko yan gamit ang Gemini Pro!",
        parse_mode='Markdown'
    )

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("🧠 Gemini Pro is analyzing... bigyan mo ko ng 5-10 seconds paps.")
    
    photo_file = await update.message.photo[-1].get_file()
    photo_path = "temp_ss.jpg"
    await photo_file.download_to_drive(photo_path)

    try:
        # Upload and process
        sample_file = genai.upload_file(path=photo_path)
        
        prompt = (
            "You are a CODM expert. Look at this Player Profile screenshot and extract:\n"
            "1. IGN (The name beside the avatar)\n"
            "2. Player Level (The number near 'TIER')\n"
            "3. Total Likes (The number beside the heart icon)\n"
            "4. Current MP Rank (Identify the icon/text at the bottom left)\n"
            "5. Current BR Rank (Identify the icon/text at the bottom middle)\n\n"
            "Format the output with emojis. Also, add a 'Rank Assessment' at the end."
        )
        
        response = model.generate_content([sample_file, prompt])
        await update.message.reply_text(f"✅ **SCAN COMPLETE** ✅\n\n{response.text}", parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"Error paps: {str(e)}")
    finally:
        if os.path.exists(photo_path):
            os.remove(photo_path)
        await status_msg.delete()

def main():
    if not TELEGRAM_TOKEN: return
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.run_polling()

if __name__ == "__main__":
    keep_alive()
    main()
