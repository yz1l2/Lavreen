"""
Lavreen - Turso Database Layer

الاتصال بقاعدة Turso يتم عبر HTTP فقط باستخدام /v2/pipeline.
هذا يتجنب مشاكل WebSocket (wss://) التي قد تظهر على Render.

متغيرات البيئة المطلوبة:
- TURSO_DATABASE_URL
- TURSO_AUTH_TOKEN

ملاحظة:
Turso يدعم SQL متوافقًا مع SQLite/libSQL، لذلك بقية المشروع
يستطيع الاستمرار باستخدام نفس الدوال الموجودة هنا.
"""

import os
import requests


# =========================================================
# TURSO CONFIG
# =========================================================

TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "").strip()
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "").strip()

HTTP_TIMEOUT = 30


def _get_http_url():
    """
    يحول رابط Turso إلى رابط HTTPS عادي.

    أمثلة:
    libsql://example.turso.io
    ->
    https://example.turso.io
    """

    if not TURSO_URL:
        raise RuntimeError(
            "TURSO_DATABASE_URL غير موجود في Environment Variables."
        )

    url = TURSO_URL.rstrip("/")

    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://"):]

    elif url.startswith("https://"):
        pass

    elif url.startswith("http://"):
        # HTTPS مطلوب مع auth token.
        url = "https://" + url[len("http://"):]

    else:
        url = "https://" + url

    return url


def _pipeline_url():
    return _get_http_url() + "/v2/pipeline"


def _ensure_configured():
    if not TURSO_URL:
        raise RuntimeError(
            "TURSO_DATABASE_URL غير مضبوط."
        )

    if not TURSO_TOKEN:
        raise RuntimeError(
            "TURSO_AUTH_TOKEN غير مضبوط."
        )


# =========================================================
# VALUE CONVERSION
# =========================================================

def _python_to_turso(value):
    """
    يحول Python value إلى قيمة Hrana/Turso.
    """

    if value is None:
        return {
            "type": "null"
        }

    if isinstance(value, bool):
        return {
            "type": "integer",
            "value": "1" if value else "0"
        }

    if isinstance(value, int):
        return {
            "type": "integer",
            "value": str(value)
        }

    if isinstance(value, float):
        return {
            "type": "float",
            "value": value
        }

    if isinstance(value, bytes):
        return {
            "type": "blob",
            "value": value.hex()
        }

    return {
        "type": "text",
        "value": str(value)
    }


def _turso_to_python(value):
    """
    يحول قيمة Turso/SQLite إلى Python.
    """

    if value is None:
        return None

    if not isinstance(value, dict):
        return value

    value_type = value.get("type")
    raw_value = value.get("value")

    if value_type == "null":
        return None

    if value_type == "integer":
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return raw_value

    if value_type == "float":
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return raw_value

    if value_type == "blob":
        try:
            return bytes.fromhex(raw_value)
        except (TypeError, ValueError):
            return raw_value

    return raw_value


# =========================================================
# ROW
# =========================================================

class Row(dict):
    """
    يحاكي sqlite3.Row.

    يدعم:
        row["name"]
        row.name
        row[0]
    """

    def __init__(self, columns, values):
        super().__init__(
            zip(columns, values)
        )

        self._values = list(values)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __getitem__(self, key):

        if isinstance(key, int):
            return self._values[key]

        return dict.__getitem__(
            self,
            key
        )


# =========================================================
# RESULT
# =========================================================

class Result:
    """
    نتيجة استعلام داخلية.
    """

    def __init__(
        self,
        columns=None,
        rows=None,
        affected_rows=0,
        last_insert_rowid=None
    ):

        self.columns = columns or []

        self.rows = rows or []

        self.affected_rows = affected_rows

        self.last_insert_rowid = last_insert_rowid


# =========================================================
# CURSOR
# =========================================================

