# 🔧 Python 3.14 Event Loop Fix
import asyncio
import sys

if sys.version_info >= (3, 14):
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

import os
import time
import random
import string
import threading
import sqlite3
import traceback
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

# ═══════════════════════════════════════════════════════════
#  🌐 FLASK SERVER
# ═══════════════════════════════════════════════════════════
server = Flask(__name__)


def check_api_key():
    valid = os.getenv("BOT_API_KEY", "fxa_McjuDGEKAPICuQjQp2zvDHytY5Rg91urNGvo8l3PLkV4ETX1")
    if not valid:
        return True
    return request.headers.get("X-API-Key", "") == valid


@server.route("/")
@server.route("/health")
def health():
    return "🎮 Panel Bot Running!", 200


@server.route("/api/status", methods=["GET"])
def api_status():
    if not check_api_key():
        return jsonify({"error": "Unauthorized"}), 401
    users = db_run("SELECT COUNT(*) FROM users", fetch=True)[0][0]
    panels = db_run("SELECT COUNT(*) FROM panels WHERE is_active=1", fetch=True)[0][0]
    keys = db_run("SELECT COUNT(*) FROM api_keys WHERE is_active=1", fetch=True)[0][0]
    return jsonify({
        "status": "online",
        "bot_name": BOT_NAME,
        "stats": {"users": users, "panels": panels, "active_keys": keys},
        "timestamp": datetime.now().isoformat()
    }), 200


@server.route("/api/panels", methods=["GET"])
def api_panels():
    if not check_api_key():
        return jsonify({"error": "Unauthorized"}), 401
    rows = db_run("SELECT id, name, description, category FROM panels WHERE is_active=1", fetch=True)
    result = []
    for r in rows:
        durs = db_run("SELECT id, duration_value, duration_unit, price FROM panel_durations WHERE panel_id=? AND is_active=1",
                      (r[0],), fetch=True)
        result.append({
            "id": r[0], "name": r[1], "description": r[2], "category": r[3],
            "durations": [{"id": d[0], "value": d[1], "unit": d[2], "price": d[3]} for d in durs]
        })
    return jsonify({"panels": result, "count": len(result)}), 200


@server.route("/api/verify-key", methods=["POST"])
def api_verify_key():
    if not check_api_key():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json or {}
    api_key = data.get("api_key", "").strip()
    if not api_key:
        return jsonify({"error": "Missing api_key"}), 400
    row = db_run("""SELECT k.id, k.user_id, k.expires_at, k.is_active, p.name, k.duration_value, k.duration_unit
                    FROM api_keys k JOIN panels p ON k.panel_id=p.id WHERE k.api_key=?""",
                 (api_key,), fetch=True)
    if not row:
        return jsonify({"valid": False, "reason": "Not found"}), 200
    row = row[0]
    try:
        expires = datetime.fromisoformat(row[2])
        expired = expires < datetime.now()
    except:
        expired = True
    return jsonify({
        "valid": row[3] == 1 and not expired,
        "user_id": row[1], "panel": row[4],
        "duration": f"{row[5]} {row[6]}",
        "expires_at": row[2], "is_expired": expired
    }), 200


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port, threaded=True)


from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram.enums import ParseMode

# ═══════════════════════════════════════════════════════════
#  ⚙️ CONFIG
# ═══════════════════════════════════════════════════════════
API_ID = int(os.getenv("API_ID", "36568110"))
API_HASH = os.getenv("API_HASH", "6d59b8f4b840756220d7b192e72d301c")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8892624627:AAEo_Zq55tSntvcQG3gPnwkCNQy167ZllOc")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8964686205"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@Fixa_mods")
BOT_NAME = os.getenv("BOT_NAME", "🎮 𝙁𝙄𝙓𝘼𝙈𝙊𝘿𝙎 𝙋𝘼𝙉𝙀𝙇 𝙎𝙏𝙊𝙍𝙀")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/vipnikhilgaming0")
SUPPORT_LINK = os.getenv("SUPPORT_LINK", "https://t.me/Ffxppanel")
CURRENCY = "₹"

# 💳 Cashfree
CASHFREE_APP_ID = os.getenv("CASHFREE_APP_ID", "")
CASHFREE_SECRET_KEY = os.getenv("CASHFREE_SECRET_KEY", "")
CASHFREE_ENV = os.getenv("CASHFREE_ENV", "")
CASHFREE_BASE_URL = "https://sandbox.cashfree.com/pg" if CASHFREE_ENV == "sandbox" else "https://api.cashfree.com/pg"
CASHFREE_API_VERSION = "2023-08-01"

# 🎮 YOUR Node.js Panel API
PANEL_API_URL = os.getenv("PANEL_API_URL", "https://fixamods-bot.onrender.com/")
PANEL_API_KEY = os.getenv("PANEL_API_KEY", "fxa_McjuDGEKAPICuQjQp2zvDHytY5Rg91urNGvo8l3PLkV4ETX1")
PANEL_API_TIMEOUT = 25

BOT_API_KEY = os.getenv("BOT_API_KEY", "")
REFERRAL_BONUS = 20
DAILY_BONUS = 5

# ═══════════════════════════════════════════════════════════
#  💾 DATABASE
# ═══════════════════════════════════════════════════════════
DB = "bot.db"


