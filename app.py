from flask import Flask, render_template, request, redirect, url_for

from database import (
    get_db,
    create_database,
    add_sample_listings,
    add_listing
)

from ai import ai_search


app = Flask(__name__)


# تجهيز قاعدة البيانات
create_database()
add_sample_listings()


@app.route("/")
def home():

    connection = get_db()

    listings = connection.execute("""
        SELECT *
        FROM listings
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "index.html",
        listings=listings,
        search_query=""
    )


@app.route("/search")
def search():

    query = request.args.get("q", "").strip()

    connection = get_db()

    if query:

        listings = connection.execute("""
            SELECT *
            FROM listings
            WHERE title LIKE ?
               OR category LIKE ?
               OR city LIKE ?
               OR description LIKE ?
            ORDER BY id DESC
        """, (
            f"%{query}%",
            f"%{query}%",
            f"%{query}%",
            f"%{query}%"
        )).fetchall()

    else:

        listings = connection.execute("""
            SELECT *
            FROM listings
            ORDER BY id DESC
        """).fetchall()

    connection.close()

    return render_template(
        "index.html",
        listings=listings,
        search_query=query
    )


# -------------------------
# Lavreen AI
# -------------------------

@app.route("/ai", methods=["GET", "POST"])
def ai():

    query = ""
    results = []

    if request.method == "POST":

        query = request.form.get("query", "").strip()

        connection = get_db()

        listings = connection.execute("""
            SELECT *
            FROM listings
            ORDER BY id DESC
        """).fetchall()

        connection.close()

        if query:
            results = ai_search(query, listings)

    return render_template(
        "ai.html",
        query=query,
        results=results
    )


# صفحة إضافة إعلان
@app.route("/sell")
def sell():

    return render_template("sell.html")


# استقبال الإعلان الجديد
@app.route("/sell", methods=["POST"])
def create_listing():

    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    price = request.form.get("price", "").strip()
    city = request.form.get("city", "").strip()
    description = request.form.get("description", "").strip()

    if not title or not category or not price or not city:

        return "فضلاً عبّ جميع الحقول المطلوبة."


    try:
        price = float(price)

    except ValueError:

        return "السعر يجب أن يكون رقمًا."


    add_listing(
        title,
        category,
        price,
        city,
        description
    )


    return redirect(url_for("home"))

if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )