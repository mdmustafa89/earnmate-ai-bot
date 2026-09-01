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

REFERRAL_BONUS = 100
MIN_WITHDRAW = 5000


# ==================================================
# DATABASE
# ==================================================

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            referred_by INTEGER,
            referrals INTEGER DEFAULT 0,
            coins INTEGER DEFAULT 0,
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
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            coins INTEGER NOT NULL,
            method TEXT NOT NULL,
            payment_number TEXT NOT NULL,
            comment TEXT,
            payment_amount REAL DEFAULT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            paid_at TIMESTAMP
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


# ==================================================
# FLASK / ADMIN
# ==================================================

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

<input
name="admin_id"
placeholder="Telegram Admin ID"
required
>

<input
name="password"
type="password"
placeholder="Admin Password"
required
>

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

body{
font-family:Arial;
background:#f5f5f5;
padding:15px
}

.container{
max-width:950px;
margin:auto
}

.box{
background:white;
padding:20px;
margin-bottom:20px;
border-radius:15px
}

input,textarea,select,button{
width:100%;
padding:12px;
margin:7px 0;
box-sizing:border-box
}

button{
cursor:pointer
}

.stat{
font-size:18px;
margin:8px 0
}

.item{
border-top:1px solid #ddd;
padding:12px 0
}

.pending{
background:#fff3cd;
padding:15px;
border-radius:10px;
margin-bottom:15px
}

.paid{
background:#d1e7dd;
padding:15px;
border-radius:10px;
margin-bottom:15px
}

.rejected{
background:#f8d7da;
padding:15px;
border-radius:10px;
margin-bottom:15px
}

</style>

</head>

<body>

<div class="container">

<h1>👑 EarnMate AI Admin Panel</h1>


<div class="box">

<h2>📊 Dashboard</h2>

<p class="stat">
👥 Total Users:
<b>{{ total_users }}</b>
</p>

<p class="stat">
🔗 Total Referrals:
<b>{{ total_referrals }}</b>
</p>

<p class="stat">
🪙 Total Coins:
<b>{{ total_coins }}</b>
</p>

<p class="stat">
🎁 Total Offers:
<b>{{ total_offers }}</b>
</p>

<p class="stat">
📢 Total Ads:
<b>{{ total_ads }}</b>
</p>

<p class="stat">
💳 Withdrawal Requests:
<b>{{ total_withdrawals }}</b>
</p>

<p>
🔐 Admin ID: {{ admin_id }}
</p>

<a href="/users">👥 User Management</a>
<br><br>

<a href="/withdrawals">
💳 Withdrawal Requests
</a>

<br><br>

<a href="/logout">🚪 Logout</a>

</div>


<div class="box">

<h2>🎁 Affiliate Offer</h2>

<form method="POST" action="/add-offer">

<input
name="name"
placeholder="Offer Name"
required
>

<textarea
name="description"
placeholder="Offer Description"
></textarea>

<input
name="link"
placeholder="Referral Link"
required
>

<button type="submit">
➕ Add Offer
</button>

</form>

</div>


<div class="box">

<h2>📢 Advertisement</h2>

<form method="POST" action="/add-ad">

<input
name="name"
placeholder="Ad Name"
required
>

<input
name="link"
placeholder="Direct Link"
required
>

<button type="submit">
➕ Add Advertisement
</button>

</form>

</div>


<div class="box">

<h2>🌐 Social Media Links</h2>

<form method="POST" action="/save-social">

<input
name="facebook"
value="{{ social[0] }}"
placeholder="Facebook Link"
>

<input
name="youtube"
value="{{ social[1] }}"
placeholder="YouTube Link"
>

<input
name="telegram"
value="{{ social[2] }}"
placeholder="Telegram Channel Link"
>

<input
name="whatsapp"
value="{{ social[3] }}"
placeholder="WhatsApp Link"
>

<button type="submit">
💾 Save Social Links
</button>

</form>

</div>


<div class="box">

<h2>📋 Current Offers</h2>

{% for offer in offers %}

<div class="item">

<b>{{ offer[1] }}</b>

<p>{{ offer[2] }}</p>

<a
href="{{ offer[3] }}"
target="_blank"
>
🔗 Referral Link
</a>

</div>

{% endfor %}

</div>


<div class="box">

<h2>📋 Current Ads</h2>

{% for ad in ads %}

<div class="item">

<b>{{ ad[1] }}</b>

<p>

