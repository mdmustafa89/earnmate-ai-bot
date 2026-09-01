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
# ==============================
# APPROVE WITHDRAWAL
# ==============================

@web_app.route("/approve/<int:withdrawal_id>", methods=["POST"])
def approve_withdrawal(withdrawal_id):

    if not session.get("admin_logged_in"):
        return redirect("/login")

    amount = request.form.get("amount", "").strip()

    if not amount:
        return redirect("/admin")

    try:
        amount = float(amount)
    except ValueError:
        return redirect("/admin")

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE withdrawals
        SET payment_amount = ?,
            status = 'Paid'
        WHERE id = ?
          AND status = 'Pending'
        """,
        (amount, withdrawal_id)
    )

    conn.commit()
    conn.close()

    return redirect("/admin")


# ==============================
# REJECT WITHDRAWAL
# ==============================

@web_app.route("/reject/<int:withdrawal_id>", methods=["POST"])
def reject_withdrawal(withdrawal_id):

    if not session.get("admin_logged_in"):
        return redirect("/login")

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT telegram_id, coins
        FROM withdrawals
        WHERE id = ?
          AND status = 'Pending'
        """,
        (withdrawal_id,)
    )

    withdrawal = cursor.fetchone()

    if withdrawal:

        cursor.execute(
            """
            UPDATE users
            SET coins = coins + ?
            WHERE telegram_id = ?
            """,
            (
                withdrawal["coins"],
                withdrawal["telegram_id"]
            )
        )

        cursor.execute(
            """
            UPDATE withdrawals
            SET status = 'Rejected'
            WHERE id = ?
            """,
            (withdrawal_id,)
        )

        conn.commit()

    conn.close()

    return redirect("/admin")
    # ==============================
# TELEGRAM USER FUNCTIONS
# ==============================

def get_user(telegram_id):

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )

    user = cursor.fetchone()

    conn.close()

    return user


def create_user(update, referred_by=None):

    user = update.effective_user

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT telegram_id FROM users WHERE telegram_id = ?",
        (user.id,)
    )

    exists = cursor.fetchone()

    if not exists:

        valid_referrer = None

        if referred_by and referred_by != user.id:

            cursor.execute(
                "SELECT telegram_id FROM users WHERE telegram_id = ?",
                (referred_by,)
            )

            referrer = cursor.fetchone()

            if referrer:
                valid_referrer = referred_by

        cursor.execute(
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
                user.id,
                user.username or "",
                user.first_name or "",
                valid_referrer
            )
        )

        if valid_referrer:

            cursor.execute(
                """
                UPDATE users
                SET referrals = referrals + 1,
                    coins = coins + ?
                WHERE telegram_id = ?
                """,
                (
                    REFERRAL_BONUS,
                    valid_referrer
                )
            )

    else:

        cursor.execute(
            """
            UPDATE users
            SET username = ?,
                first_name = ?
            WHERE telegram_id = ?
            """,
            (
                user.username or "",
                user.first_name or "",
                user.id
            )
        )

    conn.commit()
    conn.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    referred_by = None

    if context.args:

        try:
            referred_by = int(context.args[0])
        except ValueError:
            referred_by = None

    create_user(
        update,
        referred_by
    )

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
        "🪙 Referral করে Coins সংগ্রহ করুন।\n"
        "প্রতি সফল Referral = 100 Coins\n\n"
        "নিচের মেনু থেকে একটি অপশন নির্বাচন করুন।",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
        )# ==============================
# COINS / REFERRAL / WITHDRAW
# ==============================

async def show_coins(update, context):

    query = update.callback_query
    user_id = query.from_user.id

    user = get_user(user_id)

    coins = user["coins"] if user else 0
    referrals = user["referrals"] if user else 0

    await query.message.reply_text(
        f"🪙 আপনার Coins: {coins}\n\n"
        f"👥 আপনার Referral: {referrals} জন\n\n"
        "প্রতি সফল Referral = 100 Coins"
    )


async def show_referral(update, context):

    query = update.callback_query
    user_id = query.from_user.id

    bot = await context.bot.get_me()

    referral_link = (
        f"https://t.me/{bot.username}"
        f"?start={user_id}"
    )

    user = get_user(user_id)

    referrals = user["referrals"] if user else 0

    await query.message.reply_text(
        "🔗 আপনার Referral Link:\n\n"
        f"{referral_link}\n\n"
        f"👥 আপনার Referral: {referrals} জন\n\n"
        "এই লিংক শেয়ার করে নতুন User আনতে পারবেন।"
    )


