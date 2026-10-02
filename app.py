from flask import Flask, render_template, request, redirect, url_for, session
import os
import uuid

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

import database
import ai_assistant


app = Flask(__name__)

# =========================================================
# CONFIG
# =========================================================

app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    # للاستخدام المحلي فقط.
    # في Render يجب إضافة SECRET_KEY من Environment Variables.
    app.secret_key = "lavreen-local-development-secret-change-me"


UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# الحد الأقصى لكل Request = 100MB
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024


ALLOWED_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "gif",
}

ALLOWED_VIDEO_EXTENSIONS = {
    "mp4",
    "mov",
    "avi",
    "mkv",
    "webm",
}

ALLOWED_UPLOAD_EXTENSIONS = (
    ALLOWED_IMAGE_EXTENSIONS |
    ALLOWED_VIDEO_EXTENSIONS
)


# =========================================================
# DATABASE
# =========================================================

database.create_database()

# مهم جدًا:
# لا نشغل remove_demo_listings() هنا.
# تشغيله مع كل Deploy قد يحذف إعلانات من قاعدة البيانات.
#
# database.remove_demo_listings()


# =========================================================
# HELPERS
# =========================================================

def allowed_file(filename):
    """
    يتأكد أن الملف له امتداد مسموح.
    """
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_UPLOAD_EXTENSIONS


def get_file_extension(filename):
    """
    يرجع امتداد الملف بدون النقطة.
    """
    if "." not in filename:
        return ""

    return filename.rsplit(".", 1)[1].lower()


def generate_unique_filename(original_filename, prefix="file"):
    """
    ينشئ اسم ملف فريد حتى لا تتعارض الملفات التي لها نفس الاسم.
    """
    extension = get_file_extension(original_filename)

    safe_name = secure_filename(original_filename)

    if not safe_name:
        safe_name = f"{prefix}.{extension}" if extension else prefix

    unique_id = uuid.uuid4().hex

    if extension:
        return f"{prefix}_{unique_id}.{extension}"

    return f"{prefix}_{unique_id}"


def save_uploaded_file(file, prefix="file"):
    """
    يحفظ الملف ويرجع المسار النسبي المستخدم في قاعدة البيانات.
    """
    if not file or not file.filename:
        return None

    if not allowed_file(file.filename):
        raise ValueError("نوع الملف غير مسموح.")

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    filename = generate_unique_filename(file.filename, prefix=prefix)

    file_path = os.path.join(UPLOAD_FOLDER, filename)

    file.save(file_path)

    return f"uploads/{filename}"


def get_media_type(filename):
    """
    يحدد هل الملف صورة أو فيديو.
    """
    extension = get_file_extension(filename)

    if extension in ALLOWED_VIDEO_EXTENSIONS:
        return "video"

    return "image"


def parse_optional_int(value, field_name):
    """
    يحول قيمة إلى int أو يرجع None.
    """
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} يجب أن يكون رقمًا صحيحًا.")

    return number


def parse_price(value):
    """
    يحول السعر إلى float مع التحقق منه.
    """
    if value is None:
        return 0.0

    value = str(value).strip()

    if not value:
        return 0.0

    try:
        price = float(value)
    except (TypeError, ValueError):
        raise ValueError("السعر غير صحيح.")

    if price < 0:
        raise ValueError("السعر لا يمكن أن يكون سالبًا.")

    return price


def current_user_id():
    """
    يرجع ID المستخدم الحالي أو None.
    """
    return session.get("user_id")