class Cursor:
    """
    غلاف يشبه sqlite3.Cursor حتى لا نحتاج
    إلى تغيير app.py وبقية المشروع.
    """

    def __init__(self, connection):
        self.connection = connection

        self._result = None

        self.lastrowid = None

        self.rowcount = -1

    def execute(self, sql, params=()):

        self._result = self.connection._execute(
            sql,
            params
        )

        self.lastrowid = (
            self._result.last_insert_rowid
        )

        self.rowcount = (
            self._result.affected_rows
        )

        return self

    def fetchone(self):

        if not self._result:
            return None

        if not self._result.rows:
            return None

        values = self._result.rows[0]

        return Row(
            self._result.columns,
            values
        )

    def fetchall(self):

        if not self._result:
            return []

        return [
            Row(
                self._result.columns,
                values
            )
            for values in self._result.rows
        ]


# =========================================================
# CONNECTION
# =========================================================

class Connection:
    """
    غلاف يشبه sqlite3.Connection.

    كل استعلام يذهب إلى Turso عبر HTTP POST
    إلى /v2/pipeline.

    لا يوجد WebSocket هنا.
    """

    def __init__(self):

        _ensure_configured()

        self.closed = False

        self.session = requests.Session()

        self.session.headers.update({
            "Authorization": f"Bearer {TURSO_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _execute(self, sql, params=()):

        if self.closed:
            raise RuntimeError(
                "محاولة استخدام اتصال قاعدة بيانات مغلق."
            )

        sql = str(sql).strip()

        if not sql:
            raise ValueError(
                "SQL query فارغ."
            )

        if params is None:
            params = []

        params = list(params)

        request_body = {
            "baton": None,
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": sql,
                        "args": [
                            _python_to_turso(value)
                            for value in params
                        ],
                        "named_args": [],
                        "want_rows": True,
                    },
                },
                {
                    "type": "close"
                }
            ]
        }

        try:

            response = self.session.post(
                _pipeline_url(),
                json=request_body,
                timeout=HTTP_TIMEOUT
            )

        except requests.RequestException as exc:

            raise RuntimeError(
                f"تعذر الاتصال بقاعدة Turso عبر HTTP: {exc}"
            ) from exc

        if not response.ok:

            body = response.text[:1000]

            raise RuntimeError(
                f"Turso HTTP Error {response.status_code}: {body}"
            )

        try:

            data = response.json()

        except ValueError as exc:

            raise RuntimeError(
                "Turso رجع استجابة ليست JSON."
            ) from exc

        results = data.get(
            "results",
            []
        )

        if not results:

            raise RuntimeError(
                "Turso لم يرجع نتيجة للاستعلام."
            )

        first_result = results[0]

        if first_result.get("type") == "error":

            error = first_result.get(
                "error",
                {}
            )

            message = (
                error.get("message")
                if isinstance(error, dict)
                else str(error)
            )

            raise RuntimeError(
                f"Turso SQL Error: {message}"
            )

        response_data = first_result.get(
            "response",
            {}
        )

        result_data = response_data.get(
            "result",
            {}
        )

        columns = result_data.get(
            "cols",
            []
        )

        # بعض إصدارات البروتوكول تعيد cols ككائنات.
        column_names = []

        for column in columns:

            if isinstance(column, dict):

                column_names.append(
                    column.get(
                        "name",
                        ""
                    )
                )

            else:

                column_names.append(
                    str(column)
                )

        raw_rows = result_data.get(
            "rows",
            []
        )

        rows = []

        for raw_row in raw_rows:

            converted = []

            for value in raw_row:

                converted.append(
                    _turso_to_python(value)
                )

            rows.append(converted)

        affected_rows = result_data.get(
            "affected_row_count",
            0
        )

        last_insert_rowid = result_data.get(
            "last_insert_rowid"
        )

        if last_insert_rowid is not None:

            try:
                last_insert_rowid = int(
                    last_insert_rowid
                )
            except (
                TypeError,
                ValueError
            ):
                pass

        return Result(
            columns=column_names,
            rows=rows,
            affected_rows=affected_rows,
            last_insert_rowid=last_insert_rowid
        )

    def execute(self, sql, params=()):

        return Cursor(self).execute(
            sql,
            params
        )

    def cursor(self):

        return Cursor(self)

    def commit(self):
        """
        الاستعلامات المنفذة عبر Turso HTTP تكون مطبقة
        مباشرة على قاعدة البيانات.

        نحتفظ بالدالة للتوافق مع app.py.
        """
        return None

    def rollback(self):
        """
        لا يوجد transaction مفتوح من خلال هذا الغلاف.
        الدالة موجودة فقط للتوافق.
        """
        return None

    def close(self):

        if not self.closed:

            try:
                self.session.close()
            except Exception:
                pass

            self.closed = True


