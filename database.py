import sqlite3


DATABASE = "lavreen.db"


def get_db():

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    return connection


def create_database():

    connection = get_db()

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


def add_listing(
    title,
    category,
    price,
    city,
    description
):

    connection = get_db()

    connection.execute("""
        INSERT INTO listings
        (
            title,
            category,
            price,
            city,
            description
        )

        VALUES (?, ?, ?, ?, ?)
    """, (
        title,
        category,
        price,
        city,
        description
    ))

    connection.commit()

    connection.close()


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


def delete_listing(listing_id):

    connection = get_db()

    connection.execute("""
        DELETE FROM listings
        WHERE id = ?
    """, (listing_id,))

    connection.commit()

    connection.close()