async def start_withdraw(update, context):

    query = update.callback_query

    await query.answer()

    keyboard = [

        [
            InlineKeyboardButton(
                "💳 bKash",
                callback_data="withdraw_bkash"
            )
        ],

        [
            InlineKeyboardButton(
                "💳 Nagad",
                callback_data="withdraw_nagad"
            )
        ],

        [
            InlineKeyboardButton(
                "💳 Rocket",
                callback_data="withdraw_rocket"
            )
        ]

    ]

    await query.message.reply_text(
        "💳 Withdrawal\n\n"
        "আপনার Payment Method নির্বাচন করুন:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def choose_withdraw_method(update, context):

    query = update.callback_query

    await query.answer()

    method = query.data.replace(
        "withdraw_",
        ""
    )

    context.user_data["withdraw_method"] = method

    context.user_data["withdraw_step"] = "coins"

    await query.message.reply_text(
        "🪙 কত Coins উত্তোলন করতে চান?\n\n"
        "সর্বনিম্ন 5,000 Coins\n"
        "সর্বোচ্চ 25,000 Coins\n\n"
        "শুধু Coins-এর সংখ্যা লিখুন।"
    )# ==============================
# WITHDRAW FORM
# ==============================

async def process_withdraw(update, context):

    if context.user_data.get("withdraw_step") != "coins":
        return

    text = update.message.text.strip()

    try:
        coins = int(text)
    except ValueError:
        await update.message.reply_text(
            "❌ শুধু Coins-এর সংখ্যা লিখুন।\n\n"
            "উদাহরণ: 5000"
        )
        return

    if coins < MIN_WITHDRAW:
        await update.message.reply_text(
            f"❌ 5,000 Coins-এর নিচে উত্তোলন করা যাবে না।\n\n"
            f"আপনি লিখেছেন: {coins} Coins\n"
            f"আরও {MIN_WITHDRAW - coins} Coins লাগবে।"
        )
        return

    if coins > MAX_WITHDRAW:
        await update.message.reply_text(
            "❌ একবারে সর্বোচ্চ 25,000 Coins "
            "উত্তোলন করা যাবে।"
        )
        return

    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user or user["coins"] < coins:
        await update.message.reply_text(
            f"❌ আপনার পর্যাপ্ত Coins নেই।\n\n"
            f"🪙 আপনার Coins: "
            f"{user['coins'] if user else 0}\n"
            f"🪙 আপনি চেয়েছেন: {coins}"
        )
        return

    context.user_data["withdraw_coins"] = coins
    context.user_data["withdraw_step"] = "number"

    method = context.user_data.get(
        "withdraw_method",
        ""
    )

    method_name = {
        "bkash": "bKash",
        "nagad": "Nagad",
        "rocket": "Rocket"
    }.get(method, method)

    await update.message.reply_text(
        f"💳 Payment Method: {method_name}\n\n"
        "📱 আপনার bKash/Nagad/Rocket নম্বর লিখুন:"
    )


async def process_withdraw_number(update, context):

    if context.user_data.get("withdraw_step") != "number":
        return

    number = update.message.text.strip()

    if not number.isdigit():
        await update.message.reply_text(
            "❌ সঠিক মোবাইল নম্বর লিখুন।"
        )
        return

    if len(number) < 10 or len(number) > 15:
        await update.message.reply_text(
            "❌ সঠিক মোবাইল নম্বর লিখুন।"
        )
        return

    context.user_data["withdraw_number"] = number
    context.user_data["withdraw_step"] = "comment"

    await update.message.reply_text(
        "📝 Comment লিখুন:\n\n"
        "যেমন: আমার পেমেন্টটি দ্রুত দেওয়ার অনুরোধ করছি।"
    )


async def process_withdraw_comment(update, context):

    if context.user_data.get("withdraw_step") != "comment":
        return

    comment = update.message.text.strip()

    if not comment:
        comment = "No comment"

    context.user_data["withdraw_comment"] = comment

    coins = context.user_data.get(
        "withdraw_coins"
    )

    method = context.user_data.get(
        "withdraw_method"
    )

    number = context.user_data.get(
        "withdraw_number"
    )

    method_name = {
        "bkash": "bKash",
        "nagad": "Nagad",
        "rocket": "Rocket"
    }.get(method, method)

    keyboard = [
        [
            InlineKeyboardButton(
                "📤 Request পাঠান",
                callback_data="confirm_withdraw"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="cancel_withdraw"
            )
        ]
    ]

    await update.message.reply_text(
        "🔎 Withdrawal Request\n\n"
        f"🪙 Coins: {coins}\n"
        f"💳 Method: {method_name}\n"
        f"📱 Number: {number}\n"
        f"📝 Comment: {comment}\n\n"
        "সব তথ্য ঠিক থাকলে Request পাঠান।",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )# ==============================
# CONFIRM WITHDRAWAL
# ==============================

async def confirm_withdraw(update, context):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    coins = context.user_data.get("withdraw_coins")
    method = context.user_data.get("withdraw_method")
    number = context.user_data.get("withdraw_number")
    comment = context.user_data.get(
        "withdraw_comment",
        ""
    )

    if not coins or not method or not number:
        await query.message.reply_text(
            "❌ Withdrawal তথ্য পাওয়া যায়নি। "
            "আবার চেষ্টা করুন।"
        )
        return

    conn = connect_db()
    cursor = conn.cursor()

    # আবার Balance যাচাই
    cursor.execute(
        "SELECT coins FROM users WHERE telegram_id = ?",
        (user_id,)
    )

    user = cursor.fetchone()

    if not user or user["coins"] < coins:
        conn.close()

        await query.message.reply_text(
            "❌ আপনার পর্যাপ্ত Coins নেই।"
        )
        return

    # Request তৈরি + Coins একসাথে কেটে নেওয়া
    cursor.execute(
        """
        UPDATE users
        SET coins = coins - ?
        WHERE telegram_id = ?
          AND coins >= ?
        """,
        (coins, user_id, coins)
    )

    if cursor.rowcount != 1:
        conn.rollback()
        conn.close()

        await query.message.reply_text(
            "❌ Withdrawal Request তৈরি করা যায়নি।"
        )
        return

    cursor.execute(
        """
        INSERT INTO withdrawals
        (
            telegram_id,
            coins,
            method,
            payment_number,
            comment,
            status
        )
        VALUES (?, ?, ?, ?, ?, 'Pending')
        """,
        (
            user_id,
            coins,
            method,
            number,
            comment
        )
    )

    conn.commit()
    conn.close()

    # পুরোনো withdrawal data পরিষ্কার
    context.user_data.pop(
        "withdraw_coins",
        None
    )

    context.user_data.pop(
        "withdraw_method",
        None
    )

    context.user_data.pop(
        "withdraw_number",
        None
    )

    context.user_data.pop(
        "withdraw_comment",
        None
    )

    context.user_data.pop(
        "withdraw_step",
        None
    )

    await query.message.reply_text(
        "✅ Withdrawal Request পাঠানো হয়েছে!\n\n"
        f"🪙 Coins: {coins}\n"
        "📌 Status: Pending\n\n"
        "Admin আপনার Payment যাচাই করে "
        "পেমেন্ট করবেন।"
    )


# ==============================
# CANCEL WITHDRAWAL
# ==============================

async def cancel_withdraw(update, context):

    query = update.callback_query
    await query.answer()

    context.user_data.pop(
        "withdraw_coins",
        None
    )

    context.user_data.pop(
        "withdraw_method",
        None
    )

    context.user_data.pop(
        "withdraw_number",
        None
    )

    context.user_data.pop(
        "withdraw_comment",
        None
    )

    context.user_data.pop(
        "withdraw_step",
        None
    )

    await query.message.reply_text(
        "❌ Withdrawal Request বাতিল করা হয়েছে।"
    )
    # ==============================
# INCOME
# ==============================

async def income(update, context):

    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "💰 অনলাইনে ইনকামের কিছু মাধ্যম:\n\n"
        "1️⃣ Freelancing\n"
        "2️⃣ Affiliate Marketing\n"
        "3️⃣ Micro Tasks\n"
        "4️⃣ Content Creation\n"
        "5️⃣ Digital Products\n\n"
        "⚠️ কোনো মাধ্যমেই আয়ের নিশ্চয়তা নেই।"
    )


