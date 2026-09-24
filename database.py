import sqlite3

DB_NAME = "lavreen.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def create_database():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            phone TEXT,
            bio TEXT
        )
    """)

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN bio TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_path TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            city TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER,
            FOREIGN KEY (owner_id) REFERENCES users (id)
        )
    """)

    # ===== أعمدة جديدة لدعم البحث الذكي (خصوصاً السيارات) =====
    # كل عمود نضيفه بـ try/except عشان ما يسبب خطأ لو موجود مسبقاً
    for column_def in [
        "ALTER TABLE listings ADD COLUMN year INTEGER",
        "ALTER TABLE listings ADD COLUMN mileage INTEGER",
        "ALTER TABLE listings ADD COLUMN make TEXT",
        "ALTER TABLE listings ADD COLUMN model TEXT",
    ]:
        try:
            cursor.execute(column_def)
        except sqlite3.OperationalError:
            pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listing_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER,
            media_type TEXT,
            file_path TEXT,
            FOREIGN KEY (listing_id) REFERENCES listings (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER,
            sender_id INTEGER,
            sender_name TEXT NOT NULL,
            receiver_id INTEGER,
            message TEXT NOT NULL,
            is_private INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (listing_id) REFERENCES listings (id),
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id)
        )
    """)

    conn.commit()
    conn.close()

def add_sample_listings():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM listings")
    count = cursor.fetchone()[0]

    if count == 0:
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, name, email, password_hash, phone, bio)
            VALUES (1, 'متجر لافريين', 'test@lavreen.com', '123456', '0500000000', 'أهلاً بك في متجري الشخصي')
        """ )

        # (title, category, price, city, description, owner_id, year, mileage, make, model)
        sample_listings = [
            ("تويوتا كامري 2022 نظيفة جداً", "سيارات", 75000.0, "الرياض",
             "بنزين، قير أوتوماتيك، الموتر شرط الفحص والممشى معقول.", 1, 2022, 45000, "تويوتا", "كامري"),
            ("تويوتا كامري 2023 فل كامل", "سيارات", 98000.0, "جدة",
             "ماشية قليلة جداً، فحص كامل، لا حوادث.", 1, 2023, 12000, "تويوتا", "كامري"),
            ("تويوتا كامري 2023 ستاندر", "سيارات", 88000.0, "الرياض",
             "ماشية 20 ألف كم، صيانة الوكالة.", 1, 2023, 20000, "تويوتا", "كامري"),
            ("آيفون 15 برو ماكس 256 جيجابايت", "جوالات", 4200.0, "جدة",
             "الجهاز جديد بتغليف المصنع مع ضمان المشتري.", 1, None, None, None, None),
            ("شقة مفروشة للإيجار السنوي", "عقار", 30000.0, "الدمام",
             "غرفتين وصالة ومطبخ، مكيفات سبليت مطبخة بالكامل.", 1, None, None, None, None),
            ("لابتوب الألعاب ASUS ROG Strix", "كمبيوتر", 5500.0, "الرياض",
             "كرت شاشة RTX 4070 مع معالج قوي لأداء ممتاز في الألعاب والمنتجة.", 1, None, None, None, None),
        ]
        for title, category, price, city, description, owner_id, year, mileage, make, model in sample_listings:
            cursor.execute("""
                INSERT INTO listings (title, category, price, city, description, owner_id, year, mileage, make, model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, category, price, city, description, owner_id, year, mileage, make, model))
        conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def update_user_avatar(user_id, avatar_path):
    conn = get_db()
    conn.execute("UPDATE users SET avatar_path = ? WHERE id = ?", (avatar_path, user_id))
    conn.commit()
    conn.close()

def get_listings_by_owner(owner_id):
    conn = get_db()
    listings = conn.execute("""
        SELECT listings.*,
               (SELECT file_path FROM listing_media WHERE listing_media.listing_id = listings.id LIMIT 1) as first_image
        FROM listings
        WHERE owner_id = ?
        ORDER BY id DESC
    """, (owner_id,)).fetchall()
    conn.close()
    return listings

def remove_demo_listings():
    """يحذف إعلانات العينة التجريبية (لو كانت انزرعت بقاعدة بياناتك سابقاً)."""
    demo_titles = [
        "تويوتا كامري 2022 نظيفة جداً",
        "تويوتا كامري 2023 فل كامل",
        "تويوتا كامري 2023 ستاندر",
        "آيفون 15 برو ماكس 256 جيجابايت",
        "شقة مفروشة للإيجار السنوي",
        "لابتوب الألعاب ASUS ROG Strix",
    ]
    conn = get_db()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in demo_titles)
    # نحذف الوسائط المرتبطة أولاً، ثم الإعلانات نفسها
    cursor.execute(f"""
        DELETE FROM listing_media
        WHERE listing_id IN (SELECT id FROM listings WHERE title IN ({placeholders}))
    """, demo_titles)
    cursor.execute(f"DELETE FROM listings WHERE title IN ({placeholders})", demo_titles)
    conn.commit()
    conn.close()

def add_listing(title, category, price, city, description, owner_id,
                 year=None, mileage=None, make=None, model=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO listings (title, category, price, city, description, owner_id, year, mileage, make, model)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, category, price, city, description, owner_id, year, mileage, make, model))
    listing_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return listing_id

def add_listing_media(listing_id, media_type, file_path):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO listing_media (listing_id, media_type, file_path)
        VALUES (?, ?, ?)
    """, (listing_id, media_type, file_path))
    conn.commit()
    conn.close()

