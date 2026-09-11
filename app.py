from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from werkzeug.utils import secure_filename
import database
import ai_assistant

app = Flask(__name__)
app.secret_key = 'lvreen_secure_key_2026_real'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

database.create_database()
database.remove_demo_listings()  # يشيل إعلانات العينة القديمة لو كانت موجودة
# database.add_sample_listings()  # موقوفة عشان ما تنزرع إعلانات وهمية

@app.route('/')
def index():
    listings = database.get_all_listings_with_first_media()
    return render_template('index.html', listings=listings)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone', '')
        
        try:
            conn = database.get_db()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (name, email, password_hash, phone) VALUES (?, ?, ?, ?)", 
                           (name, email, password, phone))
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            
            session['user_id'] = user_id
            session['user_name'] = name
            return redirect(url_for('index'))
        except Exception as e:
            print("REGISTER ERROR:", str(e))
            return render_template('register.html', error=f"خطأ في التسجيل: {str(e)}")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = database.get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ? AND password_hash = ?", (email, password)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="البريد الإلكتروني أو كلمة المرور غير صحيحة.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        try:
            title = request.form.get('title', 'بدون عنوان')
            category = request.form.get('category', 'عام')
            price = request.form.get('price', '0')
            city = request.form.get('city', 'غير محدد')
            description = request.form.get('description', '')
            owner_id = session['user_id']

            # حقول اختيارية جديدة (مفيدة خصوصاً لتصنيف السيارات)
            year = request.form.get('year') or None
            mileage = request.form.get('mileage') or None
            make = request.form.get('make') or None
            model = request.form.get('model') or None
            year = int(year) if year else None
            mileage = int(mileage) if mileage else None

            listing_id = database.add_listing(
                title, category, float(price) if price else 0.0, city, description, owner_id,
                year=year, mileage=mileage, make=make, model=model
            )
            
            # استقبال حتى 30 صورة و 5 فيديوهات دفعة وحدة
            upload_path = os.path.join(app.root_path, 'static', 'uploads')
            os.makedirs(upload_path, exist_ok=True)
            
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(upload_path, filename)
                    file.save(file_path)
                    
                    # تحديد نوع الوسائط (صورة أو فيديو بناء على الامتداد)
                    ext = filename.lower().split('.')[-1]
                    media_type = 'video' if ext in ['mp4', 'mov', 'avi', 'mkv', 'webm'] else 'image'
                    
                    database.add_listing_media(listing_id, media_type, f'uploads/{filename}')
                    
            return redirect(url_for('index'))
        except Exception as e:
            print("SELL ERROR:", str(e))
            return f"حدث خطأ أثناء نشر الإعلان: {str(e)}"
    return render_template('sell.html')

@app.route('/listing/<int:item_id>')
def view_item(item_id):
    listing = database.get_listing(item_id)
    if not listing: 
        return "الإعلان غير موجود", 404
    media = database.get_listing_media(item_id)
    messages = database.get_messages_for_listing(item_id)
    return render_template('item.html', listing=listing, media=media, messages=messages)

