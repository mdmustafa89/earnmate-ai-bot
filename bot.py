import os
import threading
import sqlite3
from flask import Flask, request, redirect, session, render_template_string

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "change-this-secret")

DB_FILE = "earnmate.db"


# =========================
# Database
# =========================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            referred_by INTEGER,
            referrals INTEGER DEFAULT 0,
            balance REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            link TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            link TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS social_links (
            id INTEGER PRIMARY KEY,
            facebook TEXT,
            youtube TEXT,
            telegram TEXT,
            whatsapp TEXT
        )
    """)

    cur.execute("""
        INSERT OR IGNORE INTO social_links
        (id, facebook, youtube, telegram, whatsapp)
        VALUES (1, '', '', '', '')
    """)

    conn.commit()
    conn.close()


init_db()


# =========================
# Flask Admin Panel
# =========================

web_app = Flask(__name__)
web_app.secret_key = SECRET_KEY


LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EarnMate Admin Login</title>
<style>
body{font-family:Arial;background:#f2f2f2;padding:30px}
.box{max-width:400px;margin:50px auto;background:white;padding:25px;border-radius:15px}
input,button{width:100%;padding:13px;margin:8px 0;box-sizing:border-box}
button{cursor:pointer}
.error{color:red}
</style>
</head>
<body>
<div class="box">
<h2>👑 EarnMate Admin Login</h2>

{% if error %}
<p class="error">{{ error }}</p>
{% endif %}

<form method="POST">
<input name="admin_id" placeholder="Telegram Admin ID" required>
<input name="password" type="password" placeholder="Admin Password" required>
<button type="submit">🔐 Login</button>
</form>
</div>
</body>
</html>
"""


PANEL_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EarnMate Admin Panel</title>
<style>
body{font-family:Arial;background:#f5f5f5;padding:15px}
.container{max-width:900px;margin:auto}
.box{background:white;padding:20px;margin-bottom:20px;border-radius:15px}
input,textarea,button{width:100%;padding:12px;margin:7px 0;box-sizing:border-box}
button{cursor:pointer}
.stat{font-size:18px;margin:8px 0}
.item{border-top:1px solid #ddd;padding:10px 0}
</style>
</head>
<body>

<div class="container">

<h1>👑 EarnMate AI Admin Panel</h1>

<div class="box">
<h2>📊 Dashboard</h2>

<p class="stat">👥 Total Users: <b>{{ total_users }}</b></p>
<p class="stat">🔗 Total Referrals: <b>{{ total_referrals }}</b></p>
<p class="stat">💰 Total Balance: <b>{{ total_balance }}</b></p>
<p class="stat">🎁 Total Offers: <b>{{ total_offers }}</b></p>
<p class="stat">📢 Total Ads: <b>{{ total_ads }}</b></p>

<p>🔐 Admin ID: {{ admin_id }}</p>

<a href="/users">👥 User Management</a><br><br>
<a href="/logout">🚪 Logout</a>
</div>


<div class="box">
<h2>🎁 Affiliate Offer</h2>

<form method="POST" action="/add-offer">
<input name="name" placeholder="Offer Name" required>
<textarea name="description" placeholder="Offer Description"></textarea>
<input name="link" placeholder="Referral Link" required>
<button type="submit">➕ Add Offer</button>
</form>
</div>


<div class="box">
<h2>📢 Advertisement</h2>

<form method="POST" action="/add-ad">
<input name="name" placeholder="Ad Name" required>
<input name="link" placeholder="Direct Link" required>
<button type="submit">➕ Add Advertisement</button>
</form>
</div>


<div class="box">
<h2>🌐 Social Media Links</h2>

<form method="POST" action="/save-social">

<input name="facebook" value="{{ social[0] }}" placeholder="Facebook Link">

<input name="youtube" value="{{ social[1] }}" placeholder="YouTube Link">

<input name="telegram" value="{{ social[2] }}" placeholder="Telegram Channel Link">

<input name="whatsapp" value="{{ social[3] }}" placeholder="WhatsApp Link">

<button type="submit">💾 Save Social Links</button>

</form>
</div>


<div class="box">
<h2>📋 Current Offers</h2>

{% for offer in offers %}
<div class="item">
<b>{{ offer[1] }}</b>
<p>{{ offer[2] }}</p>
<a href="{{ offer[3] }}" target="_blank">🔗 Referral Link</a>
</div>
{% endfor %}

</div>


<div class="box">
<h2>📋 Current Ads</h2>

{% for ad in ads %}
<div class="item">
<b>{{ ad[1] }}</b>
<p>
<a href="{{ ad[2] }}" target="_blank">🔗 Direct Link</a>
</p>
</div>
{% endfor %}

</div>

</div>
</body>
</html>
"""


USERS_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EarnMate Users</title>
<style>
body{font-family:Arial;background:#f5f5f5;padding:15px}
.container{max-width:1000px;margin:auto}
.box{background:white;padding:15px;margin-bottom:12px;border-radius:12px}
</style>
</head>
<body>

<div class="container">

<h2>👥 User Management</h2>

<a href="/admin">⬅️ Back to Admin</a>

{% for user in users %}

<div class="box">
<b>👤 {{ user[3] }}</b>

<p>🆔 Telegram ID: {{ user[1] }}</p>

<p>📛 Username:
{{ "@" + user[2] if user[2] else "None" }}
</p>

<p>🔗 Referrals: {{ user[5] }}</p>

<p>💰 Balance: {{ user[6] }}</p>

<p>📅 Registered: {{ user[7] }}</p>
</div>

{% endfor %}

</div>
</body>
</html>
"""


@web_app.route("/")
def home():
    return "EarnMate AI Bot is running."


@web_app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        admin_id = request.form.get("admin_id", "").strip()
        password = request.form.get("password", "")

        if admin_id == ADMIN_ID and password == ADMIN_PASSWORD:

            session["admin_logged_in"] = True

            return redirect("/admin")

        return render_template_string(
            LOGIN_HTML,
            error="❌ Telegram ID অথবা Password ভুল।"
        )

    return render_template_string(
        LOGIN_HTML,
        error=None
    )


@web_app.route("/admin")
def admin():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT * FROM offers ORDER BY id DESC")
    offers = cur.fetchall()

    cur.execute("SELECT * FROM ads ORDER BY id DESC")
    ads = cur.fetchall()

    cur.execute("SELECT * FROM social_links WHERE id=1")
    social = cur.fetchone()

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(referrals),0) FROM users")
    total_referrals = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(balance),0) FROM users")
    total_balance = cur.fetchone()[0]

    total_offers = len(offers)
    total_ads = len(ads)

    conn.close()

    return render_template_string(
        PANEL_HTML,
        offers=offers,
        ads=ads,
        social=social,
        total_users=total_users,
        total_referrals=total_referrals,
        total_balance=total_balance,
        total_offers=total_offers,
        total_ads=total_ads,
        admin_id=ADMIN_ID
    )


