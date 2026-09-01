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

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "earnmate-change-this")

DB = "earnmate.db"

REFERRAL_BONUS = 100
MIN_WITHDRAW = 5000


# =========================
# DATABASE
# =========================

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
            username TEXT,
            first_name TEXT,
            referred_by INTEGER,
            referrals INTEGER DEFAULT 0,
            coins INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            coins INTEGER,
            method TEXT,
            payment_number TEXT,
            comment TEXT,
            payment_amount REAL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================
# FLASK ADMIN PANEL
# =========================

web = Flask(__name__)
web.secret_key = SECRET_KEY


LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
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

{% if error %}
<p style="color:red">{{ error }}</p>
{% endif %}

</div>

</body>
</html>
"""


PANEL_PAGE = """
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
    max-width:900px;
    margin:auto;
}

.box{
    background:white;
    padding:20px;
    margin-bottom:15px;
    border-radius:15px;
}

input,button{
    width:100%;
    padding:12px;
    margin:6px 0;
    box-sizing:border-box;
}

.request{
    border:1px solid #ddd;
    padding:15px;
    margin:10px 0;
    border-radius:10px;
}

</style>

</head>

<body>

<div class="container">

<h1>👑 EarnMate AI Admin Panel</h1>

<div class="box">

<h2>📊 Dashboard</h2>

<p>👥 Total Users: <b>{{ users }}</b></p>

<p>🔗 Total Referrals: <b>{{ referrals }}</b></p>

<p>🪙 Total Coins: <b>{{ coins }}</b></p>

<p>💳 Withdrawal Requests:
<b>{{ withdrawal_count }}</b>
</p>

<p>🔐 Admin ID: {{ admin_id }}</p>

<a href="/logout">
🚪 Logout
</a>

</div>


<div class="box">

<h2>💳 Withdrawal Requests</h2>

{% for w in withdrawals %}

<div class="request">

<p>
<b>Request #{{ w["id"] }}</b>
</p>

<p>
👤 User ID:
{{ w["telegram_id"] }}
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

<form method="POST"
action="/approve/{{ w['id'] }}">

<input
name="amount"
type="number"
step="0.01"
placeholder="Payment Amount (টাকা)"
required
>

<button type="submit">
✅ Payment Complete
</button>

</form>

<form method="POST"
action="/reject/{{ w['id'] }}">

<button type="submit">
❌ Reject
</button>

</form>

{% else %}

<p>
💰 Payment:
<b>{{ w["payment_amount"] }}</b>
</p>

{% endif %}

</div>

{% endfor %}

</div>

</div>

</body>
</html>
"""


@web.route("/")
def home():
    return "EarnMate AI Bot is running."


@web.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        admin_id = request.form.get("admin_id", "")
        password = request.form.get("password", "")

        if (
            admin_id == ADMIN_ID
            and password == ADMIN_PASSWORD
        ):

            session["admin"] = True

            return redirect("/admin")

        return render_template_string(
            LOGIN_PAGE,
            error="❌ Admin ID অথবা Password ভুল।"
        )

    return render_template_string(
        LOGIN_PAGE,
        error=None
    )


@web.route("/admin")
def admin():

    if not session.get("admin"):
        return redirect("/login")

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
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
        PANEL_PAGE,
        users=users,
        referrals=referrals,
        coins=coins,
        withdrawal_count=withdrawal_count,
        withdrawals=withdrawals,
        admin_id=ADMIN_ID
    )


@web.route("/approve/<int:request_id>", methods=["POST"])
def approve(request_id):

    if not session.get("admin"):
        return redirect("/login")

    amount = request.form.get("amount", "")

    try:
        amount = float(amount)
    except ValueError:
        return redirect("/admin")

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE withdrawals
        SET payment_amount=?,
            status='Paid'
        WHERE id=?
        AND status='Pending'
    """, (amount, request_id))

    conn.commit()
    conn.close()

    return redirect("/admin")


@web.route("/reject/<int:request_id>", methods=["POST"])
def reject(request_id):

    if not session.get("admin"):
        return redirect("/login")

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE withdrawals
        SET status='Rejected'
        WHERE id=?
        AND status='Pending'
    """, (request_id,))

    conn.commit()
    conn.close()

    return redirect("/admin")


@web.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


def run_web():

    port = int(
        os.environ.get("PORT", "10000")
    )

    web.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False
    )


# =========================
# TELEGRAM BOT
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    conn = connect_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE telegram_id=?",
        (user.id,)
    )

    existing = cur.fetchone()

    if not existing:

        referrer = None

        if context.args:

            try:

                ref_id = int(context.args[0])

                # Self referral বন্ধ
                if ref_id != user.id:

                    cur.execute(
                        "SELECT telegram_id FROM users WHERE telegram_id=?",
                        (ref_id,)
                    )

                    ref_user = cur.fetchone()

                    if ref_user:
                        referrer = ref_id

            except ValueError:
                pass

        cur.execute("""
            INSERT INTO users
            (telegram_id, username, first_name, referred_by)
            VALUES (?, ?, ?, ?)
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            referrer
        ))

        if referrer:

            cur.execute("""
                UPDATE users
                SET referrals = referrals + 1,
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
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def coins(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    conn = connect_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT coins, referrals
        FROM users
        WHERE telegram_id=?
        """,
        (user.id,)
    )

    row = cur.fetchone()

    conn.close()

    if not row:
        return

    await update.callback_query.message.reply_text(

        f"🪙 আপনার Coins: {row['coins']}\n\n"
        f"👥 Referral: {row['referrals']} জন\n\n"
        f"🎁 প্রতি Referral = {REFERRAL_BONUS} Coins\n"
        f"💳 Minimum Withdraw = {MIN_WITHDRAW} Coins"

    )