def login_required():
    """
    يفيد في التحقق السريع من تسجيل الدخول.
    """
    return "user_id" in session


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():
    listings = database.get_all_listings_with_first_media()

    return render_template(
        "index.html",
        listings=listings
    )


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()

        if not name:
            return render_template(
                "register.html",
                error="اكتب اسمك."
            )

        if not email:
            return render_template(
                "register.html",
                error="اكتب البريد الإلكتروني."
            )

        if not password:
            return render_template(
                "register.html",
                error="اكتب كلمة المرور."
            )

        if len(password) < 6:
            return render_template(
                "register.html",
                error="كلمة المرور يجب أن تكون 6 أحرف على الأقل."
            )

        try:
            conn = database.get_db()

            existing_user = conn.execute(
                "SELECT id FROM users WHERE lower(email) = ?",
                (email,)
            ).fetchone()

            if existing_user:
                conn.close()

                return render_template(
                    "register.html",
                    error="هذا البريد مسجل مسبقًا."
                )

            password_hash = generate_password_hash(password)

            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO users
                    (name, email, password_hash, phone)
                VALUES
                    (?, ?, ?, ?)
                RETURNING id
                """,
                (
                    name,
                    email,
                    password_hash,
                    phone
                )
            )

            row = cursor.fetchone()

            if not row:
                conn.close()
                raise Exception("تعذر إنشاء الحساب.")

            user_id = row["id"]

            conn.commit()
            conn.close()

            session.clear()

            session["user_id"] = user_id
            session["user_name"] = name

            return redirect(url_for("index"))

        except Exception as e:

            print("REGISTER ERROR:", str(e))

            return render_template(
                "register.html",
                error="حدث خطأ أثناء إنشاء الحساب. تأكد أن البريد غير مستخدم."
            )

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not email or not password:
            return render_template(
                "login.html",
                error="اكتب البريد وكلمة المرور."
            )

        conn = database.get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE lower(email) = ?
            """,
            (email,)
        ).fetchone()

        conn.close()

        if not user:
            return render_template(
                "login.html",
                error="البريد الإلكتروني أو كلمة المرور غير صحيحة."
            )

        stored_password = user["password_hash"] or ""

        password_valid = False

        # الحسابات القديمة في نسختك السابقة كانت تحفظ كلمة المرور
        # كنص عادي. ندعمها مؤقتًا ثم نحولها مباشرة إلى hash.
        try:
            password_valid = check_password_hash(
                stored_password,
                password
            )
        except (ValueError, TypeError):
            password_valid = False

        if not password_valid and stored_password == password:

            try:
                conn = database.get_db()

                new_hash = generate_password_hash(password)

                conn.execute(
                    """
                    UPDATE users
                    SET password_hash = ?
                    WHERE id = ?
                    """,
                    (
                        new_hash,
                        user["id"]
                    )
                )

                conn.commit()
                conn.close()

                password_valid = True

            except Exception as e:
                print("PASSWORD MIGRATION ERROR:", str(e))

        if not password_valid:
            return render_template(
                "login.html",
                error="البريد الإلكتروني أو كلمة المرور غير صحيحة."
            )

        session.clear()

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]

        return redirect(url_for("index"))

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("index"))


# =========================================================
# SELL
# =========================================================

