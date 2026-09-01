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

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SECRET_KEY = os.getenv(
    "ADMIN_SECRET_KEY",
    "please-change-this-secret"
)

DB = "earnmate.db"

REFERRAL_BONUS = 100
MIN_WITHDRAW = 5000
MAX_WITHDRAW = 25000


# =========================================================
# DATABASE
# =========================================================

def connect_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            referred_by INTEGER,
            referrals INTEGER DEFAULT 0,
            coins INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            coins INTEGER NOT NULL,
            method TEXT NOT NULL,
            payment_number TEXT NOT NULL,
            comment TEXT DEFAULT '',
            payment_amount REAL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# FLASK ADMIN PANEL
# =========================================================

web_app = Flask(__name__)
web_app.secret_key = SECRET_KEY


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
    box-shadow:0 3px 15px #ccc;
}

input,button{
    width:100%;
    padding:13px;
    margin:7px 0;
    box-sizing:border-box;
}

button{
    cursor:pointer;
}
</style>
</head>

<body>

<div class="box">

<h2>👑 EarnMate Admin Login</h2>

{% if error %}
<p style="color:red">{{ error }}</p>
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
    box-shadow:0 2px 10px #ddd;
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

.paid{
    color:green;
}

.pending{
    color:#d97706;
}

.rejected{
    color:red;
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
💳 Payment Method:
<b>{{ w["method"] }}</b>
</p>

<p>
📱 Payment Number:
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

<hr>

<form
method="POST"
action="/approve/{{ w['id'] }}"
>

<input
name="amount"
type="number"
step="0.01"
min="0"
placeholder="Payment Amount (Admin Only)"
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

{% elif w["status"] == "Paid" %}

<p class="paid">
✅ Payment:
<b>{{ w["payment_amount"] }}</b>
</p>

{% elif w["status"] == "Rejected" %}

<p class="rejected">
❌ Request Rejected
</p>

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

<p>🪙 Minimum: <b>5,000 Coins</b></p>

<p>🪙 Maximum: <b>25,000 Coins</b></p>

<p>
💰 User-এর কাছে কোনো টাকা/BDT amount দেখানো হবে না।
</p>

<p>
💳 Admin নিজে Payment Amount লিখবে।
</p>

<p>
❌ Reject করলে কাটা Coins User-এর Balance-এ ফেরত যাবে।
</p>

</div>


</div>

</body>
</html>
"""


# =========================================================
# ADMIN ROUTES
# =========================================================

@web_app.route("/")
def home():

    return "EarnMate AI Bot is running."


@web_app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        admin_id = request.form.get(
            "admin_id",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            admin_id == str(ADMIN_ID)
            and password == str(ADMIN_PASSWORD)
        ):

            session["admin_logged_in"] = True

            return redirect("/admin")

        return render_template_string(
            LOGIN_HTML,
            error="❌ Admin ID অথবা Password ভুল।"
        )

    return render_template_string(
        LOGIN_HTML,
        error=None
    )


@web_app.route("/admin")
def admin():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = connect_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )

    users = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(referrals),0) FROM users"
    )

    referrals = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(coins),0) FROM users"
    )

    coins = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM withdrawals"
    )

    withdrawal_count = cur.fetchone()[0]

    cur.execute("""
        SELECT *
        FROM withdrawals
        ORDER BY id DESC
    """)

    withdrawals = cur.fetchall()

    conn.close()

    return render_template_string(
        PANEL_HTML,
        users=users,
        referrals=referrals,
        coins=coins,
        withdrawal_count=withdrawal_count,
        withdrawals=withdrawals,
        admin_id=ADMIN_ID
    )


@web_app.route(
    "/approve/<int:request_id>",
    methods=["POST"]
)
def approve(request_id):

    if not session.get("admin_logged_in"):
        return redirect("/login")

    amount_text = request.form.get(
        "amount",
        ""
    ).strip()

    try:
        payment_amount = float(amount_text)

        if payment_amount < 0:
            raise ValueError

    except ValueError:
        return redirect("/admin")


    conn = connect_db()
    cur = conn.cursor()

    # শুধু Pending request-ই Paid করা যাবে
    cur.execute("""
        UPDATE withdrawals

        SET
            payment_amount=?,
            status='Paid'

        WHERE
            id=?
            AND status='Pending'
    """, (
        payment_amount,
        request_id
    ))

    conn.commit()
    conn.close()

    return redirect("/admin")


@web_app.route(
    "/reject/<int:request_id>",
    methods=["POST"]
)
def reject(request_id):

    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = connect_db()
    cur = conn.cursor()

    # Pending request-এর তথ্য নেওয়া
    cur.execute("""
        SELECT
            telegram_id,
            coins

        FROM withdrawals

        WHERE
            id=?
            AND status='Pending'
    """, (
        request_id,
    ))

    row = cur.fetchone()

    if row:

        # কেটে রাখা Coins ফেরত দেওয়া
        cur.execute("""
            UPDATE users

            SET coins = coins + ?

            WHERE telegram_id=?
        """, (
            row["coins"],
            row["telegram_id"]
        ))

        # Request Reject
        cur.execute("""
            UPDATE withdrawals

            SET status='Rejected'

            WHERE
                id=?
                AND status='Pending'
        """, (
            request_id,
        ))

        conn.commit()

    conn.close()

    return redirect("/admin")


@web_app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


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
    )


# =========================================================
# TELEGRAM BOT
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM users
        WHERE telegram_id=?
    """, (
        user.id,
    ))

    existing = cur.fetchone()


    # নতুন User
    if not existing:

        referrer = None

        # Referral link থেকে ID
        if context.args:

            try:

                ref_id = int(
                    context.args[0]
                )

                # Self referral বন্ধ
                if ref_id != user.id:

                    cur.execute("""
                        SELECT telegram_id
                        FROM users
                        WHERE telegram_id=?
                    """, (
                        ref_id,
                    ))

                    ref_user = cur.fetchone()

                    if ref_user:
                        referrer = ref_id

            except (ValueError, TypeError):
                pass


        # User create
        cur.execute("""
            INSERT INTO users
            (
                telegram_id,
                username,
                first_name,
                referred_by
            )

            VALUES (?, ?, ?, ?)
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            referrer
        ))


        # Valid referral হলে bonus
        if referrer:

            cur.execute("""
                UPDATE users

                SET
                    referrals = referrals + 1,
                    coins = coins + ?

                WHERE telegram_id=?
            """, (
                REFERRAL_BONUS,
                referrer
            ))


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
                "🪙 আমার Coins",
                callback_data="coins"
            )
        ],

        [
            InlineKeyboardButton(
                "🔗 Referral Link",
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
        "নিচের অপশন নির্বাচন করুন।",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


# =========================================================
# COINS
# =========================================================

async def show_coins(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            coins,
            referrals

        FROM users

        WHERE telegram_id=?
    """, (
        user.id,
    ))

    row = cur.fetchone()

    conn.close()

    if not row:
        return

    await update.callback_query.message.reply_text(

        f"🪙 আপনার Coins: {row['coins']}\n\n"
        f"👥 আপনার Referral: "
        f"{row['referrals']} জন\n\n"
        f"🎁 প্রতি সফল Referral = "
        f"{REFERRAL_BONUS} Coins"

    )


