from flask import Flask, render_template, request, redirect, url_for, flash
import os
from werkzeug.utils import secure_filename
import database  # استدعاء ملف قاعدة البيانات حقك

app = Flask(__name__)
app.secret_key = 'lvreen_secure_key_2026'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# التأكد من إنشاء قاعدة البيانات وإضافة البيانات التجريبية عند تشغيل التطبيق
database.create_database()
database.add_sample_listings()

@app.route('/')
def index():
    # جلب جميع الإعلانات مباشرة من قاعدة البيانات
    connection = database.get_db()
    listings = connection.execute("SELECT * FROM listings ORDER BY id DESC").fetchall()
    connection.close()
    return render_template('index.html', listings=listings)

# مسار استقبال وتخزين الإعلانات في قاعدة البيانات
@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if request.method == 'POST':
        try:
            title = request.form.get('title', 'بدون عنوان')
            category = request.form.get('category', 'عام')
            price = request.form.get('price', '0')
            city = request.form.get('city', 'غير محدد')
            description = request.form.get('description', '')
            
            # إضافة الإعلان لقاعدة البيانات
            listing_id = database.add_listing(
                title=title,
                category=category,
                price=float(price) if price else 0.0,
                city=city,
                description=description,
                owner_id=None
            )
            
            # معالجة رفع الصورة إن وجدت
            if 'images' in request.files:
                file = request.files['images']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    database.add_listing_media(listing_id, 'image', f'uploads/{filename}')

            return redirect(url_for('index'))
        except Exception as e:
            print(f"Error: {e}")
            return redirect(url_for('sell'))
        
    return render_template('sell.html')

# مسار عرض تفاصيل الإعلان (متطابق مع تصميمك /listing/)
@app.route('/listing/<int:item_id>')
def view_item(item_id):
    listing = database.get_listing(item_id)
    if not listing:
        return "الإعلان غير موجود", 404
        
    media = database.get_listing_media(item_id)
    return render_template('item.html', listing=listing, media=media)

# مسار البحث العام
@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    connection = database.get_db()
    if query:
        listings = connection.execute("""
            SELECT * FROM listings 
            WHERE lower(title) LIKE ? OR lower(category) LIKE ? OR lower(city) LIKE ?
        """, (f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
    else:
        listings = connection.execute("SELECT * FROM listings").fetchall()
    connection.close()
    return render_template('index.html', listings=listings)

# مسار الـ AI المحدث للبحث الذكي داخل قاعدة البيانات
@app.route('/ai', methods=['GET', 'POST'])
def ai():
    query = ""
    results = []
    if request.method == 'POST':
        query = request.form.get('query', '')
        if query:
            q_lower = f"%{query.lower()}%"
            connection = database.get_db()
            results = connection.execute("""
                SELECT * FROM listings 
                WHERE lower(title) LIKE ? 
                   OR lower(description) LIKE ? 
                   OR lower(category) LIKE ? 
                   OR lower(city) LIKE ?
            """, (q_lower, q_lower, q_lower, q_lower)).fetchall()
            connection.close()
        else:
            connection = database.get_db()
            results = connection.execute("SELECT * FROM listings").fetchall()
            connection.close()
            
    return render_template('ai.html', query=query, results=results)

@app.route('/my-listings')
def my_listings():
    connection = database.get_db()
    listings = connection.execute("SELECT * FROM listings ORDER BY id DESC").fetchall()
    connection.close()
    return render_template('my_listings.html', listings=listings)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)