@app.route("/sell", methods=["GET", "POST"])
def sell():

    if not login_required():
        return redirect(url_for("login"))

    if request.method == "POST":

        try:
            title = request.form.get(
                "title",
                "بدون عنوان"
            ).strip()

            category = request.form.get(
                "category",
                "عام"
            ).strip()

            price = parse_price(
                request.form.get("price")
            )

            city = request.form.get(
                "city",
                "غير محدد"
            ).strip()

            description = request.form.get(
                "description",
                ""
            ).strip()

            year = parse_optional_int(
                request.form.get("year"),
                "السنة"
            )

            mileage = parse_optional_int(
                request.form.get("mileage"),
                "الممشى"
            )

            make = request.form.get(
                "make"
            )

            model = request.form.get(
                "model"
            )

            make = make.strip() if make else None
            model = model.strip() if model else None

            if not title:
                return render_template(
                    "sell.html",
                    error="عنوان الإعلان مطلوب."
                )

            if year is not None and (
                year < 1900 or year > 2100
            ):
                return render_template(
                    "sell.html",
                    error="السنة غير صحيحة."
                )

            if mileage is not None and mileage < 0:
                return render_template(
                    "sell.html",
                    error="الممشى لا يمكن أن يكون سالبًا."
                )

            owner_id = session["user_id"]

            listing_id = database.add_listing(
                title,
                category,
                price,
                city,
                description,
                owner_id,
                year=year,
                mileage=mileage,
                make=make,
                model=model
            )

            os.makedirs(
                UPLOAD_FOLDER,
                exist_ok=True
            )

            files = request.files.getlist("images")

            uploaded_count = 0

            # حد أقصى 30 ملفًا للإعلان
            for file in files[:30]:

                if not file or not file.filename:
                    continue

                try:
                    relative_path = save_uploaded_file(
                        file,
                        prefix=f"listing_{listing_id}"
                    )

                    if not relative_path:
                        continue

                    media_type = get_media_type(
                        file.filename
                    )

                    database.add_listing_media(
                        listing_id,
                        media_type,
                        relative_path
                    )

                    uploaded_count += 1

                except ValueError as e:

                    print(
                        "UPLOAD SKIPPED:",
                        str(e)
                    )

                    continue

            return redirect(
                url_for(
                    "view_item",
                    item_id=listing_id
                )
            )

        except ValueError as e:

            print("SELL VALIDATION ERROR:", str(e))

            return render_template(
                "sell.html",
                error=str(e)
            )

        except Exception as e:

            print("SELL ERROR:", str(e))

            return render_template(
                "sell.html",
                error="حدث خطأ أثناء نشر الإعلان."
            )

    return render_template("sell.html")


# =========================================================
# LISTING
# =========================================================

@app.route("/listing/<int:item_id>")
def view_item(item_id):

    listing = database.get_listing(item_id)

    if not listing:
        return "الإعلان غير موجود", 404

    media = database.get_listing_media(item_id)

    messages = database.get_messages_for_listing(
        item_id
    )

    return render_template(
        "item.html",
        listing=listing,
        media=media,
        messages=messages
    )


# =========================================================
# SEND MESSAGE
# =========================================================

@app.route("/send-message", methods=["POST"])
def send_message():

    if not login_required():
        return redirect(url_for("login"))

    listing_id = request.form.get(
        "listing_id"
    )

    if not listing_id:
        return "الإعلان غير محدد", 400

    try:
        listing_id = int(listing_id)
    except ValueError:
        return "الإعلان غير صحيح", 400

    listing = database.get_listing(
        listing_id
    )

    if not listing:
        return "الإعلان غير موجود", 404

    sender_id = session["user_id"]

    sender_name = session.get(
        "user_name",
        "مستخدم"
    )

    message = request.form.get(
        "message",
        ""
    ).strip()

    try:
        is_private = int(
            request.form.get(
                "is_private",
                0
            )
        )
    except ValueError:
        is_private = 0

    receiver_id = request.form.get(
        "receiver_id"
    )

    if receiver_id:
        try:
            receiver_id = int(receiver_id)
        except ValueError:
            receiver_id = None

    if not receiver_id:
        receiver_id = listing["owner_id"]

    # منع إرسال رسالة للنفس
    if receiver_id == sender_id:

        if is_private == 1:
            return redirect(
                url_for("messages_inbox")
            )

        return redirect(
            url_for(
                "view_item",
                item_id=listing_id
            )
        )

    if message:

        # حد أقصى معقول للرسالة
        message = message[:5000]

        database.add_message(
            listing_id,
            sender_id,
            sender_name,
            receiver_id,
            message,
            is_private
        )

    if is_private == 1:
        return redirect(
            url_for("messages_inbox")
        )

    return redirect(
        url_for(
            "view_item",
            item_id=listing_id
        )
    )


# =========================================================
# MESSAGES
# =========================================================

@app.route("/messages")
def messages_inbox():

    if not login_required():
        return redirect(url_for("login"))

    messages = database.get_private_messages_for_user(
        session["user_id"]
    )

    return render_template(
        "messages.html",
        messages=messages
    )