@app.route('/send-message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    listing_id = request.form.get('listing_id')
    sender_id = session['user_id']
    sender_name = session['user_name']
    message = request.form.get('message')
    is_private = int(request.form.get('is_private', 0))
    
    receiver_id = request.form.get('receiver_id')
    if not receiver_id:
        listing = database.get_listing(listing_id)
        receiver_id = listing['owner_id'] if listing else 1
    
    if message:
        database.add_message(listing_id, sender_id, sender_name, receiver_id, message, is_private)
        
    if is_private == 1:
        return redirect(url_for('messages_inbox'))
    return redirect(url_for('view_item', item_id=listing_id))

@app.route('/messages')
def messages_inbox():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    messages = database.get_private_messages_for_user(session['user_id'])
    return render_template('messages.html', messages=messages)

@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    connection = database.get_db()
    if query:
        listings = connection.execute("""
            SELECT listings.*, 
                   (SELECT file_path FROM listing_media WHERE listing_media.listing_id = listings.id LIMIT 1) as first_image
            FROM listings 
            WHERE lower(title) LIKE ? OR lower(category) LIKE ? OR lower(city) LIKE ?
        """, (f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
    else:
        listings = database.get_all_listings_with_first_media()
    connection.close()
    return render_template('index.html', listings=listings)

@app.route('/ai', methods=['GET', 'POST'])
def ai():
    """
    مساعد بحث ذكي بالمحادثة:
    1. العميل يكتب طلبه بكلامه العادي
    2. Claude يستخرج فلاتر منظمة (سعر، سنة، ماشية، مدينة...)
    3. نفلتر قاعدة البيانات فعلياً بهالفلاتر (SQL)
    4. Claude يرتب النتائج ويشرح ليش كل خيار مناسب
    """
    query = ""
    results = []
    ai_message = None
    error = None

    if request.method == 'POST':
        query = request.form.get('query', '').strip()

        if query:
            try:
                # 1) استخراج الفلاتر من كلام العميل
                filters = ai_assistant.extract_filters(query)

                # 2) فلترة فعلية من قاعدة البيانات
                rows = database.search_listings_smart(filters, limit=20)
                listings = [dict(row) for row in rows]

                if listings:
                    # 3) ترتيب وشرح من Claude
                    ranking = ai_assistant.rank_listings(query, listings)
                    reason_by_id = {r["id"]: r.get("reason", "") for r in ranking if "id" in r}

                    # نرتب القائمة حسب ترتيب Claude، ونضيف السبب لكل عنصر
                    ordered_ids = [r["id"] for r in ranking if "id" in r]
                    listings_by_id = {l["id"]: l for l in listings}

                    ordered_results = []
                    for lid in ordered_ids:
                        if lid in listings_by_id:
                            item = listings_by_id[lid]
                            item["ai_reason"] = reason_by_id.get(lid, "")
                            ordered_results.append(item)
                    # أي عنصر ما رجع بالترتيب (احتياط) نضيفه بالآخر
                    for l in listings:
                        if l["id"] not in ordered_ids:
                            l["ai_reason"] = ""
                            ordered_results.append(l)

                    results = ordered_results
                    ai_message = f"لقيت لك {len(results)} إعلان يطابق طلبك، رتبتهم من الأنسب للأقل:"
                else:
                    results = []
                    ai_message = "ما لقيت إعلانات تطابق طلبك بالضبط، جرب تخفف الشروط شوي (زي الميزانية أو السنة)."

            except Exception as e:
                print("AI SEARCH ERROR:", str(e))
                error = "صار خطأ أثناء معالجة طلبك بالذكاء الاصطناعي. تأكد إن مفتاح API مضبوط صح."
                results = database.get_all_listings_with_first_media()
        else:
            results = database.get_all_listings_with_first_media()
    else:
        results = database.get_all_listings_with_first_media()

    return render_template('ai.html', query=query, results=results, ai_message=ai_message, error=error)

@app.route('/my-listings')
def my_listings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    connection = database.get_db()
    listings = connection.execute("""
        SELECT listings.*, 
               (SELECT file_path FROM listing_media WHERE listing_media.listing_id = listings.id LIMIT 1) as first_image
        FROM listings 
        WHERE owner_id = ? 
        ORDER BY id DESC
    """, (session['user_id'],)).fetchall()
    connection.close()
    return render_template('my_listings.html', listings=listings)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    connection = database.get_db()
    user = connection.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    connection.close()
    return render_template('profile.html', user=user)

@app.route('/update-profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    name = request.form.get('name', '')
    phone = request.form.get('phone', '')
    bio = request.form.get('bio', '')
    connection = database.get_db()
    connection.execute("UPDATE users SET name = ?, phone = ?, bio = ? WHERE id = ?", (name, phone, bio, session['user_id']))
    connection.commit()
    connection.close()
    session['user_name'] = name
    return redirect(url_for('profile'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)