import os
import asyncio
import random
import string
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from threading import Thread
from flask import Flask

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ===== KEEP ALIVE (RENDER) =====
app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(
        target=lambda: app_web.run(host="0.0.0.0", port=port),
        daemon=True
    ).start()

# ===== CONFIG =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
PH_TZ = ZoneInfo("Asia/Manila")

# ===== DATABASES (IN-MEMORY) =====
access_keys = {}        # access_key -> expire
user_access = {}        # user_id -> expire
user_access_key = {}    # user_id -> access_key
random_keys = {}        # random_key -> expire

# ===== UTILS =====
def generate_key(length=8):
    chars = string.ascii_letters + string.digits
    return "Kaze-" + ''.join(random.choice(chars) for _ in range(length))

def duration_from_code(code):
    code = code.lower()

    if code == "1m":
        return timedelta(minutes=1)
    if code == "1h":
        return timedelta(hours=1)
    if code == "1d":
        return timedelta(days=1)
    if code == "3d":
        return timedelta(days=3)
    if code == "7d":
        return timedelta(days=7)
    if code == "lifetime":
        return None  # special case
    return None
    
# ===== AUTO EXPIRE RANDOM KEY =====
async def expire_random_key(duration, key, chat_id, app):
    await asyncio.sleep(duration.total_seconds())

    if key in random_keys:
        del random_keys[key]
        await app.bot.send_message(
            chat_id=chat_id,
            text=(
                "❌ 𝗞𝗘𝗬 𝗘𝗫𝗣𝗜𝗥𝗘𝗗\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"📝 Key: `{key}`\n"
                "🔑 Your key is no longer valid\n\n"
                "📌 Status:\n"
                "🔴 EXPIRED\n\n"
                "⚠️ Please generate a new key\n"
                "🔥 Click /genkey to generate\n"
                "━━━━━━━━━━━━━━━━━━━"
            ),
            parse_mode="Markdown"
        )

# ===== /START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.now(PH_TZ)

    if user_id in user_access and user_access[user_id] > now:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 Generate Random Key", callback_data="gen_random")]
        ])
        await update.message.reply_text(
            "✅ ACCESS GRANTED\n\nChoose an option:",
            reply_markup=keyboard
        )
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔐 Enter Access Key", callback_data="enter_access")]
        ])
        await update.message.reply_text(
            "🚫 ACCESS REQUIRED\n\nYou need a valid access key.",
            reply_markup=keyboard
        )

# ===== INLINE HANDLER =====
async def inline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    now = datetime.now(PH_TZ)

    if query.data == "enter_access":
        await query.message.reply_text(
            "🔑 Send your access key using:\n\n`/access YOUR_KEY`",
            parse_mode="Markdown"
        )

    elif query.data == "gen_random":
        if user_id not in user_access or user_access[user_id] < now:
            await query.message.reply_text("❌ Access required.")
            return

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⏱ 1m", callback_data="rk_1m"),
                InlineKeyboardButton("⏱ 1h", callback_data="rk_1h"),
                InlineKeyboardButton("⏱ 1d", callback_data="rk_1d"),
            ]
        ])
        await query.message.reply_text(
            "⏳ Select duration:",
            reply_markup=keyboard
        )

    elif query.data.startswith("rk_"):
        if user_id not in user_access or user_access[user_id] < now:
            return

        code = query.data.replace("rk_", "")
        duration = duration_from_code(code)

        key = generate_key()
        expire = datetime.now(PH_TZ) + duration
        random_keys[key] = expire

        await query.message.reply_text(
          "✨ 𝗞𝗘𝗬 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗘𝗗\n"
          "━━━━━━━━━━━━━━━━━━━━\n"
          f"🔑 `{key}`\n\n"
          "📅 Expires (PH):\n"
          f"{expire.strftime('%B %d, %Y • %I:%M %p')}\n\n"
          "🟢 Status: ACTIVE\n"
          "━━━━━━━━━━━━━━━━━━━━\n"
          "🔥 Auto notify when key expires",
          parse_mode="Markdown"
        )

        asyncio.create_task(
            expire_random_key(
                duration,
                key,
                query.message.chat.id,
                context.application
            )
        )

# ===== /ACCESS =====
async def access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.now(PH_TZ)

    if not context.args:
        await update.message.reply_text("Usage: /access YOUR_KEY")
        return

    key = context.args[0]
    expire = access_keys.get(key)

    if not expire and expire is not None:
        await update.message.reply_text("❌ Invalid access key")
        return

    if expire and expire < now:
        await update.message.reply_text("❌ Expired access key")
        return

    # ✅ SAVE USER ACCESS
    user_access[user_id] = expire
    user_access_key[user_id] = key

    expire_text = (
        expire.strftime('%B %d, %Y • %I:%M %p')
        if expire else "♾ LIFETIME"
    )

    await update.message.reply_text(
        "✅ 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗔𝗖𝗖𝗘𝗦𝗦 𝗔𝗖𝗧𝗜𝗩𝗔𝗧𝗘𝗗!\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 𝗞𝗘𝗬 𝗜𝗡𝗙𝗢𝗥𝗠𝗔𝗧𝗜𝗢𝗡\n"
        f"🔑 Key: `{key}`\n"
        f"📅 Expires: {expire_text}\n"
        "📌 Status: 🟢 ACTIVE\n\n"
        "🚀 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗙𝗘𝗔𝗧𝗨𝗥𝗘𝗦 𝗨𝗡𝗟𝗢𝗖𝗞𝗘𝗗\n"
        "• ⚡ Faster & smoother\n"
        "• 🎯 Auto notify if key expired\n"
        "• ♾ Unlimited usage\n\n"
        "📘 𝗔𝗩𝗔𝗜𝗟𝗔𝗕𝗟𝗘 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦\n"
        "• /start – Open the main menu\n"
        "• /genkey – Generate random key\n\n"
        "🧪 Example:\n"
        "`/genkey 1m`\n"
        "`/genkey 1h`\n"
        "`/genkey 1d`",
        parse_mode="Markdown"
    )

# ===== /GENKEY =====
async def genkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.now(PH_TZ)

    if not context.args:
        await update.message.reply_text(
            "Usage:\n"
            "/genkey access 1d | 3d | 7d | lifetime\n"
            "/genkey 1m | 1h | 1d"
        )
        return

    # ===== OWNER: ACCESS KEY =====
    if context.args[0].lower() == "access":
        if user_id != OWNER_ID:
            await update.message.reply_text("❌ Owner only panel")
            return

        if len(context.args) < 2:
            await update.message.reply_text(
                "Example:\n"
                "/genkey access 1d\n"
                "/genkey access 3d\n"
                "/genkey access 7d\n"
                "/genkey access lifetime"
            )
            return

        duration_code = context.args[1].lower()
        duration = duration_from_code(duration_code)

        if duration is None and duration_code != "lifetime":
            await update.message.reply_text("❌ Invalid duration")
            return

        key = generate_key()

        if duration:
            expire = now + duration
        else:
            expire = None  # lifetime

        access_keys[key] = expire

        await update.message.reply_text(
            "🔐 ACCESS KEY GENERATED\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 `{key}`\n"
            f"📅 Expires (PH):\n"
            f"{expire.strftime('%B %d, %Y • %I:%M %p') if expire else '♾ LIFETIME'}",
            parse_mode="Markdown"
        )
        return
        
    # ===== USER: RANDOM KEY =====
    if user_id not in user_access or user_access[user_id] < now:
        await update.message.reply_text("❌ You need access first. Use /start")
        return

    duration = duration_from_code(context.args[0])
    if not duration:
        await update.message.reply_text("❌ Invalid duration")
        return

    key = generate_key()
    expire = now + duration
    random_keys[key] = expire

    await update.message.reply_text(
        "✨ 𝗞𝗘𝗬 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗘𝗗\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💎 𝗞𝗘𝗬 𝗜𝗡𝗙𝗢𝗥𝗠𝗔𝗧𝗜𝗢𝗡\n\n"
        f"🔑 𝗞𝗲𝘆:\n`{key}` (tap to copy)"
        "📅 𝗘𝘅𝗽𝗶𝗿𝗲𝘀 (PH):"
        f"{expire.strftime('%B %d, %Y • %I:%M %p')}"
        "📌 𝗦𝘁𝗮𝘁𝘂𝘀: ACTIVE"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔥 Auto notify when key expires",
        parse_mode="Markdown"
    )

    asyncio.create_task(
        expire_random_key(
            duration,
            key,
            update.effective_chat.id,
            context.application
        )
    )
# ===== /REVOKE =====
async def revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /revoke ACCESS_KEY")
        return

    key = context.args[0]
    removed_users = []

    # remove access key
    if key in access_keys:
        del access_keys[key]

    # remove users who used this key
    for user_id, used_key in list(user_access_key.items()):
        if used_key == key:
            user_access.pop(user_id, None)
            user_access_key.pop(user_id, None)
            removed_users.append(user_id)

    if removed_users:
        await update.message.reply_text(
            f"✅ Access revoked\n"
            f"🔑 Key: `{key}`\n"
            f"👥 Users removed: {len(removed_users)}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "✅Key revoked",
            parse_mode="Markdown"
        )
        
# ===== MAIN =====
def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("access", access))
    app.add_handler(CommandHandler("genkey", genkey))
    app.add_handler(CommandHandler("revoke", revoke))
    app.add_handler(CallbackQueryHandler(inline_handler))

    print("🤖 Bot running (Polling + Flask)")
    app.run_polling()

if __name__ == "__main__":
    keep_alive()  # optional
    main()