# =========================================================
# SEARCH
# =========================================================

@app.route("/search")
def search():

    query = request.args.get(
        "q",
        ""
    ).strip().lower()

    category = request.args.get(
        "category",
        ""
    ).strip()

    connection = database.get_db()

    if query or category:

        conditions = []
        params = []

        if query:

            conditions.append(
                """
                (
                    lower(title) LIKE ?
                    OR lower(category) LIKE ?
                    OR lower(city) LIKE ?
                    OR lower(description) LIKE ?
                )
                """
            )

            search_value = f"%{query}%"

            params.extend([
                search_value,
                search_value,
                search_value,
                search_value
            ])

        if category and category not in (
            "all",
            "الكل",
            "كل"
        ):

            conditions.append(
                "category = ?"
            )

            params.append(category)

        where_clause = " AND ".join(
            conditions
        )

        listings = connection.execute(
            f"""
            SELECT listings.*,
                   (
                       SELECT file_path
                       FROM listing_media
                       WHERE listing_media.listing_id = listings.id
                       LIMIT 1
                   ) AS first_image
            FROM listings
            WHERE {where_clause}
            ORDER BY listings.id DESC
            """,
            tuple(params)
        ).fetchall()

    else:

        listings = (
            database
            .get_all_listings_with_first_media()
        )

    connection.close()

    return render_template(
        "index.html",
        listings=listings
    )


# =========================================================
# AI CHAT
# =========================================================

AI_CHAT_SESSION_KEY = "ai_chat_history"

AI_CHAT_MAX_TURNS = 4


@app.route("/ai", methods=["GET", "POST"])
def ai():

    error = None

    history = session.get(
        AI_CHAT_SESSION_KEY,
        []
    )

    if request.method == "POST":

        query = request.form.get(
            "query",
            ""
        ).strip()

        if query:

            try:

                filters = ai_assistant.extract_filters(
                    query
                )

                ai_message = ""

                turn_results = []

                if not filters.get(
                    "is_search",
                    False
                ):

                    ai_message = (
                        ai_assistant
                        .respond_general(query)
                    )

                else:

                    rows = (
                        database
                        .search_listings_smart(
                            filters,
                            limit=20
                        )
                    )

                    listings = [
                        dict(row)
                        for row in rows
                    ]

                    if listings:

                        ai_result = (
                            ai_assistant
                            .respond_with_listings(
                                query,
                                listings
                            )
                        )

                        ranking = (
                            ai_result.get(
                                "items",
                                []
                            )
                            if isinstance(
                                ai_result,
                                dict
                            )
                            else []
                        )

                        ai_message = (
                            ai_result.get(
                                "reply",
                                ""
                            )
                            if isinstance(
                                ai_result,
                                dict
                            )
                            else ""
                        )

                        reason_by_id = {}

                        ordered_ids = []

                        for result in ranking:

                            if not isinstance(
                                result,
                                dict
                            ):
                                continue

                            listing_id = result.get(
                                "id"
                            )

                            if listing_id is None:
                                continue

                            try:
                                listing_id = int(
                                    listing_id
                                )
                            except (
                                TypeError,
                                ValueError
                            ):
                                continue

                            ordered_ids.append(
                                listing_id
                            )

                            reason_by_id[
                                listing_id
                            ] = result.get(
                                "reason",
                                ""
                            )

                        listings_by_id = {
                            int(listing["id"]): listing
                            for listing in listings
                        }

                        ordered_results = []

                        already_added = set()

                        for listing_id in ordered_ids:

                            if listing_id not in listings_by_id:
                                continue

                            if listing_id in already_added:
                                continue

                            item = listings_by_id[
                                listing_id
                            ]

                            item["ai_reason"] = (
                                reason_by_id.get(
                                    listing_id,
                                    ""
                                )
                            )

                            ordered_results.append(
                                item
                            )

                            already_added.add(
                                listing_id
                            )

                        for item in listings:

                            listing_id = int(
                                item["id"]
                            )

                            if listing_id in already_added:
                                continue

                            item["ai_reason"] = ""

                            ordered_results.append(
                                item
                            )

                        top_results = (
                            ordered_results[:5]
                        )

                        turn_results = []

                        for item in top_results:

                            turn_results.append({
                                "id": item["id"],
                                "title": item["title"],
                                "price": item["price"],
                                "city": item["city"],
                                "first_image": item.get(
                                    "first_image"
                                ),
                                "ai_reason": item.get(
                                    "ai_reason",
                                    ""
                                ),
                            })

                    else:

                        ai_message = (
                            ai_assistant
                            .respond_no_results(
                                query
                            )
                        )

                history.append({
                    "query": query,
                    "ai_message": ai_message,
                    "results": turn_results,
                })

                history = history[
                    -AI_CHAT_MAX_TURNS:
                ]

                session[
                    AI_CHAT_SESSION_KEY
                ] = history

                session.modified = True

            except Exception as e:

                print(
                    "AI SEARCH ERROR:",
                    str(e)
                )

                error = (
                    "صار خطأ أثناء معالجة "
                    "طلبك بالذكاء الاصطناعي."
                )

        return redirect(
            url_for(
                "ai",
                error=error
            )
        )

    # نحافظ على error عند العودة للصفحة
    page_error = request.args.get(
        "error"
    )

    if page_error:
        error = page_error

    return render_template(
        "ai.html",
        history=history,
        error=error
    )


