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
        
        sample_listings = [
            ("تويوتا كامري 2022 نظيفة جداً", "سيارات", 75000.0, "الرياض", "بنزين، قير أوتوماتيك، الموتر شرط الفحص والممشى معقول.", 1),
            ("آيفون 15 برو ماكس 256 جيجابايت", "جوالات", 4200.0, "جدة", "الجهاز جديد بتغليف المصنع مع ضمان المشتري.", 1),
            ("شقة مفروشة للإيجار السنوي", "عقار", 30000.0, "الدمام", "غرفتين وصالة ومطبخ، مكيفات سبليت مطبخة بالكامل.", 1),
            ("لابتوب الألعاب ASUS ROG Strix", "كمبيوتر", 5500.0, "الرياض", "كرت شاشة RTX 4070 مع معالج قوي لأداء ممتاز في الألعاب والمنتجة.", 1)
        ]
        for title, category, price, city, description, owner_id in sample_listings:
            cursor.execute("""
                INSERT INTO listings (title, category, price, city, description, owner_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, category, price, city, description, owner_id))
        conn.commit()
    conn.close()

def add_listing(title, category, price, city, description, owner_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO listings (title, category, price, city, description, owner_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (title, category, price, city, description, owner_id))
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
    listing = conn.execute("SELECT listings.*, users.name as owner_name FROM listings LEFT JOIN users ON listings.owner_id = users.id WHERE listings.id = ?", (listing_id,)).fetchone()
    conn.close()
    return listing

def get_listing_media(listing_id):
    conn = get_db()
    media = conn.execute("SELECT * FROM listing_media WHERE listing_id = ?", (listing_id,)).fetchall()
    conn.close()
    return media

def get_all_listings_with_first_media():
    conn = get_db()
    # جلب الإعلانات مع أول صورة رئيسية لها لتظهر في الواجهة الرئيسية
    query = """
        SELECT listings.*, 
               (SELECT file_path FROM listing_media WHERE listing_media.listing_id = listings.id LIMIT 1) as first_image
        FROM listings 
        ORDER BY listings.id DESC
    """
    listings = conn.execute(query).fetchall()
    conn.close()
    return listings