# =========================================================
# GET DATABASE
# =========================================================

def get_db():
    return Connection()


# =========================================================
# CREATE DATABASE / MIGRATIONS
# =========================================================

def _column_exists(conn, table_name, column_name):

    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    for row in rows:

        if row["name"] == column_name:
            return True

    return False


def _add_column_if_missing(
    conn,
    table_name,
    column_name,
    column_definition
):

    if _column_exists(
        conn,
        table_name,
        column_name
    ):
        return

    conn.execute(
        f"""
        ALTER TABLE {table_name}
        ADD COLUMN {column_name} {column_definition}
        """
    )


def create_database():

    conn = get_db()

    try:

        # =================================================
        # USERS
        # =================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                phone TEXT,
                bio TEXT,
                avatar_path TEXT
            )
            """
        )

        _add_column_if_missing(
            conn,
            "users",
            "phone",
            "TEXT"
        )

        _add_column_if_missing(
            conn,
            "users",
            "bio",
            "TEXT"
        )

        _add_column_if_missing(
            conn,
            "users",
            "avatar_path",
            "TEXT"
        )

        # =================================================
        # LISTINGS
        # =================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                city TEXT NOT NULL,
                description TEXT,
                owner_id INTEGER,
                year INTEGER,
                mileage INTEGER,
                make TEXT,
                model TEXT,
                FOREIGN KEY (owner_id)
                    REFERENCES users(id)
            )
            """
        )

        _add_column_if_missing(
            conn,
            "listings",
            "year",
            "INTEGER"
        )

        _add_column_if_missing(
            conn,
            "listings",
            "mileage",
            "INTEGER"
        )

        _add_column_if_missing(
            conn,
            "listings",
            "make",
            "TEXT"
        )

        _add_column_if_missing(
            conn,
            "listings",
            "model",
            "TEXT"
        )

        # =================================================
        # LISTING MEDIA
        # =================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listing_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER,
                media_type TEXT,
                file_path TEXT,
                FOREIGN KEY (listing_id)
                    REFERENCES listings(id)
            )
            """
        )

        # =================================================
        # MESSAGES
        # =================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER,
                sender_id INTEGER,
                sender_name TEXT NOT NULL,
                receiver_id INTEGER,
                message TEXT NOT NULL,
                is_private INTEGER DEFAULT 0,
                created_at TIMESTAMP
                    DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (listing_id)
                    REFERENCES listings(id),
                FOREIGN KEY (sender_id)
                    REFERENCES users(id),
                FOREIGN KEY (receiver_id)
                    REFERENCES users(id)
            )
            """
        )

    finally:

        conn.close()


# =========================================================
# SAMPLE DATA
# =========================================================