# =========================================================
# AI RESET
# =========================================================

@app.route("/ai/reset")
def ai_reset():

    session.pop(
        AI_CHAT_SESSION_KEY,
        None
    )

    return redirect(
        url_for("ai")
    )


# =========================================================
# EDIT LISTING
# =========================================================

@app.route(
    "/listing/<int:listing_id>/edit",
    methods=["GET", "POST"]
)
def edit_listing(listing_id):

    if not login_required():
        return redirect(url_for("login"))

    listing = database.get_listing(
        listing_id
    )

    if not listing:
        return "الإعلان غير موجود", 404

    if listing["owner_id"] != session["user_id"]:
        return "ما تملك صلاحية تعديل هذا الإعلان", 403

    if request.method == "POST":

        try:

            title = request.form.get(
                "title",
                listing["title"]
            ).strip()

            category = request.form.get(
                "category",
                listing["category"]
            ).strip()

            price_value = request.form.get(
                "price"
            )

            if price_value is None:
                price = float(
                    listing["price"] or 0
                )
            else:
                price = parse_price(
                    price_value
                )

            city = request.form.get(
                "city",
                listing["city"]
            ).strip()

            description = request.form.get(
                "description",
                listing["description"] or ""
            ).strip()

            year = parse_optional_int(
                request.form.get("year"),
                "السنة"
            )

            mileage = parse_optional_int(
                request.form.get("mileage"),
                "الممشى"
            )

            make = request.form.get(
                "make"
            )

            model = request.form.get(
                "model"
            )

            make = make.strip() if make else None
            model = model.strip() if model else None

            if not title:
                return render_template(
                    "edit_listing.html",
                    listing=listing,
                    error="عنوان الإعلان مطلوب."
                )

            if year is not None and (
                year < 1900 or year > 2100
            ):
                return render_template(
                    "edit_listing.html",
                    listing=listing,
                    error="السنة غير صحيحة."
                )

            if mileage is not None and mileage < 0:
                return render_template(
                    "edit_listing.html",
                    listing=listing,
                    error="الممشى غير صحيح."
                )

            database.update_listing(
                listing_id,
                title,
                category,
                price,
                city,
                description,
                year=year,
                mileage=mileage,
                make=make,
                model=model
            )

            return redirect(
                url_for("my_listings")
            )

        except ValueError as e:

            return render_template(
                "edit_listing.html",
                listing=listing,
                error=str(e)
            )

        except Exception as e:

            print(
                "EDIT LISTING ERROR:",
                str(e)
            )

            return render_template(
                "edit_listing.html",
                listing=listing,
                error="حدث خطأ أثناء تعديل الإعلان."
            )

    return render_template(
        "edit_listing.html",
        listing=listing
    )