@web_app.route("/users")
def users():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users ORDER BY id DESC"
    )

    users = cur.fetchall()

    conn.close()

    return render_template_string(
        USERS_HTML,
        users=users
    )


@web_app.route("/add-offer", methods=["POST"])
def add_offer():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO offers
        (name, description, link)
        VALUES (?, ?, ?)
        """,
        (
            request.form.get("name", ""),
            request.form.get("description", ""),
            request.form.get("link", "")
        )
    )

    conn.commit()
    conn.close()

    return redirect("/admin")


@web_app.route("/add-ad", methods=["POST"])
def add_ad():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO ads
        (name, link)
        VALUES (?, ?)
        """,
        (
            request.form.get("name", ""),
            request.form.get("link", "")
        )
    )

    conn.commit()
    conn.close()

    return redirect("/admin")


@web_app.route("/save-social", methods=["POST"])
def save_social():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE social_links
        SET facebook=?,
            youtube=?,
            telegram=?,
            whatsapp=?
        WHERE id=1
        """,
        (
            request.form.get("facebook", ""),
            request.form.get("youtube", ""),
            request.form.get("telegram", ""),
            request.form.get("whatsapp", "")
        )
    )

    conn.commit()
    conn.close()

    return redirect("/admin")


@web_app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


def run_web_server():

    port = int(os.environ.get("PORT", 10000))

    web_app.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False
    )


# =========================
# Telegram Bot
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    telegram_id = user.id
    username = user.username or ""
    first_name = user.first_name or ""

    # Referral information
    referred_by = None

    if context.args:

        try:
            ref_id = int(context.args[0])

            if ref_id != telegram_id:
                referred_by = ref_id

        except ValueError:
            pass

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM users WHERE telegram_id=?",
        (telegram_id,)
    )

    existing_user = cur.fetchone()

    if not existing_user:

        cur.execute(
            """
            INSERT INTO users
            (telegram_id, username, first_name, referred_by)
            VALUES (?, ?, ?, ?)
            """,
            (
                telegram_id,
                username,
                first_name,
                referred_by
            )
        )

        # Increase referral count
        if referred_by:

            cur.execute(
                """
                UPDATE users
                SET referrals = referrals + 1
                WHERE telegram_id = ?
                """,
                (referred_by,)
            )

    conn.commit()
    conn.close()


    keyboard = [

        [
            InlineKeyboardButton(
                "🤖 AI-কে প্রশ্ন করুন",
                callback_data="ai"
            )
        ],

        [
            InlineKeyboardButton(
                "💰 ইনকামের মাধ্যম",
                callback_data="income"
            )
        ],

        [
            InlineKeyboardButton(
                "🎁 Affiliate Offers",
                callback_data="offers"
            )
        ],

        [
            InlineKeyboardButton(
                "📢 Ads / Direct Link",
                callback_data="ads"
            )
        ],

        [
            InlineKeyboardButton(
                "🔗 আমার Referral Link",
                callback_data="referral"
            )
        ],

    ]


    await update.message.reply_text(

        "👋 স্বাগতম EarnMate AI Bot-এ!\n\n"

        "অনলাইন ইনকাম সম্পর্কে জানতে নিচের অপশন নির্বাচন করুন।",

        reply_markup=InlineKeyboardMarkup(keyboard)

    )


async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    bot_username = context.bot.username

    referral_link = (
        f"https://t.me/{bot_username}?start={user.id}"
    )

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT referrals FROM users WHERE telegram_id=?",
        (user.id,)
    )

    row = cur.fetchone()

    referral_count = row[0] if row else 0

    conn.close()


    await update.callback_query.message.reply_text(

        "🔗 আপনার Referral Link:\n\n"

        f"{referral_link}\n\n"

        f"👥 আপনার Referral: {referral_count} জন\n\n"

        "এই লিংক শেয়ার করে নতুন User আনতে পারবেন।"

    )


async def income(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "💰 অনলাইনে ইনকামের কিছু মাধ্যম:\n\n"

        "1️⃣ Freelancing\n"
        "2️⃣ Affiliate Marketing\n"
        "3️⃣ Micro Tasks\n"
        "4️⃣ Content Creation\n"
        "5️⃣ Digital Products\n\n"

        "⚠️ কোনো মাধ্যমেই আয়ের নিশ্চয়তা নেই।"

    )


async def offers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT name, description, link FROM offers ORDER BY id DESC"
    )

    offers = cur.fetchall()

    conn.close()


    if not offers:

        await update.message.reply_text(
            "🎁 বর্তমানে কোনো Affiliate Offer নেই।"
        )

        return


    text = "🎁 Affiliate Offers\n\n"

    for name, description, link in offers:

        text += (
            f"📌 {name}\n"
            f"{description}\n"
            f"🔗 {link}\n\n"
        )


    await update.message.reply_text(text)


async def ads_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT name, link FROM ads ORDER BY id DESC"
    )

    ads = cur.fetchall()

    conn.close()


    if not ads:

        await update.message.reply_text(
            "📢 বর্তমানে কোনো Advertisement নেই।"
        )

        return


    text = "📢 Advertisements\n\n"

    for name, link in ads:

        text += (
            f"📌 {name}\n"
            f"🔗 {link}\n\n"
        )


    await update.message.reply_text(text)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()


    if query.data == "ai":

        await query.message.reply_text(
            "🤖 আপনার প্রশ্নটি লিখুন।"
        )


    elif query.data == "income":

        await query.message.reply_text(
            "💰 Freelancing\n"
            "💰 Affiliate Marketing\n"
            "💰 Micro Tasks\n"
            "💰 Content Creation\n"
            "💰 Digital Products\n\n"
            "⚠️ আয়ের কোনো নিশ্চয়তা নেই।"
        )


    elif query.data == "offers":

        await offers_command(update, context)


    elif query.data == "ads":

        await ads_command(update, context)


    elif query.data == "referral":

        await referral(update, context)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 আপনার প্রশ্ন পেয়েছি।\n\n"
        "AI সিস্টেম পরের ধাপে যুক্ত করা হবে।"
    )


# =========================
# Main
# =========================

def main():

    if not BOT_TOKEN:

        raise ValueError(
            "BOT_TOKEN সেট করা হয়নি।"
        )


    threading.Thread(
        target=run_web_server,
        daemon=True
    ).start()


    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )


    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("income", income)
    )

    app.add_handler(
        CommandHandler("offers", offers_command)
    )

    app.add_handler(
        CommandHandler("ads", ads_command)
    )

    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler
        )
    )


    print(
        "EarnMate AI Bot + Admin Panel is running..."
    )


    app.run_polling()


if __name__ == "__main__":

    main()