<a
href="{{ ad[2] }}"
target="_blank"
>
🔗 Direct Link
</a>

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

<title>Users</title>

<style>

body{
font-family:Arial;
background:#f5f5f5;
padding:15px
}

.container{
max-width:950px;
margin:auto
}

.box{
background:white;
padding:15px;
margin-bottom:12px;
border-radius:12px
}

</style>

</head>

<body>

<div class="container">

<h2>👥 User Management</h2>

<a href="/admin">⬅️ Back to Admin</a>

<br><br>

{% for user in users %}

<div class="box">

<b>👤 {{ user["first_name"] }}</b>

<p>
🆔 Telegram ID:
{{ user["telegram_id"] }}
</p>

<p>
📛 Username:
{{ "@" + user["username"] if user["username"] else "None" }}
</p>

<p>
🔗 Referrals:
{{ user["referrals"] }}
</p>

<p>
🪙 Coins:
<b>{{ user["coins"] }}</b>
</p>

<p>
📅 Registered:
{{ user["created_at"] }}
</p>

</div>

{% endfor %}

</div>

</body>
</html>
"""


WITHDRAWALS_HTML = """
<!DOCTYPE html>
<html>
<head>

<meta name="viewport" content="width=device-width,initial-scale=1">

<title>Withdrawal Requests</title>

<style>

body{
font-family:Arial;
background:#f5f5f5;
padding:15px
}

.container{
max-width:950px;
margin:auto
}

.box{
background:white;
padding:18px;
margin-bottom:15px;
border-radius:12px
}

.pending{
border-left:6px solid orange
}

.paid{
border-left:6px solid green
}

.rejected{
border-left:6px solid red
}

input,button{
width:100%;
padding:12px;
margin:7px 0;
box-sizing:border-box
}

</style>

</head>

<body>

<div class="container">

<h2>💳 Withdrawal Requests</h2>

<a href="/admin">⬅️ Back to Admin</a>

<br><br>

{% if not withdrawals %}

<div class="box">
কোনো Withdrawal Request নেই।
</div>

{% endif %}


{% for w in withdrawals %}

<div class="box {{ w['status']|lower }}">

<h3>
Request #{{ w["id"] }}
</h3>

<p>
👤 Telegram ID:
<b>{{ w["telegram_id"] }}</b>
</p>

<p>
🪙 Requested Coins:
<b>{{ w["coins"] }}</b>
</p>

<p>
💳 Method:
<b>{{ w["method"] }}</b>
</p>

<p>
📱 Payment Number:
<b>{{ w["payment_number"] }}</b>
</p>

<p>
📝 Comment:
{{ w["comment"] or "None" }}
</p>

<p>
📌 Status:
<b>{{ w["status"] }}</b>
</p>


{% if w["status"] == "Pending" %}

<form method="POST"
action="/approve-withdraw/{{ w['id'] }}">

<label>
💰 Payment Amount
</label>

<input
name="payment_amount"
type="number"
step="0.01"
min="0"
placeholder="Admin এখানে টাকার amount লিখবে"
required
>

<button type="submit">
✅ Payment করা হয়েছে / Approve
</button>

</form>


<form method="POST"
action="/reject-withdraw/{{ w['id'] }}">

<button type="submit">
❌ Reject Request
</button>

</form>

{% elif w["status"] == "Paid" %}

<p>
💰 Payment Amount:
<b>{{ w["payment_amount"] }}</b>
</p>

{% endif %}

</div>

{% endfor %}

</div>

</body>
</html>
"""


# ==================================================
# ADMIN ROUTES
# ==================================================

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

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM offers ORDER BY id DESC"
    )
    offers = cur.fetchall()

    cur.execute(
        "SELECT * FROM ads ORDER BY id DESC"
    )
    ads = cur.fetchall()

    cur.execute(
        "SELECT * FROM social_links WHERE id=1"
    )
    social = cur.fetchone()

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )
    total_users = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(referrals),0) FROM users"
    )
    total_referrals = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(coins),0) FROM users"
    )
    total_coins = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM withdrawals"
    )
    total_withdrawals = cur.fetchone()[0]

    conn.close()

    return render_template_string(
        PANEL_HTML,
        offers=offers,
        ads=ads,
        social=social,
        total_users=total_users,
        total_referrals=total_referrals,
        total_coins=total_coins,
        total_offers=len(offers),
        total_ads=len(ads),
        total_withdrawals=total_withdrawals,
        admin_id=ADMIN_ID
    )


@web_app.route("/users")
def users():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = db()
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


@web_app.route("/withdrawals")
def withdrawals():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM withdrawals
        ORDER BY
        CASE status
            WHEN 'Pending' THEN 0
            ELSE 1
        END,
        id DESC
    """)

    withdrawals = cur.fetchall()

    conn.close()

    return render_template_string(
        WITHDRAWALS_HTML,
        withdrawals=withdrawals
    )