# =========================================================
# DELETE LISTING
# =========================================================

@app.route(
    "/listing/<int:listing_id>/delete",
    methods=["POST"]
)
def remove_listing(listing_id):

    if not login_required():
        return redirect(url_for("login"))

    listing = database.get_listing(
        listing_id
    )

    if not listing:
        return "الإعلان غير موجود", 404

    if listing["owner_id"] != session["user_id"]:
        return "ما تملك صلاحية حذف هذا الإعلان", 403

    try:

        database.delete_listing(
            listing_id
        )

    except Exception as e:

        print(
            "DELETE LISTING ERROR:",
            str(e)
        )

        return "حدث خطأ أثناء حذف الإعلان", 500

    return redirect(
        url_for("my_listings")
    )


# =========================================================
# MY LISTINGS
# =========================================================

@app.route("/my-listings")
def my_listings():

    if not login_required():
        return redirect(url_for("login"))

    connection = database.get_db()

    listings = connection.execute(
        """
        SELECT listings.*,
               (
                   SELECT file_path
                   FROM listing_media
                   WHERE listing_media.listing_id = listings.id
                   LIMIT 1
               ) AS first_image
        FROM listings
        WHERE owner_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "my_listings.html",
        listings=listings
    )


# =========================================================
# PROFILE
# =========================================================

@app.route("/profile")
def profile():

    if not login_required():
        return redirect(url_for("login"))

    user = database.get_user(
        session["user_id"]
    )

    if not user:
        session.clear()

        return redirect(
            url_for("login")
        )

    listings_count = len(
        database.get_listings_by_owner(
            session["user_id"]
        )
    )

    return render_template(
        "profile.html",
        user=user,
        listings_count=listings_count
    )


# =========================================================
# UPDATE PROFILE
# =========================================================

@app.route(
    "/update-profile",
    methods=["POST"]
)
def update_profile():

    if not login_required():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    name = request.form.get(
        "name",
        ""
    ).strip()

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    bio = request.form.get(
        "bio",
        ""
    ).strip()

    if not name:
        return redirect(
            url_for("profile")
        )

    try:

        avatar_file = request.files.get(
            "avatar"
        )

        if (
            avatar_file
            and avatar_file.filename
        ):

            relative_path = save_uploaded_file(
                avatar_file,
                prefix=f"avatar_{user_id}"
            )

            if relative_path:

                database.update_user_avatar(
                    user_id,
                    relative_path
                )

        connection = database.get_db()

        connection.execute(
            """
            UPDATE users
            SET name = ?,
                phone = ?,
                bio = ?
            WHERE id = ?
            """,
            (
                name[:100],
                phone[:30],
                bio[:1000],
                user_id
            )
        )

        connection.commit()
        connection.close()

        session["user_name"] = name

    except ValueError as e:

        print(
            "PROFILE UPLOAD ERROR:",
            str(e)
        )

    except Exception as e:

        print(
            "UPDATE PROFILE ERROR:",
            str(e)
        )

    return redirect(
        url_for("profile")
    )


# =========================================================
# PUBLIC STORE
# =========================================================

@app.route("/store/<int:user_id>")
def store(user_id):

    seller = database.get_user(
        user_id
    )

    if not seller:
        return "المتجر غير موجود", 404

    listings = database.get_listings_by_owner(
        user_id
    )

    return render_template(
        "store.html",
        seller=seller,
        listings=listings
    )


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    return "حجم الملفات كبير جدًا. الحد الأقصى للطلب 100MB.", 413


@app.errorhandler(404)
def page_not_found(error):
    return "الصفحة غير موجودة", 404


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
        port=port
    )
