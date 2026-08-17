
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from functools import wraps

from database import (
    get_db,
    create_database,
    add_sample_listings,
    add_listing,
    update_listing_for_owner,
    delete_listing_for_owner,
    add_listing_media,
    get_listing_media,
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_listing,
    get_listings_by_owner
)

from ai import ai_search

import os

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash


# =========================================================
# PATHS
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STATIC_FOLDER = os.path.join(BASE_DIR, "static")
TEMPLATES_FOLDER = os.path.join(BASE_DIR, "templates")
UPLOAD_FOLDER = os.path.join(STATIC_FOLDER, "uploads")


# =========================================================
# FLASK
# =========================================================

app = Flask(
    __name__,
    static_folder=STATIC_FOLDER,
    static_url_path="/static",
    template_folder=TEMPLATES_FOLDER
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "lavreen-development-secret-key"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================================================
# DATABASE
# =========================================================

create_database()
add_sample_listings()


# =========================================================
# LOGIN REQUIRED
# =========================================================

def login_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            flash("يجب تسجيل الدخول أولاً.", "warning")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return decorated_function


# =========================================================
# CURRENT USER
# =========================================================

@app.context_processor
def inject_current_user():

    user = None

    if "user_id" in session:
        user = get_user_by_id(session["user_id"])

    return {
        "current_user": user
    }


# =========================================================
# GET LISTINGS
# =========================================================

def get_listings():

    connection = get_db()

    listings = connection.execute("""
        SELECT
            listings.*,
            (
                SELECT file_path
                FROM listing_media
                WHERE listing_media.listing_id = listings.id
                AND listing_media.media_type = 'image'
                ORDER BY sort_order ASC, id ASC
                LIMIT 1
            ) AS image_path
        FROM listings
        ORDER BY listings.id DESC
    """).fetchall()

    connection.close()

    return listings


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    listings = get_listings()

    return render_template(
        "index.html",
        listings=listings,
        search_query=""
    )


# =========================================================
# SEARCH
# =========================================================

@app.route("/search")
def search():

    query = request.args.get("q", "").strip()

    connection = get_db()

    if query:

        listings = connection.execute("""
            SELECT
                listings.*,
                (
                    SELECT file_path
                    FROM listing_media
                    WHERE listing_media.listing_id = listings.id
                    AND listing_media.media_type = 'image'
                    ORDER BY sort_order ASC, id ASC
                    LIMIT 1
                ) AS image_path
            FROM listings
            WHERE title LIKE ?
               OR category LIKE ?
               OR city LIKE ?
               OR description LIKE ?
            ORDER BY listings.id DESC
        """, (
            f"%{query}%",
            f"%{query}%",
            f"%{query}%",
            f"%{query}%"
        )).fetchall()

    else:

        listings = connection.execute("""
            SELECT
                listings.*,
                (
                    SELECT file_path
                    FROM listing_media
                    WHERE listing_media.listing_id = listings.id
                    AND listing_media.media_type = 'image'
                    ORDER BY sort_order ASC, id ASC
                    LIMIT 1
                ) AS image_path
            FROM listings
            ORDER BY listings.id DESC
        """).fetchall()

    connection.close()

    return render_template(
        "index.html",
        listings=listings,
        search_query=query
    )


# =========================================================
# AI
# =========================================================

@app.route("/ai", methods=["GET", "POST"])
def ai():

    query = ""
    results = []

    if request.method == "POST":

        query = request.form.get(
            "query",
            ""
        ).strip()

        connection = get_db()

        listings = connection.execute("""
            SELECT *
            FROM listings
            ORDER BY id DESC
        """).fetchall()

        connection.close()

        if query:
            results = ai_search(
                query,
                listings
            )

    return render_template(
        "ai.html",
        query=query,
        results=results
    )


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not name or not email or not password:
            flash(
                "فضلاً عبّ جميع الحقول.",
                "error"
            )

            return render_template(
                "register.html"
            )

        if len(name) < 2:
            flash(
                "الاسم يجب أن يكون حرفين على الأقل.",
                "error"
            )

            return render_template(
                "register.html"
            )

        if len(password) < 6:
            flash(
                "كلمة المرور يجب أن تكون 6 أحرف على الأقل.",
                "error"
            )

            return render_template(
                "register.html"
            )

        if password != confirm_password:
            flash(
                "كلمتا المرور غير متطابقتين.",
                "error"
            )

            return render_template(
                "register.html"
            )

        existing_user = get_user_by_email(email)

        if existing_user:

            flash(
                "هذا البريد الإلكتروني مسجل مسبقًا.",
                "error"
            )

            return render_template(
                "register.html"
            )

        password_hash = generate_password_hash(
            password
        )

        user_id = create_user(
            name,
            email,
            password_hash
        )

        if user_id is None:

            flash(
                "تعذر إنشاء الحساب، جرّب بريدًا آخر.",
                "error"
            )

            return render_template(
                "register.html"
            )

        session["user_id"] = user_id

        flash(
            "تم إنشاء حسابك بنجاح 👋",
            "success"
        )

        return redirect(
            url_for("home")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        user = get_user_by_email(email)

        if user is None:

            flash(
                "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
                "error"
            )

            return render_template(
                "login.html"
            )

        if not check_password_hash(
            user["password_hash"],
            password
        ):

            flash(
                "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
                "error"
            )

            return render_template(
                "login.html"
            )

        session.clear()

        session["user_id"] = user["id"]

        flash(
            f"حياك الله {user['name']} 👋",
            "success"
        )

        next_page = request.args.get("next")

        if next_page and next_page.startswith("/"):
            return redirect(next_page)

        return redirect(
            url_for("home")
        )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "تم تسجيل الخروج.",
        "success"
    )

    return redirect(
        url_for("home")
    )


# =========================================================
# SELL
# =========================================================

@app.route("/sell")
@login_required
def sell():

    return render_template(
        "sell.html"
    )


# =========================================================
# CREATE LISTING
# =========================================================

@app.route("/sell", methods=["POST"])
@login_required
def create_listing():

    title = request.form.get(
        "title",
        ""
    ).strip()

    category = request.form.get(
        "category",
        ""
    ).strip()

    price = request.form.get(
        "price",
        ""
    ).strip()

    city = request.form.get(
        "city",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    images = request.files.getlist(
        "images"
    )

    videos = request.files.getlist(
        "videos"
    )

    if not title or not category or not price or not city:

        flash(
            "فضلاً عبّ جميع الحقول المطلوبة.",
            "error"
        )

        return redirect(
            url_for("sell")
        )

    if len(images) > 30:

        flash(
            "يمكن إضافة 30 صورة كحد أقصى.",
            "error"
        )

        return redirect(
            url_for("sell")
        )

    if len(videos) > 5:

        flash(
            "يمكن إضافة 5 فيديوهات كحد أقصى.",
            "error"
        )

        return redirect(
            url_for("sell")
        )

    try:

        price = float(price)

    except ValueError:

        flash(
            "السعر يجب أن يكون رقمًا.",
            "error"
        )

        return redirect(
            url_for("sell")
        )

    listing_id = add_listing(
        title,
        category,
        price,
        city,
        description,
        session["user_id"]
    )

    for index, image in enumerate(images):

        if image and image.filename:

            filename = secure_filename(
                image.filename
            )

            filename = (
                f"{listing_id}_image_"
                f"{index}_{filename}"
            )

            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            image.save(filepath)

            add_listing_media(
                listing_id,
                "image",
                f"uploads/{filename}",
                index
            )

    for index, video in enumerate(videos):

        if video and video.filename:

            filename = secure_filename(
                video.filename
            )

            filename = (
                f"{listing_id}_video_"
                f"{index}_{filename}"
            )

            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            video.save(filepath)

            add_listing_media(
                listing_id,
                "video",
                f"uploads/{filename}",
                index
            )

    flash(
        "تم نشر إعلانك بنجاح 🎉",
        "success"
    )

    return redirect(
        url_for(
            "listing",
            listing_id=listing_id
        )
    )


# =========================================================
# LISTING PAGE
# =========================================================

@app.route("/listing/<int:listing_id>")
def listing(listing_id):

    item = get_listing(
        listing_id
    )

    if item is None:

        return "الإعلان غير موجود.", 404

    media = get_listing_media(
        listing_id
    )

    seller = None

    if item["owner_id"]:

        seller = get_user_by_id(
            item["owner_id"]
        )

    return render_template(
        "listing.html",
        listing=item,
        media=media,
        seller=seller
    )


# =========================================================
# MY LISTINGS
# =========================================================

@app.route("/my-listings")
@login_required
def my_listings():

    listings = get_listings_by_owner(
        session["user_id"]
    )

    return render_template(
        "my_listings.html",
        listings=listings
    )


# =========================================================
# EDIT LISTING
# =========================================================

@app.route(
    "/listing/<int:listing_id>/edit",
    methods=["GET", "POST"]
)
@login_required
def edit_listing(listing_id):

    item = get_listing(
        listing_id
    )

    if item is None:

        return "الإعلان غير موجود.", 404

    if item["owner_id"] != session["user_id"]:

        flash(
            "ما تقدر تعدّل إعلان مو لك.",
            "error"
        )

        return redirect(
            url_for("my_listings")
        )

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        price = request.form.get(
            "price",
            ""
        ).strip()

        city = request.form.get(
            "city",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        images = request.files.getlist(
            "images"
        )

        videos = request.files.getlist(
            "videos"
        )

        if not title or not category or not price or not city:

            flash(
                "فضلاً عبّ جميع الحقول المطلوبة.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_listing",
                    listing_id=listing_id
                )
            )

        if len(images) > 30:

            flash(
                "يمكن إضافة 30 صورة كحد أقصى.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_listing",
                    listing_id=listing_id
                )
            )

        if len(videos) > 5:

            flash(
                "يمكن إضافة 5 فيديوهات كحد أقصى.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_listing",
                    listing_id=listing_id
                )
            )

        try:

            price = float(price)

        except ValueError:

            flash(
                "السعر يجب أن يكون رقمًا.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_listing",
                    listing_id=listing_id
                )
            )

        updated = update_listing_for_owner(
            listing_id,
            session["user_id"],
            title,
            category,
            price,
            city,
            description
        )

        if not updated:

            flash(
                "تعذر تعديل الإعلان.",
                "error"
            )

            return redirect(
                url_for("my_listings")
            )

        media = get_listing_media(
            listing_id
        )

        image_order = 0
        video_order = 0

        for media_item in media:

            if media_item["media_type"] == "image":
                image_order += 1

            elif media_item["media_type"] == "video":
                video_order += 1

        for image in images:

            if image and image.filename:

                filename = secure_filename(
                    image.filename
                )

                filename = (
                    f"{listing_id}_image_"
                    f"{image_order}_{filename}"
                )

                filepath = os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )

                image.save(filepath)

                add_listing_media(
                    listing_id,
                    "image",
                    f"uploads/{filename}",
                    image_order
                )

                image_order += 1

        for video in videos:

            if video and video.filename:

                filename = secure_filename(
                    video.filename
                )

                filename = (
                    f"{listing_id}_video_"
                    f"{video_order}_{filename}"
                )

                filepath = os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )

                video.save(filepath)

                add_listing_media(
                    listing_id,
                    "video",
                    f"uploads/{filename}",
                    video_order
                )

                video_order += 1

        flash(
            "تم تعديل الإعلان بنجاح ✅",
            "success"
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


# =========================================================
# DELETE LISTING
# =========================================================

@app.route(
    "/listing/<int:listing_id>/delete",
    methods=["POST"]
)
@login_required
def remove_listing(listing_id):

    deleted = delete_listing_for_owner(
        listing_id,
        session["user_id"]
    )

    if not deleted:

        flash(
            "ما تقدر تحذف إعلان مو لك.",
            "error"
        )

        return redirect(
            url_for("my_listings")
        )

    flash(
        "تم حذف الإعلان.",
        "success"
    )

    return redirect(
        url_for("my_listings")
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

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