def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        wallet INTEGER DEFAULT 0, referred_by INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0, is_premium INTEGER DEFAULT 0,
        total_spent INTEGER DEFAULT 0, last_bonus TIMESTAMP,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS panels (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT,
        category TEXT, is_active INTEGER DEFAULT 1, sales INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS panel_durations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, panel_id INTEGER,
        duration_value INTEGER, duration_unit TEXT, price INTEGER,
        is_active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, panel_id INTEGER,
        duration_id INTEGER, duration_value INTEGER, duration_unit TEXT,
        amount INTEGER, payment_method TEXT, status TEXT DEFAULT 'pending',
        cf_order_id TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, panel_id INTEGER,
        api_key TEXT UNIQUE, expires_at TIMESTAMP, is_active INTEGER DEFAULT 1,
        duration_value INTEGER, duration_unit TEXT, source TEXT DEFAULT 'local',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS wallet_txns (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER,
        txn_type TEXT, note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', 'off')")
    conn.commit()
    conn.close()


def db_run(query, args=(), fetch=False):
    try:
        conn = sqlite3.connect(DB, timeout=10)
        c = conn.cursor()
        c.execute(query, args)
        if fetch:
            r = c.fetchall()
            conn.close()
            return r
        conn.commit()
        last_id = c.lastrowid
        conn.close()
        return last_id
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return [] if fetch else None


def get_setting(key):
    r = db_run("SELECT value FROM settings WHERE key=?", (key,), fetch=True)
    return r[0][0] if r else None


def set_setting(key, value):
    db_run("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))


init_db()

app = Client("PanelSellingBot", api_id=API_ID, api_hash=API_HASH,
             bot_token=BOT_TOKEN, workers=4, sleep_threshold=30)

admin_states = {}
user_states = {}

COMMANDS = ["start", "admin", "addpanel", "listpanels", "deletepanel",
            "pendingorders", "broadcast", "cancel", "skip", "ping",
            "ban", "unban", "maintenance", "addwallet", "deductwallet",
            "userinfo", "mykeys", "wallet", "addmoney", "daily",
            "addduration", "listdurations", "apiinfo", "testapi"]


# ═══════════════════════════════════════════════════════════
#  🔧 HELPERS
# ═══════════════════════════════════════════════════════════
def safe_handler(func):
    async def wrapper(client, update, *a, **kw):
        try:
            return await func(client, update, *a, **kw)
        except Exception as e:
            print(f"⚠️ {func.__name__}: {e}")
            traceback.print_exc()
    return wrapper


async def auto_delete(msg, delay=5):
    try:
        await asyncio.sleep(delay)
        await msg.delete()
    except:
        pass


def gen_local_key():
    while True:
        key = "FIXA-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=20))
        if not db_run("SELECT 1 FROM api_keys WHERE api_key=?", (key,), fetch=True):
            return key


def duration_label(value, unit):
    u = (unit or "days").lower()
    if u == "minutes":
        return f"{value} Min" if value == 1 else f"{value} Mins"
    elif u == "hours":
        return f"{value} Hour" if value == 1 else f"{value} Hours"
    else:
        if value == 1: return "1 Day"
        elif value == 7: return "1 Week"
        elif value == 30: return "1 Month"
        elif value == 90: return "3 Months"
        elif value == 180: return "6 Months"
        elif value == 365: return "1 Year"
        return f"{value} Days"


def get_badge(total_spent):
    if total_spent >= 10000: return "💎 PLATINUM"
    elif total_spent >= 5000: return "🥇 GOLD"
    elif total_spent >= 1000: return "🥈 SILVER"
    elif total_spent > 0: return "🥉 BRONZE"
    return "⭐ NEWBIE"


async def safe_edit(q, text, kb):
    try:
        await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except:
        try:
            await q.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        except:
            pass


def is_admin(uid):
    return uid == ADMIN_ID


# ═══════════════════════════════════════════════════════════
#  💳 CASHFREE
# ═══════════════════════════════════════════════════════════
def cf_create_order(order_id, amount, customer_id, customer_phone, customer_email, return_url):
    url = f"{CASHFREE_BASE_URL}/orders"
    headers = {
        "x-api-version": CASHFREE_API_VERSION,
        "x-client-id": CASHFREE_APP_ID,
        "x-client-secret": CASHFREE_SECRET_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "order_id": order_id, "order_amount": amount, "order_currency": "INR",
        "customer_details": {"customer_id": customer_id, "customer_phone": customer_phone,
                             "customer_email": customer_email},
        "order_meta": {"return_url": return_url}
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()
        print(f"❌ CF create: {r.text}")
        return None
    except Exception as e:
        print(f"❌ CF failed: {e}")
        return None


def cf_status(cf_order_id):
    url = f"{CASHFREE_BASE_URL}/orders/{cf_order_id}"
    headers = {
        "x-api-version": CASHFREE_API_VERSION,
        "x-client-id": CASHFREE_APP_ID,
        "x-client-secret": CASHFREE_SECRET_KEY
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception as e:
        print(f"❌ CF status: {e}")
        return None


# ═══════════════════════════════════════════════════════════
#  🎮 PANEL PROVIDER API — YOUR Node.js API
#  GET /generate?username=X&days=30&adminKey=Y
#  GET /generate?username=X&hours=24&adminKey=Y
#  GET /generate?username=X&minutes=30&adminKey=Y
# ═══════════════════════════════════════════════════════════
def generate_panel_key_from_provider(user_id, username, panel_name, value, unit):
    """
    Call Node.js API and return {key, validity, expires_at} or None.
    """
    if not PANEL_API_URL or not PANEL_API_KEY:
        print("⚠️ PANEL_API_URL or PANEL_API_KEY not configured")
        return None

    safe_username = "".join(c for c in str(username) if c.isalnum() or c in "_-")[:20]
    if not safe_username:
        safe_username = f"user{user_id}"

    base = PANEL_API_URL.rstrip("/")
    url = f"{base}/generate" if not base.endswith("/generate") else base

    params = {
        "username": safe_username,
        "adminKey": PANEL_API_KEY,
        "maxDevices": 1
    }
    unit_lower = (unit or "days").lower()
    if unit_lower == "minutes":
        params["minutes"] = value
    elif unit_lower == "hours":
        params["hours"] = value
    else:
        params["days"] = value

    headers = {
        "X-API-KEY": PANEL_API_KEY,
        "Accept": "application/json"
    }

    try:
        print(f"📡 Calling Panel API: {url}")
        print(f"   Params: {params}")
        resp = requests.get(url, params=params, headers=headers, timeout=PANEL_API_TIMEOUT)
        print(f"📥 Response [{resp.status_code}]: {resp.text[:400]}")

        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") and data.get("key"):
                return {
                    "key": data["key"],
                    "validity": data.get("validity", ""),
                    "expires_at": data.get("expiresAt", ""),
                    "duration": data.get("duration", value),
                    "unit": data.get("unit", unit_lower)
                }
            else:
                print(f"⚠️ API returned no key: {data}")
                return None
        else:
            print(f"❌ API failed: {resp.status_code} {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Panel API exception: {e}")
        return None


def parse_validity_to_datetime(validity_str):
    try:
        return datetime.strptime(validity_str.strip(), "%d-%m-%Y %H:%M:%S")
    except:
        return None


# ═══════════════════════════════════════════════════════════
#  📦 DELIVER PANEL
# ═══════════════════════════════════════════════════════════
async def deliver_panel(client, uid, panel_id, order_id, value, unit):
    p = db_run("SELECT name FROM panels WHERE id=?", (panel_id,), fetch=True)
    if not p:
        return False
    p_name = p[0][0]

    ud = db_run("SELECT username, first_name FROM users WHERE user_id=?", (uid,), fetch=True)
    user_raw = (ud[0][0] or ud[0][1]) if ud else f"user{uid}"
    username = "".join(c for c in str(user_raw or f"user{uid}") if c.isalnum() or c in "_-")[:20] or f"user{uid}"

    print(f"🔑 Generating key | User: {username} | Panel: {p_name} | Duration: {value} {unit}")
    result = generate_panel_key_from_provider(uid, username, p_name, value, unit)

    if result and result.get("key"):
        api_key = result["key"]
        source = "provider"
        validity_str = result.get("validity", "")
        exp_dt = parse_validity_to_datetime(validity_str)
        if not exp_dt:
            mult = {"minutes": 60, "hours": 3600, "days": 86400}
            exp_dt = datetime.now() + timedelta(seconds=value * mult.get(unit.lower(), 86400))
        print(f"✅ Real key: {api_key}")
    else:
        api_key = gen_local_key()
        source = "local"
        mult = {"minutes": 60, "hours": 3600, "days": 86400}
        exp_dt = datetime.now() + timedelta(seconds=value * mult.get(unit.lower(), 86400))
        validity_str = exp_dt.strftime("%d-%m-%Y %H:%M:%S")
        print(f"⚠️ Fallback local key: {api_key}")

    db_run("""INSERT INTO api_keys
              (user_id, panel_id, api_key, expires_at, duration_value, duration_unit, source)
              VALUES (?,?,?,?,?,?,?)""",
           (uid, panel_id, api_key, exp_dt.isoformat(), value, unit, source))
    db_run("UPDATE panels SET sales = sales + 1 WHERE id=?", (panel_id,))
    db_run("UPDATE orders SET status='approved' WHERE id=?", (order_id,))

    source_text = "🔗 Provider API" if source == "provider" else "⚠️ Local Key"

    try:
        await client.send_message(uid,
            f"🎉✨ **𝙋𝘼𝙉𝙀𝙇 𝘿𝙀𝙇𝙄𝙑𝙀𝙍𝙀𝘿!** ✨🎉\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎮 **Panel:** {p_name}\n"
            f"⏱️ **Duration:** {duration_label(value, unit)}\n"
            f"🔑 **API Key:**\n`{api_key}`\n\n"
            f"⏰ **Expires:** `{validity_str}`\n"
            f"📌 **Source:** {source_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 **Kaise Use Karein:**\n"
            f"   1️⃣ Panel app download karo\n"
            f"   2️⃣ API key paste karo\n"
            f"   3️⃣ Enjoy! 🎮\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💬 Support: {SUPPORT_LINK}\n"
            f"⚠️ **Key kisi ko na do!**",
            parse_mode=ParseMode.MARKDOWN)
        return True
    except Exception as e:
        print(f"Deliver err: {e}")
        return False


# ═══════════════════════════════════════════════════════════
#  🚀 START
# ═══════════════════════════════════════════════════════════
@app.on_message(filters.command("start") & filters.private)
@safe_handler
async def start_cmd(client, message: Message):
    try:
        await message.delete()
    except:
        pass

    u = message.from_user
    user = db_run("SELECT is_banned FROM users WHERE user_id=?", (u.id,), fetch=True)
    if user and user[0][0] == 1:
        m = await message.reply_text("🚫 **Aap ban ho chuke ho!**\n\n💬 Support: " + SUPPORT_LINK)
        asyncio.create_task(auto_delete(m, 10))
        return

    if get_setting("maintenance") == "on" and u.id != ADMIN_ID:
        m = await message.reply_text("🚨 **MAINTENANCE MODE** 🚨\n\n🛠️ Bot update ho raha hai...")
        asyncio.create_task(auto_delete(m, 15))
        return

    ref_id = 0
    if len(message.command) > 1:
        try:
            ref_id = int(message.command[1])
        except:
            pass

    existing = db_run("SELECT 1 FROM users WHERE user_id=?", (u.id,), fetch=True)
    if not existing:
        db_run("INSERT INTO users (user_id, username, first_name, referred_by) VALUES (?,?,?,?)",
               (u.id, u.username, u.first_name, ref_id))
        if ref_id and ref_id != u.id:
            if db_run("SELECT 1 FROM users WHERE user_id=?", (ref_id,), fetch=True):
                db_run("UPDATE users SET wallet = wallet + ? WHERE user_id=?", (REFERRAL_BONUS, ref_id))
                db_run("INSERT INTO wallet_txns (user_id, amount, txn_type, note) VALUES (?,?,?,?)",
                       (ref_id, REFERRAL_BONUS, "referral", f"Referral from {u.first_name}"))
                try:
                    await client.send_message(ref_id,
                        f"🎉💎 **NEW REFERRAL!**\n\n👤 {u.first_name}\n💰 **+{CURRENCY}{REFERRAL_BONUS}**",
                        parse_mode=ParseMode.MARKDOWN)
                except:
                    pass
    else:
        db_run("UPDATE users SET username=?, first_name=? WHERE user_id=?",
               (u.username, u.first_name, u.id))

    ud = db_run("SELECT wallet, total_spent, is_premium, last_bonus FROM users WHERE user_id=?", (u.id,), fetch=True)
    wallet = ud[0][0] if ud else 0
    total_spent = ud[0][1] if ud else 0
    is_premium = ud[0][2] if ud else 0
    last_bonus = ud[0][3] if ud else None

    ref_count = db_run("SELECT COUNT(*) FROM users WHERE referred_by=?", (u.id,), fetch=True)[0][0]
    purchases = db_run("SELECT COUNT(*) FROM api_keys WHERE user_id=?", (u.id,), fetch=True)[0][0]
    active_keys = db_run("SELECT COUNT(*) FROM api_keys WHERE user_id=? AND is_active=1", (u.id,), fetch=True)[0][0]

    badge = get_badge(total_spent)
    premium_tag = "💎 PREMIUM" if is_premium else "🆓 FREE"

    bonus_msg = ""
    if not last_bonus:
        bonus_msg = "\n🎁 **Daily bonus available!** /daily"
    else:
        try:
            if datetime.now() - datetime.fromisoformat(last_bonus) >= timedelta(hours=24):
                bonus_msg = "\n🎁 **Daily bonus available!** /daily"
        except:
            pass

    text = (
        f"╔═══════════════════════════╗\n"
        f"   🎮 **𝙁𝙄𝙓𝘼𝙈𝙊𝘿𝙎 𝙋𝘼𝙉𝙀𝙇 𝙎𝙏𝙊𝙍𝙀** 🎮\n"
        f"╚═══════════════════════════╝\n\n"
        f"✨ ʜᴇʟʟᴏ **{u.first_name}**! ✨\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏅 **Badge:** {badge}\n"
        f"💎 **Type:** {premium_tag}\n"
        f"💰 **Wallet:** `{CURRENCY}{wallet}`\n"
        f"🔑 **Active Keys:** `{active_keys}`\n"
        f"🛒 **Total Buys:** `{purchases}`\n"
        f"👥 **Referrals:** `{ref_count}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 **Features:**\n"
        f"   🎮 Premium Panels\n"
        f"   ⏱️ Minutes / Hours / Days\n"
        f"   🔑 Instant API Key Delivery\n"
        f"   💰 Wallet System\n"
        f"   💳 Cashfree Payments{bonus_msg}\n\n"
        f"👇 **Choose:**"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ 𝘽𝙧𝙤𝙬𝙨𝙚 𝙋𝙖𝙣𝙚𝙡𝙨", callback_data="browse"),
         InlineKeyboardButton("🔑 𝙈𝙮 𝙆𝙚𝙮𝙨", callback_data="mykeys")],
        [InlineKeyboardButton("💰 𝙒𝙖𝙡𝙡𝙚𝙩", callback_data="wallet"),
         InlineKeyboardButton("💳 𝘼𝙙𝙙 𝙈𝙤𝙣𝙚𝙮", callback_data="addmoney")],
        [InlineKeyboardButton("📦 𝙈𝙮 𝙊𝙧𝙙𝙚𝙧𝙨", callback_data="myorders"),
         InlineKeyboardButton("👤 𝙋𝙧𝙤𝙛𝙞𝙡𝙚", callback_data="profile")],
        [InlineKeyboardButton("🎁 𝙍𝙚𝙛𝙚𝙧 & 𝙀𝙖𝙧𝙣", callback_data="refer"),
         InlineKeyboardButton("🎰 𝙎𝙥𝙞𝙣", callback_data="spin")],
        [InlineKeyboardButton("🎁 𝘿𝙖𝙞𝙡𝙮 𝘽𝙤𝙣𝙪𝙨", callback_data="daily"),
         InlineKeyboardButton("💬 𝙎𝙪𝙥𝙥𝙤𝙧𝙩", url=SUPPORT_LINK)],
    ])
    await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════
#  💰 WALLET / KEYS HELPERS
# ═══════════════════════════════════════════════════════════
async def show_wallet(client, uid):
    ud = db_run("SELECT wallet, total_spent FROM users WHERE user_id=?", (uid,), fetch=True)
    wallet = ud[0][0] if ud else 0
    total_spent = ud[0][1] if ud else 0
    txns = db_run("SELECT amount, txn_type FROM wallet_txns WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,), fetch=True)

    text = (
        f"╔═══════════════════════════╗\n"
        f"   💰 **𝙔𝙊𝙐𝙍 𝙒𝘼𝙇𝙇𝙀𝙏** 💰\n"
        f"╚═══════════════════════════╝\n\n"
        f"💰 **Balance:** `{CURRENCY}{wallet}`\n"
        f"💸 **Spent:** `{CURRENCY}{total_spent}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n📜 **Recent:**\n"
    )
    if txns:
        for t in txns:
            emoji = "➕" if t[0] > 0 else "➖"
            text += f"{emoji} `{CURRENCY}{abs(t[0])}` — {t[1]}\n"
    else:
        text += "❌ No transactions\n"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 𝘼𝙙𝙙 𝙈𝙤𝙣𝙚𝙮", callback_data="addmoney")],
        [InlineKeyboardButton("🏠 𝙈𝙖𝙞𝙣 𝙈𝙚𝙣𝙪", callback_data="home")]
    ])
    await client.send_message(uid, text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


async def add_money_prompt(client, uid):
    amounts = [50, 100, 200, 500, 1000, 2000]
    btns = []
    for i in range(0, len(amounts), 3):
        btns.append([InlineKeyboardButton(f"💰 {CURRENCY}{a}", callback_data=f"addamt_{a}") for a in amounts[i:i+3]])
    btns.append([InlineKeyboardButton("✏️ 𝘾𝙪𝙨𝙩𝙤𝙢", callback_data="addamt_custom")])
    btns.append([InlineKeyboardButton("🏠 𝙈𝙖𝙞𝙣 𝙈𝙚𝙣𝙪", callback_data="home")])

    await client.send_message(uid,
        f"╔═══════════════════════════╗\n   💳 **𝘼𝘿𝘿 𝙈𝙊𝙉𝙀𝙔** 💳\n╚═══════════════════════════╝\n\n"
        f"💰 **Amount choose karein:**\n\n_(Min {CURRENCY}10)_",
        reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)


async def show_keys(client, uid):
    rows = db_run("""SELECT k.api_key, k.expires_at, k.is_active, p.name, k.duration_value, k.duration_unit
                    FROM api_keys k JOIN panels p ON k.panel_id = p.id
                    WHERE k.user_id=? ORDER BY k.id DESC LIMIT 20""", (uid,), fetch=True)

    if not rows:
        await client.send_message(uid,
            "🔑 **Abhi tak koi API key nahi!**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ 𝘽𝙧𝙤𝙬𝙨𝙚 𝙋𝙖𝙣𝙚𝙡𝙨", callback_data="browse")],
                [InlineKeyboardButton("🏠 𝙈𝙖𝙞𝙣 𝙈𝙚𝙣𝙪", callback_data="home")]
            ]), parse_mode=ParseMode.MARKDOWN)
        return

    text = f"🔑 **𝙔𝙊𝙐𝙍 𝘼𝙋𝙄 𝙆𝙀𝙔𝙎** 🔑\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, r in enumerate(rows, 1):
        try:
            exp = datetime.fromisoformat(r[1])
            status = "✅ Active" if r[2] == 1 and exp > datetime.now() else "❌ Expired"
        except:
            status = "❌ Unknown"
        text += f"**{i}. {r[3]}** ({duration_label(r[4], r[5])})\n🔑 `{r[0]}`\n{status}\n\n"

    await client.send_message(uid, text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 𝙈𝙖𝙞𝙣 𝙈𝙚𝙣𝙪", callback_data="home")]]),
        parse_mode=ParseMode.MARKDOWN)


