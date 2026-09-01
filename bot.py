
import os
import threading
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


# =========================
# Flask / Admin Panel
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
</style>
</head>
<body>

<div class="container">

<h1>👑 EarnMate AI Admin Panel</h1>

<div class="box">
<h2>📊 Dashboard</h2>
<p>🔐 Admin ID: {{ admin_id }}</p>
<p>🎁 Affiliate Offers: {{ offers|length }}</p>
<p>📢 Advertisements: {{ ads|length }}</p>
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
<h2>📢 Advertisement / Direct Link</h2>

<form method="POST" action="/add-ad">
<input name="name" placeholder="Ad Name" required>
<input name="link" placeholder="Direct Link" required>
<button type="submit">➕ Add Advertisement</button>
</form>
</div>

<div class="box">
<h2>🌐 Social Media Links</h2>

<form method="POST" action="/save-social">
<input name="facebook" placeholder="Facebook Link">
<input name="youtube" placeholder="YouTube Link">
<input name="telegram" placeholder="Telegram Channel Link">
<input name="whatsapp" placeholder="WhatsApp Link">
<button type="submit">💾 Save Social Links</button>
</form>
</div>

<div class="box">
<h2>📋 Current Offers</h2>
{% for offer in offers %}
<hr>
<b>{{ offer["name"] }}</b>
<p>{{ offer["description"] }}</p>
<a href="{{ offer["link"] }}" target="_blank">🔗 Referral Link</a>
{% endfor %}
</div>

<div class="box">
<h2>📋 Current Ads</h2>
{% for ad in ads %}
<hr>
<b>{{ ad["name"] }}</b>
<p><a href="{{ ad["link"] }}" target="_blank">🔗 Direct Link</a></p>
{% endfor %}
</div>

</div>
</body>
</html>
"""


offers = []
ads = []
social_links = {
    "facebook": "",
    "youtube": "",
    "telegram": "",
    "whatsapp": ""
}


@web_app.route("/")
def home():
    return "EarnMate AI Bot is running."


@web_app.route("/admin", methods=["GET"])
def admin():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    return render_template_string(
        PANEL_HTML,
        offers=offers,
        ads=ads,
        admin_id=ADMIN_ID
    )


@web_app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        admin_id = request.form.get("admin_id", "")
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


@web_app.route("/logout")
def logout():

    session.clear()
    return redirect("/login")


@web_app.route("/add-offer", methods=["POST"])
def add_offer():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    offers.append({
        "name": request.form.get("name", ""),
        "description": request.form.get("description", ""),
        "link": request.form.get("link", "")
    })

    return redirect("/admin")


@web_app.route("/add-ad", methods=["POST"])
def add_ad():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    ads.append({
        "name": request.form.get("name", ""),
        "link": request.form.get("link", "")
    })

    return redirect("/admin")


@web_app.route("/save-social", methods=["POST"])
def save_social():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    social_links["facebook"] = request.form.get("facebook", "")
    social_links["youtube"] = request.form.get("youtube", "")
    social_links["telegram"] = request.form.get("telegram", "")
    social_links["whatsapp"] = request.form.get("whatsapp", "")

    return redirect("/admin")


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

    keyboard = [
        [InlineKeyboardButton("🤖 AI-কে প্রশ্ন করুন", callback_data="ai")],
        [InlineKeyboardButton("💰 ইনকামের মাধ্যম", callback_data="income")],
        [InlineKeyboardButton("🎁 Affiliate Offers", callback_data="offers")],
        [InlineKeyboardButton("📢 Ads / Direct Link", callback_data="ads")],
    ]

    await update.message.reply_text(
        "👋 স্বাগতম EarnMate AI Bot-এ!\n\n"
        "অনলাইন ইনকাম সম্পর্কে জানতে নিচের অপশন নির্বাচন করুন।",
        reply_markup=InlineKeyboardMarkup(keyboard)
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

    if not offers:
        await update.message.reply_text(
            "🎁 বর্তমানে কোনো Affiliate Offer নেই।"
        )
        return

    text = "🎁 Affiliate Offers\n\n"

    for offer in offers:
        text += (
            f"📌 {offer['name']}\n"
            f"{offer['description']}\n"
            f"🔗 {offer['link']}\n\n"
        )

    await update.message.reply_text(text)


async def ads_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not ads:
        await update.message.reply_text(
            "📢 বর্তমানে কোনো Advertisement নেই।"
        )
        return

    text = "📢 Advertisements\n\n"

    for ad in ads:
        text += (
            f"📌 {ad['name']}\n"
            f"🔗 {ad['link']}\n\n"
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

        await income(update, context)

    elif query.data == "offers":

        await offers_command(update, context)

    elif query.data == "ads":

        await ads_command(update, context)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text

    await update.message.reply_text(
        "🤖 আপনার প্রশ্ন পেয়েছি।\n\n"
        f"প্রশ্ন: {text}\n\n"
        "AI সিস্টেম পরের ধাপে যুক্ত করা হবে।"
    )


def main():

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN সেট করা হয়নি।")

    threading.Thread(
        target=run_web_server,
        daemon=True
    ).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("income", income))
    app.add_handler(CommandHandler("offers", offers_command))
    app.add_handler(CommandHandler("ads", ads_command))

    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler
        )
    )

    print("EarnMate AI Bot + Admin Panel is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