@web_app.route(
    "/approve-withdraw/<int:withdrawal_id>",
    methods=["POST"]
)
def approve_withdraw(withdrawal_id):

    if not session.get("admin_logged_in"):
        return redirect("/login")

    try:
        payment_amount = float(
            request.form.get("payment_amount", "")
        )

        if payment_amount < 0:
            return redirect("/withdrawals")

    except ValueError:
        return redirect("/withdrawals")

    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM withdrawals
        WHERE id=?
        """,
        (withdrawal_id,)
    )

    withdrawal = cur.fetchone()

    if not withdrawal:
        conn.close()
        return redirect("/withdrawals")

    if withdrawal["status"] != "Pending":
        conn.close()
        return redirect("/withdrawals")

    cur.execute(
        """
        UPDATE withdrawals
        SET payment_amount=?,
            status='Paid',
            paid_at=CURRENT_TIMESTAMP
        WHERE id=?
        AND status='Pending'
        """,
        (
            payment_amount,
            withdrawal_id
        )
    )

    conn.commit()
    conn.close()

    return redirect("/withdrawals")


@web_app.route(
    "/reject-withdraw/<int:withdrawal_id>",
    methods=["POST"]
)
def reject_withdraw(withdrawal_id):

    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM withdrawals
        WHERE id=?
        """,
        (withdrawal_id,)
    )

    withdrawal = cur.fetchone()

    if not withdrawal:
        conn.close()
        return redirect("/withdrawals")

    if withdrawal["status"] != "Pending":
        conn.close()
        return redirect("/withdrawals")

    cur.execute(
        """
        UPDATE withdrawals
        SET status='Rejected'
        WHERE id=?
        AND status='Pending'
        """,
        (withdrawal_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/withdrawals")


@web_app.route("/add-offer", methods=["POST"])
def add_offer():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = db()
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

    conn = db()
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

    conn = db()
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


# ==================================================
# TELEGRAM BOT
# ==================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    telegram_id = user.id
    username = user.username or ""
    first_name = user.first_name or ""

    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM users
        WHERE telegram_id=?
        """,
        (telegram_id,)
    )

    existing_user = cur.fetchone()

    if not existing_user:

        referred_by = None

        if context.args:

            try:

                ref_id = int(context.args[0])

                # নিজের referral link ব্যবহার করলে referral হবে না
                if ref_id != telegram_id:

                    cur.execute(
                        """
                        SELECT telegram_id
                        FROM users
                        WHERE telegram_id=?
                        """,
                        (ref_id,)
                    )

                    referrer = cur.fetchone()

                    if referrer:
                        referred_by = ref_id

            except (ValueError, TypeError):
                pass


        cur.execute(
            """
            INSERT INTO users
            (
                telegram_id,
                username,
                first_name,
                referred_by,
                referrals,
                coins
            )
            VALUES (?, ?, ?, ?, 0, 0)
            """,
            (
                telegram_id,
                username,
                first_name,
                referred_by
            )
        )


        # সফল নতুন referral হলে 100 Coins
        if referred_by:

            cur.execute(
                """
                UPDATE users
                SET referrals = referrals + 1,
                    coins = coins + ?
                WHERE telegram_id=?
                """,
                (
                    REFERRAL_BONUS,
                    referred_by
                )
            )


    else:

        # Username/name update
        cur.execute(
            """
            UPDATE users
            SET username=?,
                first_name=?
            WHERE telegram_id=?
            """,
            (
                username,
                first_name,
                telegram_id
            )
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
                "🪙 আমার Coins",
                callback_data="coins"
            )
        ],

        [
            InlineKeyboardButton(
                "🔗 আমার Referral Link",
                callback_data="referral"
            )
        ],

        [
            InlineKeyboardButton(
                "💳 Withdraw",
                callback_data="withdraw"
            )
        ]

    ]


    await update.message.reply_text(

        "👋 স্বাগতম EarnMate AI Bot-এ!\n\n"
        "অনলাইন ইনকাম সম্পর্কে জানতে নিচের অপশন নির্বাচন করুন।",

        reply_ma