def get_listing(listing_id):
    conn = get_db()
    listing = conn.execute("""
        SELECT listings.*, users.name as owner_name, users.avatar_path as owner_avatar
        FROM listings
        LEFT JOIN users ON listings.owner_id = users.id
        WHERE listings.id = ?
    """, (listing_id,)).fetchone()
    conn.close()
    return listing

def update_listing(listing_id, title, category, price, city, description,
                    year=None, mileage=None, make=None, model=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE listings
        SET title = ?, category = ?, price = ?, city = ?, description = ?,
            year = ?, mileage = ?, make = ?, model = ?
        WHERE id = ?
    """, (title, category, price, city, description, year, mileage, make, model, listing_id))
    conn.commit()
    conn.close()

def delete_listing(listing_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM listing_media WHERE listing_id = ?", (listing_id,))
    cursor.execute("DELETE FROM messages WHERE listing_id = ?", (listing_id,))
    cursor.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
    conn.commit()
    conn.close()

def get_listing_media(listing_id):
    conn = get_db()
    media = conn.execute("SELECT * FROM listing_media WHERE listing_id = ?", (listing_id,)).fetchall()
    conn.close()
    return media

def get_all_listings_with_first_media():
    conn = get_db()
    query = """
        SELECT listings.*, 
               (SELECT file_path FROM listing_media WHERE listing_media.listing_id = listings.id LIMIT 1) as first_image
        FROM listings 
        ORDER BY listings.id DESC
    """
    listings = conn.execute(query).fetchall()
    conn.close()
    return listings

# ===== البحث الذكي: يبني استعلام SQL ديناميكي بناءً على الفلاتر اللي يستخرجها Claude =====
def search_listings_smart(filters, limit=20):
    """
    filters: dict ممكن يحتوي على:
      category, keywords (list[str]), city,
      min_price, max_price, min_year, max_year, max_mileage
    """
    conditions = []
    params = []

    if filters.get("category"):
        conditions.append("lower(category) LIKE ?")
        params.append(f"%{filters['category'].lower()}%")

    if filters.get("city"):
        conditions.append("lower(city) LIKE ?")
        params.append(f"%{filters['city'].lower()}%")

    if filters.get("keywords"):
        keyword_conditions = []
        for kw in filters["keywords"]:
            keyword_conditions.append("(lower(title) LIKE ? OR lower(description) LIKE ? OR lower(make) LIKE ? OR lower(model) LIKE ?)")
            kw_pattern = f"%{kw.lower()}%"
            params.extend([kw_pattern, kw_pattern, kw_pattern, kw_pattern])
        if keyword_conditions:
            conditions.append("(" + " OR ".join(keyword_conditions) + ")")

    if filters.get("min_price") is not None:
        conditions.append("price >= ?")
        params.append(filters["min_price"])

    if filters.get("max_price") is not None:
        conditions.append("price <= ?")
        params.append(filters["max_price"])

    if filters.get("min_year") is not None:
        conditions.append("year >= ?")
        params.append(filters["min_year"])

    if filters.get("max_year") is not None:
        conditions.append("year <= ?")
        params.append(filters["max_year"])

    if filters.get("max_mileage") is not None:
        conditions.append("(mileage IS NULL OR mileage <= ?)")
        params.append(filters["max_mileage"])

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT listings.*,
               (SELECT file_path FROM listing_media WHERE listing_media.listing_id = listings.id LIMIT 1) as first_image
        FROM listings
        {where_clause}
        ORDER BY listings.id DESC
        LIMIT ?
    """
    params.append(limit)

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows

# دوال الرسائل والدردشة
def add_message(listing_id, sender_id, sender_name, receiver_id, message, is_private):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO messages (listing_id, sender_id, sender_name, receiver_id, message, is_private)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (listing_id, sender_id, sender_name, receiver_id, message, is_private))
    conn.commit()
    conn.close()

def get_messages_for_listing(listing_id):
    conn = get_db()
    messages = conn.execute("""
        SELECT * FROM messages 
        WHERE listing_id = ? AND is_private = 0 
        ORDER BY id ASC
    """, (listing_id,)).fetchall()
    conn.close()
    return messages

def get_private_messages_for_user(user_id):
    conn = get_db()
    messages = conn.execute("""
        SELECT messages.*, listings.title as listing_title 
        FROM messages 
        LEFT JOIN listings ON messages.listing_id = listings.id
        WHERE (messages.receiver_id = ? OR messages.sender_id = ?) AND messages.is_private = 1
        ORDER BY messages.id DESC
    """, (user_id, user_id)).fetchall()
    conn.close()
    return messages