# ==============================
# AFFILIATE OFFERS
# ==============================

async def offers(update, context):

    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "🎁 Affiliate Offers\n\n"
        "Affiliate Offers সিস্টেম পরবর্তী ধাপে যুক্ত করা যাবে।"
    )


# ==============================
# ADS
# ==============================

async def ads(update, context):

    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "📢 Ads / Direct Link\n\n"
        "Advertisement সিস্টেম পরবর্তী ধাপে যুক্ত করা যাবে।"
    )


# ==============================
# BUTTON HANDLER
# ==============================

async def button_handler(update, context):

    query = update.callback_query

    if query.data == "coins":

        await show_coins(update, context)

    elif query.data == "referral":

        await show_referral(update, context)

    elif query.data == "withdraw":

        await start_withdraw(update, context)

    elif query.data in (
        "withdraw_bkash",
        "withdraw_nagad",
        "withdraw_rocket"
    ):

        await choose_withdraw_method(
            update,
            context
        )

    elif query.data == "confirm_withdraw":

        await confirm_withdraw(
            update,
            context
        )

    elif query.data == "cancel_withdraw":

        await cancel_withdraw(
            update,
            context
        )

    elif query.data == "income":

        await income(update, context)

    elif query.data == "offers":

        await offers(update, context)

    elif query.data == "ads":

        await ads(update, context)

    elif query.data == "ai":

        await query.answer()

        await query.message.reply_text(
            "🤖 আপনার প্রশ্নটি লিখুন।"
        )

    else:

        await query.answer()


# ==============================
# MESSAGE HANDLER
# ==============================

async def message_handler(update, context):

    step = context.user_data.get(
        "withdraw_step"
    )

    if step == "coins":

        await process_withdraw(
            update,
            context
        )

        return

    if step == "number":

        await process_withdraw_number(
            update,
            context
        )

        return

    if step == "comment":

        await process_withdraw_comment(
            update,
            context
        )

        return

    text = update.message.text

    await update.message.reply_text(
        "🤖 আপনার প্রশ্ন পেয়েছি।\n\n"
        f"প্রশ্ন: {text}\n\n"
        "AI সিস্টেম পরবর্তী ধাপে যুক্ত করা হবে।"
    )


# ==============================
# MAIN
# ==============================

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
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            button_handler
        )
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