async def daily_bonus(client, uid):
    ud = db_run("SELECT wallet, last_bonus FROM users WHERE user_id=?", (uid,), fetch=True)
    if not ud:
        return
    wallet, last_bonus = ud[0][0], ud[0][1]
    if last_bonus:
        try:
            if datetime.now() - datetime.fromisoformat(last_bonus) < timedelta(hours=24):
                remaining = timedelta(hours=24) - (datetime.now() - datetime.fromisoformat(last_bonus))
                h, m_ = remaining.seconds // 3600, (remaining.seconds % 3600) // 60
                msg = await client.send_message(uid, f"⏰ **Already claimed!** Next: **{h}h {m_}m**")
                asyncio.create_task(auto_delete(msg, 10))
                return
        except:
            pass

    bonus = random.randint(DAILY_BONUS, DAILY_BONUS * 3)
    db_run("UPDATE users SET wallet = wallet + ?, last_bonus = ? WHERE user_id=?",
           (bonus, datetime.now().isoformat(), uid))
    db_run("INSERT INTO wallet_txns (user_id, amount, txn_type, note) VALUES (?,?,?,?)",
           (uid, bonus, "daily_bonus", "Daily bonus"))
    msg = await client.send_message(uid,
        f"🎁 **DAILY BONUS!**\n\n💰 **+{CURRENCY}{bonus}**\n💎 **Balance:** `{CURRENCY}{wallet + bonus}`",
        parse_mode=ParseMode.MARKDOWN)
    asyncio.create_task(auto_delete(msg, 15))