def add_sample_listings():

    conn = get_db()

    try:

        count_row = conn.execute(
            "SELECT COUNT(*) AS count FROM listings"
        ).fetchone()

        count = count_row["count"]

        if count != 0:
            return

        conn.execute(
            """
            INSERT OR IGNORE INTO users
                (
                    id,
                    name,
                    email,
                    password_hash,
                    phone,
                    bio
                )
            VALUES
                (
                    1,
                    'متجر لافريين',
                    'test@lavreen.com',
                    '123456',
                    '0500000000',
                    'أهلاً بك في متجري الشخصي'
                )
            """
        )

        conn.execute(
            """
            INSERT INTO listings
                (
                    title,
                    category,
                    price,
                    city,
                    description,
                    owner_id,
                    year,
                    mileage,
                    make,
                    model
                )
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "تويوتا كامري 2022 نظيفة جداً",
                "سيارات",
                75000.0,
                "الرياض",
                "بنزين، قير أوتوماتيك، الموتر شرط الفحص والممشى معقول.",
                1,
                2022,
                45000,
                "تويوتا",
                "كامري"
            )
        )

    finally:

        conn.close()


# =========================================================
# ADD LISTING
# =========================================================

def add_listing(
    title,
    category,
    price,
    city,
    description,
    owner_id,
    year=None,
    mileage=None,
    make=None,
    model=None
):

    conn = get_db()

    try:

        row = conn.execute(
            """
            INSERT INTO listings
                (
                    title,
                    category,
                    price,
                    city,
                    description,
                    owner_id,
                    year,
                    mileage,
                    make,
                    model
                )
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                title,
                category,
                price,
                city,
                description,
                owner_id,
                year,
                mileage,
                make,
                model
            )
        ).fetchone()

        if not row:
            raise RuntimeError(
                "لم يتم إنشاء الإعلان."
            )

        return row["id"]

    finally:

        conn.close()


# =========================================================
# LISTING MEDIA
# =========================================================

def add_listing_media(
    listing_id,
    media_type,
    file_path
):

    conn = get_db()

    try:

        conn.execute(
            """
            INSERT INTO listing_media
                (
                    listing_id,
                    media_type,
                    file_path
                )
            VALUES
                (?, ?, ?)
            """,
            (
                listing_id,
                media_type,
                file_path
            )
        )

    finally:

        conn.close()


def get_listing_media(listing_id):

    conn = get_db()

    try:

        return conn.execute(
            """
            SELECT *
            FROM listing_media
            WHERE listing_id = ?
            ORDER BY id ASC
            """,
            (listing_id,)
        ).fetchall()

    finally:

        conn.close()


# =========================================================
# USERS
# =========================================================

def get_user(user_id):

    conn = get_db()

    try:

        return conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

    finally:

        conn.close()


def update_user_avatar(
    user_id,
    avatar_path
):

    conn = get_db()

    try:

        conn.execute(
            """
            UPDATE users
            SET avatar_path = ?
            WHERE id = ?
            """,
            (
                avatar_path,
                user_id
            )
        )

    finally:

        conn.close()


# =========================================================
# LISTINGS BY OWNER
# =========================================================

def get_listings_by_owner(owner_id):

    conn = get_db()

    try:

        return conn.execute(
            """
            SELECT listings.*,
                   (
                       SELECT file_path
                       FROM listing_media
                       WHERE listing_media.listing_id = listings.id
                       ORDER BY listing_media.id ASC
                       LIMIT 1
                   ) AS first_image
            FROM listings
            WHERE owner_id = ?
            ORDER BY id DESC
            """,
            (owner_id,)
        ).fetchall()

    finally:

        conn.close()


# =========================================================
# REMOVE DEMO LISTINGS
# =========================================================

def remove_demo_listings():
    """
    يحذف إعلانات العينة القديمة فقط.

    ملاحظة:
    لا يتم استدعاء هذه الدالة تلقائيًا عند تشغيل التطبيق.
    """

    demo_titles = [
        "تويوتا كامري 2022 نظيفة جداً",
        "تويوتا كامري 2023 فل كامل",
        "تويوتا كامري 2023 ستاندر",
        "آيفون 15 برو ماكس 256 جيجابايت",
        "شقة مفروشة للإيجار السنوي",
        "لابتوب الألعاب ASUS ROG Strix",
    ]

    conn = get_db()

    try:

        placeholders = ",".join(
            "?"
            for _ in demo_titles
        )

        conn.execute(
            f"""
            DELETE FROM listing_media
            WHERE listing_id IN (
                SELECT id
                FROM listings
                WHERE title IN ({placeholders})
            )
            """,
            demo_titles
        )

        conn.execute(
            f"""
            DELETE FROM messages
            WHERE listing_id IN (
                SELECT id
                FROM listings
                WHERE title IN ({placeholders})
            )
            """,
            demo_titles
        )

        conn.execute(
            f"""
            DELETE FROM listings
            WHERE title IN ({placeholders})
            """,
            demo_titles
        )

    finally:

        conn.close()


# =========================================================
# GET LISTING
# =========================================================

def get_listing(listing_id):

    conn = get_db()

    try:

        return conn.execute(
            """
            SELECT
                listings.*,
                users.name AS owner_name,
                users.avatar_path AS owner_avatar
            FROM listings
            LEFT JOIN users
                ON listings.owner_id = users.id
            WHERE listings.id = ?
            """,
            (listing_id,)
        ).fetchone()

    finally:

        conn.close()


# =========================================================
# UPDATE LISTING
# =========================================================

def update_listing(
    listing_id,
    title,
    category,
    price,
    city,
    description,
    year=None,
    mileage=None,
    make=None,
    model=None
):

    conn = get_db()

    try:

        conn.execute(
            """
            UPDATE listings
            SET
                title = ?,
                category = ?,
                price = ?,
                city = ?,
                description = ?,
                year = ?,
                mileage = ?,
                make = ?,
                model = ?
            WHERE id = ?
            """,
            (
                title,
                category,
                price,
                city,
                description,
                year,
                mileage,
                make,
                model,
                listing_id
            )
        )

    finally:

        conn.close()


# =========================================================
# DELETE LISTING
# =========================================================

def delete_listing(listing_id):

    conn = get_db()

    try:

        # الرسائل المرتبطة بالإعلان
        conn.execute(
            """
            DELETE FROM messages
            WHERE listing_id = ?
            """,
            (listing_id,)
        )

        # الوسائط المرتبطة بالإعلان
        conn.execute(
            """
            DELETE FROM listing_media
            WHERE listing_id = ?
            """,
            (listing_id,)
        )

        # الإعلان نفسه
        conn.execute(
            """
            DELETE FROM listings
            WHERE id = ?
            """,
            (listing_id,)
        )

    finally:

        conn.close()


# =========================================================
# ALL LISTINGS
# =========================================================

def get_all_listings_with_first_media():

    conn = get_db()

    try:

        return conn.execute(
            """
            SELECT
                listings.*,
                (
                    SELECT file_path
                    FROM listing_media
                    WHERE listing_media.listing_id = listings.id
                    ORDER BY listing_media.id ASC
                    LIMIT 1
                ) AS first_image
            FROM listings
            ORDER BY listings.id DESC
            """
        ).fetchall()

    finally:

        conn.close()


# =========================================================
# SMART SEARCH
# =========================================================

def search_listings_smart(
    filters,
    limit=20
):

    conditions = []

    params = []

    filters = filters or {}

    # -----------------------------------------------------
    # CATEGORY
    # -----------------------------------------------------

    category = filters.get(
        "category"
    )

    if category:

        conditions.append(
            "lower(category) LIKE ?"
        )

        params.append(
            f"%{str(category).lower()}%"
        )

    # -----------------------------------------------------
    # CITY
    # -----------------------------------------------------

    city = filters.get(
        "city"
    )

    if city:

        conditions.append(
            "lower(city) LIKE ?"
        )

        params.append(
            f"%{str(city).lower()}%"
        )

    # -----------------------------------------------------
    # KEYWORDS
    # -----------------------------------------------------

    keywords = filters.get(
        "keywords"
    )

    if keywords:

        keyword_conditions = []

        for keyword in keywords:

            if keyword is None:
                continue

            keyword = str(
                keyword
            ).strip()

            if not keyword:
                continue

            pattern = (
                f"%{keyword.lower()}%"
            )

            keyword_conditions.append(
                """
                (
                    lower(title) LIKE ?
                    OR lower(description) LIKE ?
                    OR lower(make) LIKE ?
                    OR lower(model) LIKE ?
                )
                """
            )

            params.extend([
                pattern,
                pattern,
                pattern,
                pattern
            ])

        if keyword_conditions:

            conditions.append(
                "("
                + " OR ".join(
                    keyword_conditions
                )
                + ")"
            )

    # -----------------------------------------------------
    # PRICE
    # -----------------------------------------------------

    min_price = filters.get(
        "min_price"
    )

    if min_price is not None:

        conditions.append(
            "price >= ?"
        )

        params.append(
            min_price
        )

    max_price = filters.get(
        "max_price"
    )

    if max_price is not None:

        conditions.append(
            "price <= ?"
        )

        params.append(
            max_price
        )

    # -----------------------------------------------------
    # YEAR
    # -----------------------------------------------------

    min_year = filters.get(
        "min_year"
    )

    if min_year is not None:

        conditions.append(
            "year >= ?"
        )

        params.append(
            min_year
        )

    max_year = filters.get(
        "max_year"
    )

    if max_year is not None:

        conditions.append(
            "year <= ?"
        )

        params.append(
            max_year
        )

    # -----------------------------------------------------
    # MILEAGE
    # -----------------------------------------------------

    max_mileage = filters.get(
        "max_mileage"
    )

    if max_mileage is not None:

        conditions.append(
            """
            (
                mileage IS NULL
                OR mileage <= ?
            )
            """
        )

        params.append(
            max_mileage
        )

    # -----------------------------------------------------
    # QUERY
    # -----------------------------------------------------

    if conditions:

        where_clause = (
            "WHERE "
            + " AND ".join(
                conditions
            )
        )

    else:

        where_clause = ""

    try:

        limit = int(limit)

    except (
        TypeError,
        ValueError
    ):

        limit = 20

    limit = max(
        1,
        min(limit, 100)
    )

    query = f"""
        SELECT
            listings.*,
            (
                SELECT file_path
                FROM listing_media
                WHERE listing_media.listing_id = listings.id
                ORDER BY listing_media.id ASC
                LIMIT 1
            ) AS first_image
        FROM listings
        {where_clause}
        ORDER BY listings.id DESC
        LIMIT ?
    """

    params.append(
        limit
    )

    conn = get_db()

    try:

        return conn.execute(
            query,
            params
        ).fetchall()

    finally:

        conn.close()


# =========================================================
# MESSAGES
# =========================================================

def add_message(
    listing_id,
    sender_id,
    sender_name,
    receiver_id,
    message,
    is_private
):

    conn = get_db()

    try:

        conn.execute(
            """
            INSERT INTO messages
                (
                    listing_id,
                    sender_id,
                    sender_name,
                    receiver_id,
                    message,
                    is_private
                )
            VALUES
                (?, ?, ?, ?, ?, ?)
            """,
            (
                listing_id,
                sender_id,
                sender_name,
                receiver_id,
                message,
                is_private
            )
        )

    finally:

        conn.close()


def get_messages_for_listing(
    listing_id
):

    conn = get_db()

    try:

        return conn.execute(
            """
            SELECT *
            FROM messages
            WHERE listing_id = ?
              AND is_private = 0
            ORDER BY id ASC
            """,
            (listing_id,)
        ).fetchall()

    finally:

        conn.close()


def get_private_messages_for_user(
    user_id
):

    conn = get_db()

    try:

        return conn.execute(
            """
            SELECT
                messages.*,
                listings.title AS listing_title
            FROM messages
            LEFT JOIN listings
                ON messages.listing_id = listings.id
            WHERE (
                messages.receiver_id = ?
                OR messages.sender_id = ?
            )
            AND messages.is_private = 1
            ORDER BY messages.id DESC
            """,
            (
                user_id,
                user_id
            )
        ).fetchall()

    finally:

        conn.close()
