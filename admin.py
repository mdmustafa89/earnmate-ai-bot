import os
import sqlite3
from functools import wraps
from flask import Flask, request, redirect, session, render_template_string

app = Flask(__name__)

# These values come from Render Environment Variables
ADMIN_ID = os.getenv("ADMIN_ID")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "change-this-secret-key")

app.secret_key = SECRET_KEY

DB_FILE = "earnmate.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

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


def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect("/login")
        return function(*args, **kwargs)

    return wrapper


LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EarnMate Admin Login</title>
<style>
body {
    font-family: Arial;
    background:#f2f2f2;
    padding:30px;
}
.box {
    max-width:400px;
    margin:50px auto;
    background:white;
    padding:25px;
    border-radius:15px;
    box-shadow:0 2px 10px #ccc;
}
input, button {
    width:100%;
    padding:13px;
    margin:8px 0;
    box-sizing:border-box;
}
button {
    cursor:pointer;
}
.error {
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
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EarnMate Admin Panel</title>
<style>
body {
    font-family:Arial;
    background:#f5f5f5;
    padding:15px;
}
.container {
    max-width:900px;
    margin:auto;
}
.box {
    background:white;
    padding:20px;
    margin-bottom:20px;
    border-radius:15px;
    box-shadow:0 2px 8px #ddd;
}
input, textarea, button {
    width:100%;
    padding:12px;
    margin:7px 0;
    box-sizing:border-box;
}
button {
    cursor:pointer;
}
.item {
    border:1px solid #ddd;
    padding:12px;
    margin:10px 0;
    border-radius:10px;
}
a {
    word-break:break-all;
}
</style>
</head>

<body>
<div class="container">

<h1>👑 EarnMate AI Admin Panel</h1>

<div class="box">
<h2>📊 Dashboard</h2>
<p>🎁 Total Offers: {{ offer_count }}</p>
<p>📢 Total Ads: {{ ad_count }}</p>
<p>🔐 Admin ID: {{ admin_id }}</p>
<a href="/logout">🚪 Logout</a>
</div>


<div class="box">
<h2>🎁 Affiliate Offer যোগ করুন</h2>

<form method="POST" action="/add-offer">
<input name="name" placeholder="Offer Name" required>
<textarea name="description" placeholder="Offer Description"></textarea>
<input name="link" placeholder="Referral Link" required>
<button type="submit">➕ Add Offer</button>
</form>
</div>


<div class="box">
<h2>📋 Affiliate Offers</h2>

{% for offer in offers %}
<div class="item">
<b>{{ offer[1] }}</b>
<p>{{ offer[2] }}</p>
<a href="{{ offer[3] }}" target="_blank">{{ offer[3] }}</a>

<form method="POST" action="/delete-offer/{{ offer[0] }}">
<button type="submit">🗑️ Delete</button>
</form>
</div>
{% endfor %}

</div>


<div class="box">
<h2>📢 Advertisement / Direct Link</h2>

<form method="POST" action="/add-ad">
<input name="name" placeholder="Ad Name" required>
<input name="link" placeholder="Direct Ad Link" required>
<button type="submit">➕ Add Advertisement</button>
</form>
</div>


<div class="box">
<h2>📋 Current Ads</h2>

{% for ad in ads %}
<div class="item">
<b>{{ ad[1] }}</b>
<p>
<a href="{{ ad[2] }}" target="_blank">{{ ad[2] }}</a>
</p>

<form method="POST" action="/delete-ad/{{ ad[0] }}">
<button type="submit">🗑️ Delete</button>
</form>
</div>
{% endfor %}

</div>


<div class="box">
<h2>🌐 Social Media Links</h2>

<form method="POST" action="/save-social">

<input name="facebook"
value="{{ social[0] }}"
placeholder="Facebook Link">

<input name="youtube"
value="{{ social[1] }}"
placeholder="YouTube Link">

<input name="telegram"
value="{{ social[2] }}"
placeholder="Telegram Channel Link">

<input name="whatsapp"
value="{{ social[3] }}"
placeholder="WhatsApp Link">

<button type="submit">💾 Save Social Links</button>

</form>
</div>


<div class="box">
<h2>🌐 User Social Buttons</h2>

<p>👤 User-এর কাছে এই বাটনগুলো দেখানো যাবে:</p>

<p>🔵 Facebook</p>
<p>🔴 YouTube</p>
<p>✈️ Telegram</p>
<p>🟢 WhatsApp</p>

</div>

</div>
</body>
</html>
"""


@app.route("/login", methods=["GET", "POST"])
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


@app.route("/admin")
@admin_required
def admin():

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT * FROM offers ORDER BY id DESC")
    offers = cur.fetchall()

    cur.execute("SELECT * FROM ads ORDER BY id DESC")
    ads = cur.fetchall()

    cur.execute("""
        SELECT facebook, youtube, telegram, whatsapp
        FROM social_links
        WHERE id = 1
    """)
    social = cur.fetchone()

    offer_count = len(offers)
    ad_count = len(ads)

    conn.close()

    return render_template_string(
        PANEL_HTML,
        offers=offers,
        ads=ads,
        social=social,
        offer_count=offer_count,
        ad_count=ad_count,
        admin_id=ADMIN_ID
    )


@app.route("/add-offer", methods=["POST"])
@admin_required
def add_offer():

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    link = request.form.get("link", "").strip()

    if name and link:

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO offers (name, description, link) VALUES (?, ?, ?)",
            (name, description, link)
        )

        conn.commit()
        conn.close()

    return redirect("/admin")


@app.route("/delete-offer/<int:offer_id>", methods=["POST"])
@admin_required
def delete_offer(offer_id):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM offers WHERE id = ?",
        (offer_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/admin")


@app.route("/add-ad", methods=["POST"])
@admin_required
def add_ad():

    name = request.form.get("name", "").strip()
    link = request.form.get("link", "").strip()

    if name and link:

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO ads (name, link) VALUES (?, ?)",
            (name, link)
        )

        conn.commit()
        conn.close()

    return redirect("/admin")


@app.route("/delete-ad/<int:ad_id>", methods=["POST"])
@admin_required
def delete_ad(ad_id):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM ads WHERE id = ?",
        (ad_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/admin")


@app.route("/save-social", methods=["POST"])
@admin_required
def save_social():

    facebook = request.form.get("facebook", "").strip()
    youtube = request.form.get("youtube", "").strip()
    telegram = request.form.get("telegram", "").strip()
    whatsapp = request.form.get("whatsapp", "").strip()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        UPDATE social_links
        SET facebook = ?,
            youtube = ?,
            telegram = ?,
            whatsapp = ?
        WHERE id = 1
    """, (
        facebook,
        youtube,
        telegram,
        whatsapp
    ))

    conn.commit()
    conn.close()

    return redirect("/admin")


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
  )