async def referral(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    bot_username = context.bot.username

    link = (
        f"https://t.me/{bot_username}"
        f"?start={user.id}"
    )

    conn = connect_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT referrals, coins
        FROM users
        WHERE telegram_id=?
        """,
        (user.id,)
    )

    row = cur.fetchone()

    conn.close()

    referrals = row["referrals"] if row else 0
    coins = row["coins"] if row else 0

    await update.callback_query.message.reply_text(

        "🔗 আপনার Referral Link:\n\n"
        f"{link}\n\n"
        f"👥 Referral: {referrals} জন\n"
        f"🪙 Coins: {coins}\n\n"
        f"🎁 প্রতি সফল Referral = "
        f"{REFERRAL_BONUS} Coins"

    )


async def withdraw(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    conn = connect_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT coins FROM users WHERE telegram_id=?",
        (user.id,)
    )

    row = cur.fetchone()

    conn.close()

    if not row:
        return

    if row["coins"] < MIN_WITHDRAW:

        await update.callback_query.message.reply_text(

            f"❌ Withdraw করা যাবে না।\n\n"
            f"🪙 আপনার Coins: {row['coins']}\n"
            f"💳 Minimum: {MIN_WITHDRAW} Coins\n\n"
            f"আরও {MIN_WITHDRAW-row['coins']} Coins লাগবে।"

        )

        return

    keyboard = [

        [
            InlineKeyboardButton(
                "💳 bKash",
                callback_data="method_bkash"
            )
        ],

        [
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
        "💳 Payment Method নির্বাচন করুন:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


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

    context.user_data["withdraw_method"] = method
    context.user_data["withdraw_step"] = "number"

    await query.message.reply_text(

        f"💳 Method: {method.capitalize()}\n\n"
        "📱 আপনার ১১ সংখ্যার Payment Number লিখুন।"

    )


async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if query.data == "coins":
        await query.answer()
        await coins(update, context)

    elif query.data == "referral":
        await query.answer()
        await referral(update, context)

    elif query.data == "withdraw":
        await query.answer()
        await withdraw(update, context)

    elif query.data.startswith("method_"):
        await choose_method(update, context)

    elif query.data == "income":

        await query.answer()

        await query.message.reply_text(
            "💰 ইনকামের মাধ্যম:\n\n"
            "1️⃣ Freelancing\n"
            "2️⃣ Affiliate Marketing\n"
            "3️⃣ Micro Tasks\n"
            "4️⃣ Content Creation"
        )

    elif query.data == "ai":

        await query.answer()

        await query.message.reply_text(
            "🤖 আপনার প্রশ্নটি লিখুন।"
        )


async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()

    step = context.user_data.get(
        "withdraw_step"
    )


    # =========================
    # PAYMENT NUMBER
    # =========================

    if step == "number":

        number = (
            text.replace(" ", "")
            .replace("-", "")
        )

        if not number.isdigit() or len(number) != 11:

            await update.message.reply_text(
                "❌ সঠিক ১১ সংখ্যার নম্বর দিন।"
            )

            return

        context.user_data["number"] = number
        context.user_data["withdraw_step"] = "comment"

        await update.message.reply_text(

            "📝 এখন Comment লিখুন।\n\n"
            "উদাহরণ:\n"
            "Payment করার অনুরোধ করছি।"

        )

        return


    # =========================
    # COMMENT
    # =========================

    if step == "comment":

        user = update.effective_user

        method = context.user_data.get(
            "withdraw_method"
        )

        number = context.user_data.get(
            "number"
        )

        conn = connect_db()
        cur = conn.cursor()

        # আবার balance check
        cur.execute(
            "SELECT coins FROM users WHERE telegram_id=?",
            (user.id,)
        )

        row = cur.fetchone()

        if not row or row["coins"] < MIN_WITHDRAW:

            conn.close()

            context.user_data.clear()

            await update.message.reply_text(
                "❌ আপনার পর্যাপ্ত Coins নেই।"
            )

            return


        # একই user-এর Pending request আছে কিনা
        cur.execute("""
            SELECT id
            FROM withdrawals
            WHERE telegram_id=?
            AND status='Pending'
        """, (user.id,))

        pending = cur.fetchone()

        if pending:

            conn.close()

            context.user_data.clear()

            await update.message.reply_text(
                "⏳ আপনার একটি Withdrawal Request ইতিমধ্যে Pending আছে।"
            )

            return


        # Withdrawal request
        cur.execute("""
            INSERT INTO withdrawals
            (
                telegram_id,
                coins,
                method,
                payment_number,
                comment
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user.id,
            row["coins"],
            method,
            number,
            text
        ))

        conn.commit()
        conn.close()

        context.user_data.clear()

        await update.message.reply_text(

            "✅ Withdrawal Request পাঠানো হয়েছে!\n\n"
            f"🪙 Coins: {row['coins']}\n"
            f"💳 Method: {method.capitalize()}\n"
            f"📱 Number: {number}\n\n"
            "⏳ Admin যাচাই করে Payment করবেন।"

        )

        return


    await update.message.reply_text(
        "🤖 আপনার প্রশ্নটি পেয়েছি।"
    )


# =========================
# MAIN
# =========================

def main():

    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN সেট করা হয়নি।"
        )

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )

    print(
        "EarnMate AI Bot + Admin Panel is running..."
    )

    app.run_polling()


if __name__ == "__main__":
    main()