# ═══════════════════════════════════════════════════════════
#  🔘 CALLBACKS
# ═══════════════════════════════════════════════════════════
@app.on_callback_query()
@safe_handler
async def cb(client, q: CallbackQuery):
    d = q.data
    uid = q.from_user.id

    user = db_run("SELECT is_banned FROM users WHERE user_id=?", (uid,), fetch=True)
    if user and user[0][0] == 1:
        await q.answer("🚫 Banned!", show_alert=True)
        return

    # ---------- HOME ----------
    if d == "home":
        try:
            await q.message.delete()
        except:
            pass
        try:
            u = q.from_user
            ud = db_run("SELECT wallet, total_spent, is_premium FROM users WHERE user_id=?", (u.id,), fetch=True)
            wallet = ud[0][0] if ud else 0
            total_spent = ud[0][1] if ud else 0
            ref_count = db_run("SELECT COUNT(*) FROM users WHERE referred_by=?", (u.id,), fetch=True)[0][0]
            active_keys = db_run("SELECT COUNT(*) FROM api_keys WHERE user_id=? AND is_active=1", (u.id,), fetch=True)[0][0]
            badge = get_badge(total_spent)

            text = (
                f"╔═══════════════════════════╗\n"
                f"   🏠 **𝙈𝘼𝙄𝙉 𝙈𝙀𝙉𝙐** 🏠\n"
                f"╚═══════════════════════════╝\n\n"
                f"🏅 **{badge}**\n"
                f"💰 Wallet: `{CURRENCY}{wallet}`\n"
                f"🔑 Keys: `{active_keys}`\n"
                f"👥 Referrals: `{ref_count}`"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ 𝘽𝙧𝙤𝙬𝙨𝙚 𝙋𝙖𝙣𝙚𝙡𝙨", callback_data="browse"),
                 InlineKeyboardButton("🔑 𝙈𝙮 𝙆𝙚𝙮𝙨", callback_data="mykeys")],
                [InlineKeyboardButton("💰 𝙒𝙖𝙡𝙡𝙚𝙩", callback_data="wallet"),
                 InlineKeyboardButton("💳 𝘼𝙙𝙙 𝙈𝙤𝙣𝙚𝙮", callback_data="addmoney")],
                [InlineKeyboardButton("📦 𝙈𝙮 𝙊𝙧𝙙𝙚𝙧𝙨", callback_data="myorders"),
                 InlineKeyboardButton("👤 𝙋𝙧𝙤𝙛𝙞𝙡𝙚", callback_data="profile")],
                [InlineKeyboardButton("🎁 𝙍𝙚𝙛𝙚𝙧", callback_data="refer"),
                 InlineKeyboardButton("🎰 𝙎𝙥𝙞𝙣", callback_data="spin")],
            ])
            await client.send_message(uid, text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            print(f"Home err: {e}")
        return

    # ---------- BROWSE ----------
    elif d == "browse":
        cats = db_run("SELECT DISTINCT category FROM panels WHERE is_active=1", fetch=True)
        if not cats:
            await q.answer("❌ Koi panel nahi!", show_alert=True)
            return
        cat_emojis = {"panel": "🎮", "root": "🔓", "non root": "📱", "cheat": "🧪", "mod": "⚡", "proxy": "🌐"}
        btns = []
        for c in cats:
            cnt = db_run("SELECT COUNT(*) FROM panels WHERE category=? AND is_active=1", (c[0],), fetch=True)[0][0]
            emoji = cat_emojis.get(c[0].lower(), "📂")
            btns.append([InlineKeyboardButton(f"{emoji} {c[0].upper()} • {cnt}", callback_data=f"cat_{c[0]}")])
        btns.append([InlineKeyboardButton("🏠 𝙈𝙖𝙞𝙣 𝙈𝙚𝙣𝙪", callback_data="home")])
        await safe_edit(q,
            "╔═══════════════════════════╗\n   🛍️ **𝙋𝘼𝙉𝙀𝙇 𝙎𝙏𝙊𝙍𝙀** 🛍️\n╚═══════════════════════════╝\n\n"
            "📂 **Category:**", InlineKeyboardMarkup(btns))

    elif d.startswith("cat_"):
        cat = d.replace("cat_", "", 1)
        rows = db_run("""SELECT p.id, p.name, MIN(d.price)
                        FROM panels p JOIN panel_durations d ON p.id=d.panel_id
                        WHERE p.category=? AND p.is_active=1 AND d.is_active=1
                        GROUP BY p.id""", (cat,), fetch=True)
        if not rows:
            await q.answer("❌ Khaali category!", show_alert=True)
            return
        btns = []
        for i, r in enumerate(rows, 1):
            btns.append([InlineKeyboardButton(f"🎮 {i}. {r[1]} — From {CURRENCY}{r[2]}",
                                              callback_data=f"view_{r[0]}")])
        btns.append([InlineKeyboardButton("🔙 𝘽𝙖𝙘𝙠", callback_data="browse")])
        btns.append([InlineKeyboardButton("🏠 𝙈𝙖𝙞𝙣 𝙈𝙚𝙣𝙪", callback_data="home")])
        await safe_edit(q,
            f"╔═══════════════════════════╗\n   📂 **{cat.upper()}** 📂\n╚═══════════════════════════╝\n\n"
            f"🎯 **{len(rows)} Panels**",
            InlineKeyboardMarkup(btns))

    # ---------- VIEW PANEL ----------
    elif d.startswith("view_"):
        pid = int(d.split("_")[1])
        p = db_run("SELECT id, name, description, category, sales FROM panels WHERE id=?", (pid,), fetch=True)
        if not p:
            await q.answer("❌ Not found!", show_alert=True)
            return
        p = p[0]
        durations = db_run("SELECT id, duration_value, duration_unit, price FROM panel_durations WHERE panel_id=? AND is_active=1",
                           (pid,), fetch=True)
        if not durations:
            await q.answer("❌ Koi duration nahi!", show_alert=True)
            return

        dur_text = ""
        btns = []
        for dr in durations:
            label = duration_label(dr[1], dr[2])
            dur_text += f"⏱️ **{label}** — `{CURRENCY}{dr[3]}`\n"
            btns.append([InlineKeyboardButton(
                f"⏱️ {label} — {CURRENCY}{dr[3]}",
                callback_data=f"pickdur_{pid}_{dr[0]}_{dr[1]}_{dr[2]}_{dr[3]}"
            )])

        btns.append([InlineKeyboardButton("🔙 𝘽𝙖𝙘𝙠", callback_data=f"cat_{p[3]}")])
        btns.append([InlineKeyboardButton("🏠 𝙈𝙖𝙞𝙣 𝙈𝙚𝙣𝙪", callback_data="home")])

        text = (
            f"╔═══════════════════════════╗\n"
            f"   🎮 **{p[1]}** 🎮\n"
            f"╚═══════════════════════════╝\n\n"
            f"📝 {p[2]}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷️ {p[3]} | 📦 Sold: {p[4]}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⏱️ **Durations:**\n\n{dur_text}\n"
            f"👇 **Select karein:**"
        )
        await safe_edit(q, text, InlineKeyboardMarkup(btns))

    # ---------- PICK DURATION ----------
    elif d.startswith("pickdur_"):
        parts = d.split("_")
        pid = int(parts[1])
        dur_id = int(parts[2])
        value = int(parts[3])
        unit = parts[4]
        price = int(parts[5])

        p = db_run("SELECT name FROM panels WHERE id=?", (pid,), fetch=True)
        if not p:
            await q.answer("❌ Not found!", show_alert=True)
            return
        p = p[0]
        ud = db_run("SELECT wallet FROM users WHERE user_id=?", (uid,), fetch=True)
        wallet = ud[0][0] if ud else 0

        text = (
            f"╔═══════════════════════════╗\n"
            f"   💳 **𝙋𝘼𝙔𝙈𝙀𝙉𝙏** 💳\n"
            f"╚═══════════════════════════╝\n\n"
            f"🎮 **Panel:** {p[0]}\n"
            f"⏱️ **Duration:** {duration_label(value, unit)}\n"
            f"💰 **Price:** `{CURRENCY}{price}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💼 **Wallet:** `{CURRENCY}{wallet}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👇 **Payment method:**"
        )
        kb = [
            [InlineKeyboardButton(f"💰 𝘽𝙪𝙮 𝙬𝙞𝙩𝙝 𝙒𝙖𝙡𝙡𝙚𝙩", callback_data=f"payw_{pid}_{dur_id}_{value}_{unit}_{price}")],
            [InlineKeyboardButton(f"💳 𝘽𝙪𝙮 𝙬𝙞𝙩𝙝 𝘾𝙖𝙧𝙙/𝙐𝙋𝙄", callback_data=f"payc_{pid}_{dur_id}_{value}_{unit}_{price}")],
            [InlineKeyboardButton("🔙 𝘽𝙖𝙘𝙠", callback_data=f"view_{pid}")],
        ]
        await safe_edit(q, text, InlineKeyboardMarkup(kb))

    # ---------- PAY WITH WALLET ----------
    elif d.startswith("payw_"):
        parts = d.split("_")
        pid = int(parts[1]); dur_id = int(parts[2]); value = int(parts[3]); unit = parts[4]; price = int(parts[5])

        p = db_run("SELECT name FROM panels WHERE id=?", (pid,), fetch=True)
        if not p:
            return
        p = p[0]
        ud = db_run("SELECT wallet FROM users WHERE user_id=?", (uid,), fetch=True)
        wallet = ud[0][0] if ud else 0

        if wallet < price:
            await q.answer(f"❌ Insufficient! Need {CURRENCY}{price - wallet} more", show_alert=True)
            return

        db_run("UPDATE users SET wallet = wallet - ?, total_spent = total_spent + ? WHERE user_id=?",
               (price, price, uid))
        db_run("INSERT INTO wallet_txns (user_id, amount, txn_type, note) VALUES (?,?,?,?)",
               (uid, -price, "purchase", f"{p[0]} {duration_label(value, unit)}"))

        order_id = db_run(
            "INSERT INTO orders (user_id, panel_id, duration_id, duration_value, duration_unit, amount, payment_method, status) VALUES (?,?,?,?,?,?,?,?)",
            (uid, pid, dur_id, value, unit, price, "wallet", "pending"))

        await deliver_panel(client, uid, pid, order_id, value, unit)

        try:
            await client.send_message(ADMIN_ID,
                f"💰 **WALLET PURCHASE**\n👤 `{uid}`\n🎮 {p[0]}\n⏱️ {duration_label(value, unit)}\n💵 {CURRENCY}{price}",
                parse_mode=ParseMode.MARKDOWN)
        except:
            pass

        await q.answer("✅ Delivered! Check /mykeys", show_alert=True)

    # ---------- PAY WITH CASHFREE ----------
    elif d.startswith("payc_"):
        parts = d.split("_")
        pid = int(parts[1]); dur_id = int(parts[2]); value = int(parts[3]); unit = parts[4]; price = int(parts[5])

        p = db_run("SELECT name FROM panels WHERE id=?", (pid,), fetch=True)
        if not p:
            return
        p = p[0]

        loading = await q.message.reply_text("⏳ Creating payment...")
        cf_order_id = f"PANEL_{uid}_{int(time.time())}"
        cf_result = cf_create_order(
            order_id=cf_order_id, amount=price, customer_id=str(uid),
            customer_phone="9999999999", customer_email="user@panelbot.com",
            return_url=f"https://t.me/{(await client.get_me()).username}")
        try:
            await loading.delete()
        except:
            pass

        if not cf_result:
            await q.message.reply_text("❌ Gateway error!")
            return

        psid = cf_result.get("payment_session_id")
        pay_link = f"https://sandbox.cashfree.com/pg/view/sessions/{psid}" if CASHFREE_ENV == "sandbox" else f"https://api.cashfree.com/pg/view/sessions/{psid}"

        order_db_id = db_run(
            "INSERT INTO orders (user_id, panel_id, duration_id, duration_value, duration_unit, amount, payment_method, status, cf_order_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (uid, pid, dur_id, value, unit, price, "cashfree", "pending", cf_order_id))

        text = (
            f"╔═══════════════════════════╗\n   💳 **𝙋𝘼𝙔𝙈𝙀𝙉𝙏** 💳\n╚═══════════════════════════╝\n\n"
            f"🎮 **{p[0]}**\n⏱️ **{duration_label(value, unit)}**\n💰 **{CURRENCY}{price}**\n🆔 `{cf_order_id}`\n\n"
            f"👇 Pay karein:"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 𝙋𝘼𝙔 𝙉𝙊𝙒", url=pay_link)],
            [InlineKeyboardButton("❌ 𝘾𝙖𝙣𝙘𝙚𝙡", callback_data="home")]
        ])
        await q.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        asyncio.create_task(poll_payment(client, uid, order_db_id, cf_order_id, pid, value, unit))

    # ---------- MY KEYS / WALLET / ADD MONEY ----------
    elif d == "mykeys":
        await show_keys(client, uid)

    elif d == "wallet":
        await show_wallet(client, uid)

    elif d == "addmoney":
        await add_money_prompt(client, uid)

    elif d.startswith("addamt_"):
        val = d.replace("addamt_", "")
        if val == "custom":
            user_states[uid] = {"action": "custom_amount"}
            await q.message.reply_text("✏️ Amount bhejein (Min ₹10):\n❌ /cancel")
            return

        amount = int(val)
        if amount < 10:
            await q.answer("❌ Min ₹10", show_alert=True)
            return

        loading = await q.message.reply_text("⏳ Creating payment...")
        cf_order_id = f"WALLET_{uid}_{int(time.time())}"
        cf_result = cf_create_order(
            order_id=cf_order_id, amount=amount, customer_id=str(uid),
            customer_phone="9999999999", customer_email="user@panelbot.com",
            return_url=f"https://t.me/{(await client.get_me()).username}")
        try:
            await loading.delete()
        except:
            pass

        if not cf_result:
            await q.message.reply_text("❌ Gateway error!")
            return

        psid = cf_result.get("payment_session_id")
        pay_link = f"https://sandbox.cashfree.com/pg/view/sessions/{psid}" if CASHFREE_ENV == "sandbox" else f"https://api.cashfree.com/pg/view/sessions/{psid}"

        order_db_id = db_run(
            "INSERT INTO orders (user_id, panel_id, duration_id, duration_value, duration_unit, amount, payment_method, status, cf_order_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (uid, 0, 0, 0, "", amount, "wallet_topup", "pending", cf_order_id))

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 𝙋𝘼𝙔 𝙉𝙊𝙒", url=pay_link)],
            [InlineKeyboardButton("❌ 𝘾𝙖𝙣𝙘𝙚𝙡", callback_data="home")]
        ])
        await q.message.reply_text(f"💳 **Wallet Top-Up**\n💰 `{CURRENCY}{amount}`",
            reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        asyncio.create_task(poll_wallet_payment(client, uid, order_db_id, cf_order_id, amount))

    # ---------- PROFILE ----------
    elif d == "profile":
        ud = db_run("SELECT wallet, total_spent, is_premium, joined_at FROM users WHERE user_id=?", (uid,), fetch=True)
        wallet, total_spent, is_premium, joined = ud[0] if ud else (0, 0, 0, "")
        badge = get_badge(total_spent)
        keys = db_run("SELECT COUNT(*) FROM api_keys WHERE user_id=?", (uid,), fetch=True)[0][0]

        text = (
            f"╔═══════════════════════════╗\n   👤 **𝙔𝙊𝙐𝙍 𝙋𝙍𝙊𝙁𝙄𝙇𝙀** 👤\n╚═══════════════════════════╝\n\n"
            f"🆔 `{uid}`\n👤 {q.from_user.first_name}\n🌐 @{q.from_user.username or 'N/A'}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏅 {badge}\n💎 {'PREMIUM' if is_premium else 'FREE'}\n"
            f"💰 `{CURRENCY}{wallet}`\n🔑 Keys: `{keys}`\n💸 Spent: `{CURRENCY}{total_spent}`"
        )
        await safe_edit(q, text, InlineKeyboardMarkup([[InlineKeyboardButton("🏠 𝙈𝙖𝙞𝙣 𝙈𝙚𝙣𝙪", callback_data="home")]]))

    # ---------- MY ORDERS ----------
    elif d == "myorders":
        rows = db_run("""SELECT o.id, p.name, o.amount, o.status, o.payment_method, o.duration_value, o.duration_unit
                        FROM orders o LEFT JOIN panels p ON o.panel_id=p.id
                        WHERE o.user_id=? ORDER BY o.id DESC LIMIT 10""", (uid,), fetch=True)
        if not rows:
            await q.answer("📦 Koi order nahi!", show_alert=True)
            return
        text = "╔═══════════════════════════╗\n   📦 **𝙈𝙔 𝙊𝙍𝘿𝙀𝙍𝙎** 📦\n╚═══════════════════════════╝\n\n"
        for o in rows:
            emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(o[3], "❓")
            dur = f" • {duration_label(o[5], o[6])}" if o[5] else ""
            text += f"{emoji} #{o[0]} — {o[1] or 'Top-Up'}{dur}\n   {CURRENCY}{o[2]} | {o[4]}\n\n"
        await safe_edit(q, text, InlineKeyboardMarkup([[InlineKeyboardButton("🏠 𝙈𝙖𝙞𝙣 𝙈𝙚𝙣𝙪", callback_data="home")]]))

    # ---------- REFER ----------
    elif d == "refer":
        bot_user = (await client.get_me()).username
        link = f"https://t.me/{bot_user}?start={uid}"
        ref_count = db_run("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,), fetch=True)[0][0]
        earned = ref_count * REFERRAL_BONUS
        text = (
            f"╔═══════════════════════════╗\n   🎁 **𝙍𝙀𝙁𝙀𝙍 & 𝙀𝘼𝙍𝙉** 🎁\n╚═══════════════════════════╝\n\n"
            f"💰 Per Refer: `{CURRENCY}{REFERRAL_BONUS}`\n👥 Yours: `{ref_count}`\n💵 Earned: `{CURRENCY}{earned}`\n\n"
            f"🔗 `{link}`"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 𝙎𝙝𝙖𝙧𝙚", url=f"https://t.me/share/url?url={link}&text=🎮 Best Panel Store!")],
            [InlineKeyboardButton("🏠 𝙈𝙖𝙞𝙣 𝙈𝙚𝙣𝙪", callback_data="home")]
        ])
        await safe_edit(q, text, kb)

    # ---------- SPIN ----------
    elif d == "spin":
        spin_msg = await q.message.reply_text("🎰 Spinning...")
        for f in ["🎰", "🎯", "🎲", "🎁", "💰", "💎"]:
            await asyncio.sleep(0.4)
            try:
                await spin_msg.edit_text(f"{f} Spinning...")
            except:
                pass
        prizes = [("₹5", 5, "💰"), ("₹10", 10, "💰"), ("₹20", 20, "💵"),
                  ("₹50", 50, "💎"), ("Better luck!", 0, "😢"), ("₹2", 2, "🪙")]
        txt, val, emoji = random.choices(prizes, weights=[20, 15, 8, 2, 40, 15])[0]
        if val > 0:
            db_run("UPDATE users SET wallet = wallet + ? WHERE user_id=?", (val, uid))
            db_run("INSERT INTO wallet_txns (user_id, amount, txn_type, note) VALUES (?,?,?,?)",
                   (uid, val, "spin", "Spin win"))
        await spin_msg.edit_text(f"🎰 **SPIN RESULT**\n\n{emoji} **{txt}**", parse_mode=ParseMode.MARKDOWN)

    elif d == "daily":
        await daily_bonus(client, uid)

    # ---------- ADMIN ----------
    elif d.startswith("approve_"):
        if not is_admin(uid):
            return
        oid = int(d.split("_")[1])
        o = db_run("SELECT user_id, panel_id, duration_value, duration_unit FROM orders WHERE id=?", (oid,), fetch=True)
        if not o:
            return
        o = o[0]
        await deliver_panel(client, o[0], o[1], oid, o[2] or 30, o[3] or "days")
        await q.message.edit_text(f"✅ Order #{oid} Approved!")

    elif d.startswith("reject_"):
        if not is_admin(uid):
            return
        oid = int(d.split("_")[1])
        o = db_run("SELECT user_id FROM orders WHERE id=?", (oid,), fetch=True)
        if o:
            db_run("UPDATE orders SET status='rejected' WHERE id=?", (oid,))
            try:
                await client.send_message(o[0][0], f"❌ Order #{oid} rejected.")
            except:
                pass
        await q.message.edit_text(f"❌ Order #{oid} Rejected!")


# ═══════════════════════════════════════════════════════════
#  ⏳ PAYMENT POLLING
# ═══════════════════════════════════════════════════════════
async def poll_payment(client, uid, order_db_id, cf_order_id, panel_id, value, unit):
    for _ in range(100):
        await asyncio.sleep(3)
        try:
            st = cf_status(cf_order_id)
            if st:
                if st.get("order_status") == "PAID":
                    await deliver_panel(client, uid, panel_id, order_db_id, value, unit)
                    return
                elif st.get("order_status") in ["EXPIRED", "CANCELLED"]:
                    db_run("UPDATE orders SET status='rejected' WHERE id=?", (order_db_id,))
                    return
        except Exception as e:
            print(f"Poll err: {e}")
    db_run("UPDATE orders SET status='rejected' WHERE id=?", (order_db_id,))


async def poll_wallet_payment(client, uid, order_db_id, cf_order_id, amount):
    for _ in range(100):
        await asyncio.sleep(3)
        try:
            st = cf_status(cf_order_id)
            if st and st.get("order_status") == "PAID":
                db_run("UPDATE users SET wallet = wallet + ? WHERE user_id=?", (amount, uid))
                db_run("INSERT INTO wallet_txns (user_id, amount, txn_type, note) VALUES (?,?,?,?)",
                       (uid, amount, "topup", "Wallet top-up"))
                db_run("UPDATE orders SET status='approved' WHERE id=?", (order_db_id,))
                try:
                    await client.send_message(uid, f"✅ Wallet Top-Up!\n💰 +{CURRENCY}{amount}",
                        parse_mode=ParseMode.MARKDOWN)
                except:
                    pass
                return
        except Exception as e:
            print(f"Poll wallet err: {e}")


# ═══════════════════════════════════════════════════════════
#  📝 USER TEXT
# ═══════════════════════════════════════════════════════════
@app.on_message(filters.private & filters.text & ~filters.command(COMMANDS) & ~filters.user(ADMIN_ID))
@safe_handler
async def user_text(client, message: Message):
    uid = message.from_user.id
    text = message.text.strip()

    if uid in user_states and user_states[uid].get("action") == "custom_amount":
        del user_states[uid]
        try:
            amt = int(text)
            if amt < 10 or amt > 10000:
                await message.reply_text("❌ ₹10 - ₹10000")
                return
        except:
            await message.reply_text("❌ Valid number bhejein")
            return

        loading = await message.reply_text("⏳ Creating...")
        cf_order_id = f"WALLET_{uid}_{int(time.time())}"
        cf_result = cf_create_order(
            order_id=cf_order_id, amount=amt, customer_id=str(uid),
            customer_phone="9999999999", customer_email="user@panelbot.com",
            return_url=f"https://t.me/{(await client.get_me()).username}")
        try:
            await loading.delete()
        except:
            pass

        if not cf_result:
            await message.reply_text("❌ Error!")
            return

        psid = cf_result.get("payment_session_id")
        pay_link = f"https://sandbox.cashfree.com/pg/view/sessions/{psid}" if CASHFREE_ENV == "sandbox" else f"https://api.cashfree.com/pg/view/sessions/{psid}"

        order_db_id = db_run(
            "INSERT INTO orders (user_id, panel_id, duration_id, duration_value, duration_unit, amount, payment_method, status, cf_order_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (uid, 0, 0, 0, "", amt, "wallet_topup", "pending", cf_order_id))

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💳 𝙋𝘼𝙔 𝙉𝙊𝙒", url=pay_link)]])
        await message.reply_text(f"💳 **Top-Up**\n💰 `{CURRENCY}{amt}`", reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        asyncio.create_task(poll_wallet_payment(client, uid, order_db_id, cf_order_id, amt))
        return


# ═══════════════════════════════════════════════════════════
#  👑 ADMIN — ADD PANEL + DURATION
# ═══════════════════════════════════════════════════════════
@app.on_message(filters.command("addpanel") & filters.private)
@safe_handler
async def addpanel_cmd(c, m):
    if not is_admin(m.from_user.id):
        return
    try:
        await m.delete()
    except:
        pass
    admin_states[m.from_user.id] = {"step": "name"}
    await m.reply_text("📝 **Step 1/3:** Panel **naam**:")


@app.on_message(filters.private & filters.text & ~filters.command(COMMANDS) & filters.user(ADMIN_ID))
@safe_handler
async def admin_text(c, m):
    uid = m.from_user.id
    if uid not in admin_states:
        return
    s = admin_states[uid]
    step = s.get("step")

    if step == "name":
        s["name"] = m.text
        s["step"] = "description"
        await m.reply_text("📝 **Step 2/3:** Description:")
    elif step == "description":
        s["description"] = m.text
        s["step"] = "category"
        await m.reply_text("🏷️ **Step 3/3:** Category (Panel, Root, Non Root, Cheat, Mod):")
    elif step == "category":
        s["category"] = m.text
        pid = db_run("INSERT INTO panels (name, description, category) VALUES (?,?,?)",
                     (s["name"], s["description"], s["category"]))
        del admin_states[uid]
        await m.reply_text(
            f"✅ **PANEL ADDED!**\n🆔 `{pid}`\n🎮 {s['name']}\n\n"
            f"⚠️ Ab durations: `/addduration {pid}`")

    elif step == "dur_value":
        try:
            val = int(m.text)
            if val < 1:
                raise ValueError
        except:
            await m.reply_text("❌ Positive number bhejein!")
            return
        s["dur_value"] = val
        s["step"] = "dur_unit"
        await m.reply_text(
            "⏱️ **Unit choose karein:**\n\n"
            "`minutes` — minutes ke liye\n"
            "`hours` — hours ke liye\n"
            "`days` — days ke liye")
    elif step == "dur_unit":
        unit = m.text.strip().lower()
        if unit not in ["minutes", "hours", "days"]:
            await m.reply_text("❌ Sirf `minutes`, `hours` ya `days`")
            return
        s["dur_unit"] = unit
        s["step"] = "dur_price"
        await m.reply_text(f"💰 **Price for {duration_label(s['dur_value'], unit)}** (number):")
    elif step == "dur_price":
        try:
            price = int(m.text)
        except:
            await m.reply_text("❌ Sirf number!")
            return
        pid = s["panel_id"]
        v, u = s["dur_value"], s["dur_unit"]
        db_run("INSERT INTO panel_durations (panel_id, duration_value, duration_unit, price) VALUES (?,?,?,?)",
               (pid, v, u, price))
        del admin_states[uid]
        await m.reply_text(
            f"✅ **Duration Added!**\n\n🎮 Panel #{pid}\n⏱️ {duration_label(v, u)} — {CURRENCY}{price}\n\n"
            f"Add more: `/addduration {pid}`")


@app.on_message(filters.command("addduration") & filters.private)
@safe_handler
async def addduration_cmd(c, m):
    if not is_admin(m.from_user.id):
        return
    try:
        pid = int(m.command[1])
    except:
        await m.reply_text("Usage: `/addduration <panel_id>`")
        return
    if not db_run("SELECT 1 FROM panels WHERE id=?", (pid,), fetch=True):
        await m.reply_text("❌ Panel not found!")
        return
    admin_states[m.from_user.id] = {"step": "dur_value", "panel_id": pid}
    await m.reply_text(
        f"⏱️ **Duration for Panel #{pid}**\n\n"
        f"Value bhejein (number):\n"
        f"_Examples: `30` (30 days), `24` (24 hours), `30` (30 mins)_")


@app.on_message(filters.command("listdurations") & filters.private)
@safe_handler
async def listdurations_cmd(c, m):
    if not is_admin(m.from_user.id):
        return
    try:
        pid = int(m.command[1])
    except:
        await m.reply_text("Usage: `/listdurations <panel_id>`")
        return
    p = db_run("SELECT name FROM panels WHERE id=?", (pid,), fetch=True)
    if not p:
        await m.reply_text("❌ Not found!")
        return
    rows = db_run("SELECT id, duration_value, duration_unit, price FROM panel_durations WHERE panel_id=?",
                  (pid,), fetch=True)
    if not rows:
        await m.reply_text(f"❌ No durations for #{pid}")
        return
    txt = f"📅 **Durations for {p[0][0]}** (#{pid})\n\n"
    for r in rows:
        txt += f"🆔 `{r[0]}` — {duration_label(r[1], r[2])} | {CURRENCY}{r[3]}\n"
    await m.reply_text(txt, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("listpanels") & filters.private)
@safe_handler
async def listpanels_cmd(c, m):
    if not is_admin(m.from_user.id):
        return
    rows = db_run("SELECT id, name, category, sales FROM panels", fetch=True)
    if not rows:
        await m.reply_text("❌ Koi panel nahi!")
        return
    txt = "🎮 **ALL PANELS** 🎮\n\n"
    for r in rows:
        dc = db_run("SELECT COUNT(*) FROM panel_durations WHERE panel_id=?", (r[0],), fetch=True)[0][0]
        txt += f"🆔 `{r[0]}` — {r[1]}\n   🏷️ {r[2]} | 📅 {dc} durations | 📦 {r[3]}\n\n"
    await m.reply_text(txt, parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("deletepanel") & filters.private)
@safe_handler
async def deletepanel_cmd(c, m):
    if not is_admin(m.from_user.id):
        return
    try:
        pid = int(m.command[1])
        db_run("DELETE FROM panel_durations WHERE panel_id=?", (pid,))
        db_run("DELETE FROM panels WHERE id=?", (pid,))
        await m.reply_text(f"✅ Deleted `{pid}`")
    except:
        await m.reply_text("Usage: `/deletepanel <id>`")


@app.on_message(filters.command("pendingorders") & filters.private)
@safe_handler
async def pending_cmd(c, m):
    if not is_admin(m.from_user.id):
        return
    rows = db_run("""SELECT o.id, o.user_id, o.amount, o.payment_method, p.name, o.duration_value, o.duration_unit
                    FROM orders o LEFT JOIN panels p ON o.panel_id=p.id
                    WHERE o.status='pending'""", fetch=True)
    if not rows:
        await m.reply_text("✅ No pending orders")
        return
    for o in rows:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{o[0]}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{o[0]}"),
        ]])
        dur = f" | {duration_label(o[5], o[6])}" if o[5] else ""
        await m.reply_text(
            f"🆔 #{o[0]}\n👤 `{o[1]}`\n🎮 {o[4] or 'Top-Up'}{dur}\n💰 {CURRENCY}{o[2]}\n💳 {o[3]}",
            reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════
#  🧪 TEST API COMMAND
# ═══════════════════════════════════════════════════════════
@app.on_message(filters.command("testapi") & filters.private)
@safe_handler
async def testapi_cmd(c, m):
    if not is_admin(m.from_user.id):
        return
    try:
        dur = int(m.command[1]) if len(m.command) > 1 else 1
        unit = m.command[2] if len(m.command) > 2 else "days"
    except:
        await m.reply_text("Usage: `/testapi <value> <unit>`\nExample: `/testapi 5 minutes`")
        return

    msg = await m.reply_text(f"📡 Testing API...\n\nDuration: {dur} {unit}")
    result = generate_panel_key_from_provider(
        m.from_user.id, "test_user", "TEST_PANEL", dur, unit
    )

    if result:
        await msg.edit_text(
            f"✅ **API WORKING!**\n\n"
            f"🔑 Key: `{result['key']}`\n"
            f"⏰ Validity: `{result.get('validity', 'N/A')}`\n"
            f"📌 Duration: {dur} {unit}",
            parse_mode=ParseMode.MARKDOWN)
    else:
        await msg.edit_text(
            f"❌ **API FAILED**\n\n"
            f"Check:\n"
            f"• `PANEL_API_URL` in Render Env\n"
            f"• `PANEL_API_KEY` correct?\n"
            f"• Node.js app chal rahi hai?\n\n"
            f"Current URL: `{PANEL_API_URL or 'NOT SET'}`",
            parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("apiinfo") & filters.private)
@safe_handler
async def apiinfo_cmd(c, m):
    if not is_admin(m.from_user.id):
        return
    text = (
        f"🌐 **PANEL API INFO**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔗 URL: `{PANEL_API_URL or 'NOT SET'}`\n"
        f"🔑 Key: `{PANEL_API_KEY[:20]}...`\n"
        f"🌐 Bot API: `https://fixamods-bot.onrender.com`\n"
        f"🔐 Bot API Key: `{'SET' if BOT_API_KEY else 'NOT SET'}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 **Test:** `/testapi 30 days`\n"
        f"📌 **Test:** `/testapi 24 hours`\n"
        f"📌 **Test:** `/testapi 30 minutes`"
    )
    await m.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════
#  👑 ADMIN PANEL
# ═══════════════════════════════════════════════════════════
@app.on_message(filters.command("admin") & filters.private)
@safe_handler
async def admin_cmd(c, m):
    if not is_admin(m.from_user.id):
        return
    try:
        await m.delete()
    except:
        pass
    users = db_run("SELECT COUNT(*) FROM users", fetch=True)[0][0]
    panels = db_run("SELECT COUNT(*) FROM panels", fetch=True)[0][0]
    keys = db_run("SELECT COUNT(*) FROM api_keys WHERE is_active=1", fetch=True)[0][0]
    revenue = db_run("SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='approved'", fetch=True)[0][0]

    await m.reply_text(
        f"👑 **ADMIN PANEL**\n\n"
        f"👥 Users: `{users}`\n"
        f"🎮 Panels: `{panels}`\n"
        f"🔑 Keys: `{keys}`\n"
        f"💰 Revenue: `{CURRENCY}{revenue}`\n\n"
        f"**Commands:**\n"
        f"/addpanel — Add panel\n"
        f"/addduration <id> — Add duration\n"
        f"/listpanels — List panels\n"
        f"/listdurations <id> — List durations\n"
        f"/addwallet <uid> <amt> — Add wallet\n"
        f"/deductwallet <uid> <amt> — Deduct\n"
        f"/userinfo <uid> — User info\n"
        f"/pendingorders — Pending\n"
        f"/testapi <v> <unit> — Test API\n"
        f"/apiinfo — API config\n"
        f"/broadcast <msg> — Broadcast\n"
        f"/ban <uid> /unban <uid>\n"
        f"/maintenance",
        parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("addwallet") & filters.private)
@safe_handler
async def addwallet_cmd(c, m):
    if not is_admin(m.from_user.id):
        return
    try:
        uid = int(m.command[1]); amt = int(m.command[2])
        note = m.text.split(None, 3)[3] if len(m.command) > 3 else "Admin credit"
    except:
        await m.reply_text("Usage: `/addwallet <uid> <amt> [note]`")
        return
    if not db_run("SELECT 1 FROM users WHERE user_id=?", (uid,), fetch=True):
        await m.reply_text("❌ User not found!")
        return
    db_run("UPDATE users SET wallet = wallet + ? WHERE user_id=?", (amt, uid))
    db_run("INSERT INTO wallet_txns (user_id, amount, txn_type, note) VALUES (?,?,?,?)",
           (uid, amt, "admin_credit", note))
    await m.reply_text(f"✅ Added {CURRENCY}{amt} to `{uid}`")
    try:
        await c.send_message(uid, f"💰 **+{CURRENCY}{amt}** credited!", parse_mode=ParseMode.MARKDOWN)
    except:
        pass


@app.on_message(filters.command("deductwallet") & filters.private)
@safe_handler
async def deductwallet_cmd(c, m):
    if not is_admin(m.from_user.id):
        return
    try:
        uid = int(m.command[1]); amt = int(m.command[2])
    except:
        await m.reply_text("Usage: `/deductwallet <uid> <amt>`")
        return
    db_run("UPDATE users SET wallet = wallet - ? WHERE user_id=?", (amt, uid))
    db_run("INSERT INTO wallet_txns (user_id, amount, txn_type, note) VALUES (?,?,?,?)",
           (uid, -amt, "admin_debit", "Admin debit"))
    await m.reply_text(f"✅ Deducted {CURRENCY}{amt}")


@app.on_message(filters.command("userinfo") & filters.private)
@safe_handler
async def userinfo_cmd(c, m):
    if not is_admin(m.from_user.id):
        return
    try:
        uid = int(m.command[1])
    except:
        await m.reply_text("Usage: `/userinfo <uid>`")
        return
    ud = db_run("SELECT wallet, total_spent, is_premium, is_banned, joined_at FROM users WHERE user_id=?", (uid,), fetch=True)
    if not ud:
        await m.reply_text("❌ Not found!")
        return
    ud = ud[0]
    keys = db_run("SELECT COUNT(*) FROM api_keys WHERE user_id=?", (uid,), fetch=True)[0][0]
    await m.reply_text(
        f"👤 **USER INFO**\n🆔 `{uid}`\n💰 `{CURRENCY}{ud[0]}`\n💸 `{CURRENCY}{ud[1]}`\n"
        f"🔑 Keys: `{keys}`\n💎 Premium: {'✅' if ud[2] else '❌'}\n🚫 Banned: {'✅' if ud[3] else '❌'}",
        parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("ban") & filters.private)
@safe_handler
async def ban_cmd(c, m):
    if not is_admin(m.from_user.id): return
    try:
        db_run("UPDATE users SET is_banned=1 WHERE user_id=?", (int(m.command[1]),))
        await m.reply_text("🚫 Banned")
    except:
        await m.reply_text("Usage: `/ban <uid>`")


@app.on_message(filters.command("unban") & filters.private)
@safe_handler
async def unban_cmd(c, m):
    if not is_admin(m.from_user.id): return
    try:
        db_run("UPDATE users SET is_banned=0 WHERE user_id=?", (int(m.command[1]),))
        await m.reply_text("✅ Unbanned")
    except:
        await m.reply_text("Usage: `/unban <uid>`")


@app.on_message(filters.command("maintenance") & filters.private)
@safe_handler
async def maint_cmd(c, m):
    if not is_admin(m.from_user.id): return
    cur = get_setting("maintenance")
    new = "off" if cur == "on" else "on"
    set_setting("maintenance", new)
    await m.reply_text(f"🚨 Maintenance: **{new.upper()}**", parse_mode=ParseMode.MARKDOWN)


@app.on_message(filters.command("broadcast") & filters.private)
@safe_handler
async def broadcast_cmd(c, m):
    if not is_admin(m.from_user.id): return
    if len(m.command) < 2:
        await m.reply_text("Usage: `/broadcast <msg>`")
        return
    msg = m.text.split(None, 1)[1]
    users = db_run("SELECT user_id FROM users WHERE is_banned=0", fetch=True)
    ok, fail = 0, 0
    s = await m.reply_text(f"📢 Sending to {len(users)}...")
    for u in users:
        try:
            await c.send_message(u[0], msg)
            ok += 1
        except:
            fail += 1
    await s.edit_text(f"✅ Done! ✔️ {ok} | ❌ {fail}")


@app.on_message(filters.command("mykeys") & filters.private)
@safe_handler
async def mykeys_cmd(c, m):
    await show_keys(c, m.from_user.id)


@app.on_message(filters.command("wallet") & filters.private)
@safe_handler
async def wallet_cmd(c, m):
    await show_wallet(c, m.from_user.id)


@app.on_message(filters.command("cancel") & filters.private)
@safe_handler
async def cancel_cmd(c, m):
    try:
        await m.delete()
    except:
        pass
    user_states.pop(m.from_user.id, None)
    admin_states.pop(m.from_user.id, None)
    msg = await m.reply_text("❌ Cancelled")
    asyncio.create_task(auto_delete(msg, 5))


@app.on_message(filters.command("ping") & filters.private)
@safe_handler
async def ping_cmd(c, m):
    start = time.time()
    msg = await m.reply_text("🏓 Pong!")
    await msg.edit_text(f"⚡ `{round((time.time() - start) * 1000, 2)} ms`")


# ═══════════════════════════════════════════════════════════
#  🔄 AUTO RESTART
# ═══════════════════════════════════════════════════════════
def run_bot_forever():
    while True:
        try:
            print("🎮 Starting Panel Bot...")
            app.run()
        except Exception as e:
            print(f"❌ Crashed: {e}")
            traceback.print_exc()
            print("⏳ Restarting in 5s...")
            time.sleep(5)


if __name__ == "__main__":
    print("🎮 FIXAMODS PANEL BOT starting...")
    print(f"👑 Admin: {ADMIN_ID}")
    print(f"📡 Panel API URL: {PANEL_API_URL or 'NOT SET'}")
    if PANEL_API_KEY:
        print(f"🔑 Panel API Key: {PANEL_API_KEY[:20]}...")
    else:
        print("❌ Panel API Key: NOT SET")
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot_forever()