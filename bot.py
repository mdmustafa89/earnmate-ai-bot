import os
import threading

from flask import Flask
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

# -------------------------
# Flask server
# -------------------------

web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "EarnMate AI Bot is running."


@web_app.route("/health")
def health():
    return "OK"


def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False
    )


# -------------------------
# Telegram Bot
# -------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

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
    ]

    await update.message.reply_text(
        "👋 স্বাগতম EarnMate AI Bot-এ!\n\n"
        "অনলাইন ইনকাম সম্পর্কে জানতে নিচের অপশন নির্বাচন করুন।",
        reply_markup=InlineKeyboardMarkup(keyboard),
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


async def offers(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🎁 Affiliate Offers\n\n"
        "Admin Panel থেকে যোগ করা অফারগুলো এখানে দেখানো হবে।"
    )


async def ads(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📢 Ads / Direct Link\n\n"
        "Admin Panel থেকে যোগ করা বিজ্ঞাপন এখানে দেখানো হবে।"
    )


async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    if query.data == "ai":

        await query.message.reply_text(
            "🤖 আপনার প্রশ্নটি লিখুন।\n\n"
            "উদাহরণ:\n"
            "👉 অনলাইন থেকে কীভাবে ইনকাম করব?"
        )

    elif query.data == "income":

        await income(update, context)

    elif query.data == "offers":

        await offers(update, context)

    elif query.data == "ads":

        await ads(update, context)


async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text

    await update.message.reply_text(
        "🤖 আপনার প্রশ্ন পেয়েছি।\n\n"
        f"প্রশ্ন: {text}\n\n"
        "AI উত্তর দেওয়ার সিস্টেম পরের ধাপে যুক্ত করা হবে।"
    )


# -------------------------
# Main
# -------------------------

def main():

    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN সেট করা হয়নি।"
        )

    # Start Flask server
    threading.Thread(
        target=run_web_server,
        daemon=True
    ).start()

    # Start Telegram bot
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
        CommandHandler("offers", offers)
    )

    app.add_handler(
        CommandHandler("ads", ads)
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
        "EarnMate AI Bot + Admin Web Server is running..."
    )

    app.run_polling()


if __name__ == "__main__":
    main()