# =========================================================
# REFERRAL
# =========================================================

async def show_referral(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    bot_username = context.bot.username

    referral_link = (
        f"https://t.me/"
        f"{bot_username}"
        f"?start={user.id}"
    )


    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            referrals,
            coins

        FROM users

        WHERE telegram_id=?
    """, (
        user.id,
    ))

    row = cur.fetchone()

    conn.close()

    referrals = (
        row["referrals"]
        if row
        else 0
    )

    coins = (
        row["coins"]
        if row
        else 0
    )


    await update.callback_query.message.reply_text(

        "🔗 আপনার Referral Link:\n\n"

        f"{referral_link}\n\n"

        f"👥 আপনার Referral: "
        f"{referrals} জন\n\n"

        f"🪙 আপনার Coins: "
        f"{coins}\n\n"

        f"🎁 প্রতি সফল Referral = "
        f"{REFERRAL_BONUS} Coins"

    )


# =========================================================
# WITHDRAW START
# =========================================================

async def withdraw(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = [

        [
            InlineKeyboardButton(
                "💳 bKash",
                callback_data="method_bkash"
            ),

            InlineKeyboardButton(
                "💳 Nagad",
                callback_data="method_nagad"
            )
        ],

        [
            InlineKeyboardButton(
                "💳 Rocket",
                callback_data="method_rocket"
            )
        ]

    ]


    await update.callback_query.message.reply_text(

        "💳 Withdrawal Request\n\n"

        "প্রথমে Payment Method নির্বাচন করুন:",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


# =========================================================
# PAYMENT METHOD
# =========================================================

async def choose_method(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    method = query.data.replace(
        "method_",
        ""
    )


    context.user_data[
        "withdraw_method"
    ] = method

    context.user_data[
        "withdraw_step"
    ] = "amount"


    await query.message.reply_text(

        "🪙 Amount (Coins)\n\n"

        "কত Coins উত্তোলন করতে চান "
        "সেটি লিখুন।"

    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()


    if query.data == "ai":

        await query.message.reply_text(
            "🤖 আপনার প্রশ্নটি লিখুন।"
        )


    elif query.data == "income":

        await query.message.reply_text(

            "💰 ইনকামের মাধ্যম:\n\n"

            "1️⃣ Freelancing\n"
            "2️⃣ Affiliate Marketing\n"
            "3️⃣ Micro Tasks\n"
            "4️⃣ Content Creation\n"
            "5️⃣ Digital Products"

        )


    elif query.data == "coins":

        await show_coins(
            update,
            context
        )


    elif query.data == "referral":

        await show_referral(
            update,
            context
        )


    elif query.data == "withdraw":

        await withdraw(
            update,
            context
        )


    elif query.data.startswith(
        "method_"
    ):

        await choose_method(
            update,
            context
        )


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()

    step = context.user_data.get(
        "withdraw_step"
    )


    # =====================================================
    # AMOUNT
    # =====================================================

    if step == "amount":

        if not text.isdigit():

            await update.message.reply_text(
                "❌ শুধু Coins-এর সংখ্যা লিখুন।"
            )

            return


        amount = int(text)


        if amount < MIN_WITHDRAW:

            await update.message.reply_text(

                "❌ 5,000 Coins-এর নিচে "
                "উত্তোলন করা যাবে না।"

            )

            return


        if amount > MAX_WITHDRAW:

            await update.message.reply_text(

                "❌ একসাথে সর্বোচ্চ "
                "25,000 Coins উত্তোলন করা যাবে।"

            )

            return


        user = update.effective_user

        conn = connect_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT coins
            FROM users
            WHERE telegram_id=?
        """, (
            user.id,
        ))

        row = cur.fetchone()

        conn.close()


        if not row:

            context.user_data.clear()

            await update.message.reply_text(
                "❌ User account পাওয়া যায়নি।"
            )

            return


        balance = row["coins"]


        if amount > balance:

            await update.message.reply_text(

                f"❌ আপনার কাছে পর্যাপ্ত Coins নেই।\n\n"
                f"🪙 আপনার Balance: "
                f"{balance} Coins"

            )

            return


        context.user_data[
            "withdraw_amount"
        ] = amount

        context.user_data[
            "withdraw_step"
        ] = "number"


        await update.message.reply_text(

            "📱 Payment Number\n\n"

            "আপনার bKash / Nagad / Rocket "
            "নম্বর লিখুন।"

        )

        return


    # =====================================================
    # PAYMENT NUMBER
    # =====================================================

    if step == "number":

        number = (
            text
            .replace(" ", "")
            .replace("-", "")
        )


        if (
            not number.isdigit()
            or len(number) != 11
        ):

            await update.message.reply_text(

                "❌ সঠিক ১১ সংখ্যার "
                "Payment Number দিন।"

            )

            return


        context.user_data[
            "payment_number"
     
