import os
import sqlite3
import threading

from flask import Flask, request, redirect, session, render_template_string

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# ==============================
# SETTINGS
# ==============================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

SECRET_KEY = os.getenv(
    "ADMIN_SECRET_KEY",
    "change-this-secret"
)

DATABASE = "earnmate.db"

REFERRAL_BONUS = 100

MIN_WITHDRAW = 5000
MAX_WITHDRAW = 25000


# ==============================
# DATABASE
# ==============================

def connect_db():

    conn = sqlite3.connect(
        DATABASE,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_database():

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (

            telegram_id INTEGER PRIMARY KEY,

            username TEXT DEFAULT '',

            first_name TEXT DEFAULT '',

            referred_by INTEGER,

            referrals INTEGER DEFAULT 0,

            coins INTEGER DEFAULT 0

        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            telegram_id INTEGER NOT NULL,

            coins INTEGER NOT NULL,

            method TEXT NOT NULL,

            payment_number TEXT NOT NULL,

            comment TEXT DEFAULT '',

            payment_amount REAL,

            status TEXT DEFAULT 'Pending',

            created_at TIMESTAMP
            DEFAULT CURRENT_TIMESTAMP

        )
    """)

    conn.commit()
    conn.close()


init_database()


# ==============================
# FLASK SERVER
# ==============================

web_app = Flask(__name__)

web_app.secret_key = SECRET_KEY


@web_app.route("/")
def home():

    return "EarnMate AI Bot is running."


def run_web_server():

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    web_app.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False
)# ==============================
# ADMIN LOGIN PAGE
# ==============================

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>

<meta name="viewport"
      content="width=device-width,initial-scale=1">

<title>EarnMate Admin Login</title>

<style>

body{
    font-family:Arial;
    background:#f2f2f2;
    padding:20px;
}

.box{
    max-width:400px;
    margin:60px auto;
    background:white;
    padding:25px;
    border-radius:15px;
}

input,button{
    width:100%;
    padding:13px;
    margin:8px 0;
    box-sizing:border-box;
}

button{
    cursor:pointer;
}

.error{
    color:red;
}

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

<button type="submit">
🔐 Login
</button>

</form>

</div>

</body>
</html>
"""


# ==============================
# ADMIN PANEL PAGE
# ==============================

PANEL_HTML = """
<!DOCTYPE html>
<html>

<head>

<meta name="viewport"
      content="width=device-width,initial-scale=1">

<title>EarnMate Admin Panel</title>

<style>

body{
    font-family:Arial;
    background:#f5f5f5;
    padding:15px;
}

.container{
    max-width:950px;
    margin:auto;
}

.box{
    background:white;
    padding:20px;
    margin-bottom:18px;
    border-radius:15px;
}

.request{
    border:1px solid #ddd;
    padding:15px;
    margin:12px 0;
    border-radius:12px;
}

input,button{
    width:100%;
    padding:12px;
    margin:6px 0;
    box-sizing:border-box;
}

button{
    cursor:pointer;
}

</style>

</head>

<body>

<div class="container">

<h1>👑 EarnMate AI Admin Panel</h1>


<div class="box">

<h2>📊 Dashboard</h2>

<p>
👥 Total Users:
<b>{{ users }}</b>
</p>

<p>
🔗 Total Referrals:
<b>{{ referrals }}</b>
</p>

<p>
🪙 Total Coins:
<b>{{ coins }}</b>
</p>

<p>
💳 Withdrawal Requests:
<b>{{ withdrawal_count }}</b>
</p>

<p>
🔐 Admin ID:
<b>{{ admin_id }}</b>
</p>

<a href="/logout">
🚪 Logout
</a>

</div>


<div class="box">

<h2>💳 Withdrawal Requests</h2>

{% if withdrawals %}

{% for w in withdrawals %}

<div class="request">

<p>
<b>Request #{{ w["id"] }}</b>
</p>

<p>
👤 User ID:
<b>{{ w["telegram_id"] }}</b>
</p>

<p>
🪙 Coins:
<b>{{ w["coins"] }}</b>
</p>

<p>
💳 Method:
<b>{{ w["method"] }}</b>
</p>

<p>
📱 Number:
<b>{{ w["payment_number"] }}</b>
</p>

<p>
📝 Comment:
{{ w["comment"] }}
</p>

<p>
📌 Status:
<b>{{ w["status"] }}</b>
</p>

{% if w["status"] == "Pending" %}

<form
method="POST"
action="/approve/{{ w['id'] }}"
>

<input
name="amount"
type="number"
step="0.01"
min="0"
placeholder="Payment Amount"
required
>

<button type="submit">
✅ Payment Complete
</button>

</form>


<form
method="POST"
action="/reject/{{ w['id'] }}"
>

<button type="submit">
❌ Reject Request
</button>

</form>

{% endif %}

</div>

{% endfor %}

{% else %}

<p>
কোনো Withdrawal Request নেই।
</p>

{% endif %}

</div>


<div class="box">

<h2>ℹ️ Withdrawal Rules</h2>

<p>
🪙 Minimum: <b>5,000 Coins</b>
</p>

<p>
🪙 Maximum: <b>25,000 Coins</b>
</p>

<p>
💰 User-এর কাছে টাকা দেখানো হবে না।
</p>

<p>
💳 Payment Amount Admin নিজে নির্ধারণ করবে।
</p>

</div>

</div>

</body>
</html>
"""
