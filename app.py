from flask import Flask, render_template, request, redirect, url_for

from database import (
    get_db,
    create_database,
    add_sample_listings,
    add_listing,
    update_listing,
    delete_listing
)

from ai import ai_search


app = Flask(__name__)


# تجهيز قاعدة البيانات
create_database()
add_sample_listings()


# -------------------------
# الرئيسية
# -------------------------

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


# -------------------------
# البحث
# -------------------------

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


# -------------------------
# بيع الآن
# -------------------------

@app.route("/sell")
def sell():

    return render_template("sell.html")


# -------------------------
# إنشاء إعلان
# -------------------------

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


# -------------------------
# فتح إعلان
# -------------------------

@app.route("/listing/<int:listing_id>")
def listing(listing_id):

    connection = get_db()

    item = connection.execute("""
        SELECT *
        FROM listings
        WHERE id = ?
    """, (listing_id,)).fetchone()

    connection.close()

    if item is None:

        return "الإعلان غير موجود.", 404

    return render_template(
        "listing.html",
        listing=item
    )


# -------------------------
# إعلاناتي
# -------------------------

@app.route("/my-listings")
def my_listings():

    connection = get_db()

    listings = connection.execute("""
        SELECT *
        FROM listings
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "my_listings.html",
        listings=listings
    )


# -------------------------
# تعديل إعلان
# -------------------------

@app.route("/listing/<int:listing_id>/edit", methods=["GET", "POST"])
def edit_listing(listing_id):

    connection = get_db()

    item = connection.execute("""
        SELECT *
        FROM listings
        WHERE id = ?
    """, (listing_id,)).fetchone()

    connection.close()

    if item is None:

        return "الإعلان غير موجود.", 404

    if request.method == "POST":

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

        update_listing(
            listing_id,
            title,
            category,
            price,
            city,
            description
        )

        return redirect(
            url_for(
                "listing",
                listing_id=listing_id
            )
        )

    return render_template(
        "edit_listing.html",
        listing=item
    )


# -------------------------
# حذف إعلان
# -------------------------

@app.route("/listing/<int:listing_id>/delete", methods=["POST"])
def remove_listing(listing_id):

    delete_listing(listing_id)

    return redirect(
        url_for("my_listings")
    )


# -------------------------
# تشغيل التطبيق
# -------------------------

if __name__ == "__main__":

    import os

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )