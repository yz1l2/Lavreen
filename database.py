import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "lavreen.db")


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():
    connection = get_db()

    # إنشاء جدول المستخدمين مع دعم الهاتف والبايو
    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            phone TEXT,
            bio TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # التحقق من وجود أعمدة الهاتف والبايو في الجداول القديمة
    user_columns = connection.execute(
        "PRAGMA table_info(users)"
    ).fetchall()
    user_column_names = [column["name"] for column in user_columns]

    if "phone" not in user_column_names:
        connection.execute("ALTER TABLE users ADD COLUMN phone TEXT")

    if "bio" not in user_column_names:
        connection.execute("ALTER TABLE users ADD COLUMN bio TEXT")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            city TEXT NOT NULL,
            description TEXT
        )
    """)

    columns = connection.execute(
        "PRAGMA table_info(listings)"
    ).fetchall()

    column_names = [column["name"] for column in columns]

    if "owner_id" not in column_names:
        connection.execute("""
            ALTER TABLE listings
            ADD COLUMN owner_id INTEGER
        """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS listing_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL,
            media_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_listings_owner_id
        ON listings(owner_id)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_listing_media_listing_id
        ON listing_media(listing_id)
    """)

    connection.commit()
    connection.close()


def add_sample_listings():
    connection = get_db()

    listings = [
        (
            "Toyota Camry 2022",
            "سيارات",
            61000,
            "الرياض",
            "GLE، ممشى 87,000 كم"
        ),
        (
            "iPhone 15 Pro",
            "جوالات",
            2850,
            "الرياض",
            "256GB، حالة ممتازة"
        ),
        (
            "Gaming PC RTX 4070",
            "كمبيوتر",
            4500,
            "الرياض",
            "Ryzen 7، 32GB RAM"
        ),
        (
            "PlayStation 5",
            "ألعاب",
            1650,
            "الرياض",
            "نسخة Disc، نظيف جدًا"
        )
    ]

    for listing in listings:
        connection.execute("""
            INSERT INTO listings
            (title, category, price, city, description)
            SELECT ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1
                FROM listings
                WHERE title = ?
            )
        """, (*listing, listing[0]))

    connection.commit()
    connection.close()


def create_user(name, email, password_hash):
    connection = get_db()

    try:
        cursor = connection.execute("""
            INSERT INTO users
            (name, email, password_hash)
            VALUES (?, ?, ?)
        """, (name, email, password_hash))

        user_id = cursor.lastrowid

        connection.commit()
        connection.close()

        return user_id

    except sqlite3.IntegrityError:
        connection.close()
        return None


def get_user_by_email(email):
    connection = get_db()

    user = connection.execute("""
        SELECT *
        FROM users
        WHERE email = ?
        LIMIT 1
    """, (email,)).fetchone()

    connection.close()

    return user


def get_user_by_id(user_id):
    connection = get_db()

    user = connection.execute("""
        SELECT *
        FROM users
        WHERE id = ?
        LIMIT 1
    """, (user_id,)).fetchone()

    connection.close()

    return user


def add_listing(
    title,
    category,
    price,
    city,
    description,
    owner_id=None
):
    connection = get_db()

    cursor = connection.execute("""
        INSERT INTO listings
        (
            title,
            category,
            price,
            city,
            description,
            owner_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        title,
        category,
        price,
        city,
        description,
        owner_id
    ))

    listing_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return listing_id


def get_listing(listing_id):
    connection = get_db()

    listing = connection.execute("""
        SELECT *
        FROM listings
        WHERE id = ?
        LIMIT 1
    """, (listing_id,)).fetchone()

    connection.close()

    return listing


def get_listings_by_owner(owner_id):
    connection = get_db()

    listings = connection.execute("""
        SELECT *
        FROM listings
        WHERE owner_id = ?
        ORDER BY id DESC
    """, (owner_id,)).fetchall()

    connection.close()

    return listings


def update_listing(
    listing_id,
    title,
    category,
    price,
    city,
    description
):
    connection = get_db()

    connection.execute("""
        UPDATE listings
        SET
            title = ?,
            category = ?,
            price = ?,
            city = ?,
            description = ?
        WHERE id = ?
    """, (
        title,
        category,
        price,
        city,
        description,
        listing_id
    ))

    connection.commit()
    connection.close()


def update_listing_for_owner(
    listing_id,
    owner_id,
    title,
    category,
    price,
    city,
    description
):
    connection = get_db()

    cursor = connection.execute("""
        UPDATE listings
        SET
            title = ?,
            category = ?,
            price = ?,
            city = ?,
            description = ?
        WHERE id = ?
        AND owner_id = ?
    """, (
        title,
        category,
        price,
        city,
        description,
        listing_id,
        owner_id
    ))

    changed = cursor.rowcount > 0

    connection.commit()
    connection.close()

    return changed


def delete_listing(listing_id):
    connection = get_db()

    media = connection.execute("""
        SELECT file_path
        FROM listing_media
        WHERE listing_id = ?
    """, (listing_id,)).fetchall()

    for item in media:
        filepath = os.path.join(
            BASE_DIR,
            "static",
            item["file_path"]
        )

        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass

    connection.execute("""
        DELETE FROM listing_media
        WHERE listing_id = ?
    """, (listing_id,))

    connection.execute("""
        DELETE FROM listings
        WHERE id = ?
    """, (listing_id,))

    connection.commit()
    connection.close()


def delete_listing_for_owner(listing_id, owner_id):
    connection = get_db()

    listing = connection.execute("""
        SELECT id
        FROM listings
        WHERE id = ?
        AND owner_id = ?
    """, (
        listing_id,
        owner_id
    )).fetchone()

    if listing is None:
        connection.close()
        return False

    media = connection.execute("""
        SELECT file_path
        FROM listing_media
        WHERE listing_id = ?
    """, (listing_id,)).fetchall()

    for item in media:
        filepath = os.path.join(
            BASE_DIR,
            "static",
            item["file_path"]
        )

        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass

    connection.execute("""
        DELETE FROM listing_media
        WHERE listing_id = ?
    """, (listing_id,))

    connection.execute("""
        DELETE FROM listings
        WHERE id = ?
        AND owner_id = ?
    """, (
        listing_id,
        owner_id
    ))

    connection.commit()
    connection.close()

    return True


def add_listing_media(
    listing_id,
    media_type,
    file_path,
    sort_order=0
):
    connection = get_db()

    connection.execute("""
        INSERT INTO listing_media
        (
            listing_id,
            media_type,
            file_path,
            sort_order
        )
        VALUES (?, ?, ?, ?)
    """, (
        listing_id,
        media_type,
        file_path,
        sort_order
    ))

    connection.commit()
    connection.close()


def get_listing_media(listing_id):
    connection = get_db()

    media = connection.execute("""
        SELECT *
        FROM listing_media
        WHERE listing_id = ?
        ORDER BY sort_order ASC, id ASC
    """, (listing_id,)).fetchall()

    connection.close()

    return media