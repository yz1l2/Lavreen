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

AI_CHAT_SESSION_KEY = 'ai_chat_history'
AI_CHAT_MAX_TURNS = 4  # نحتفظ بآخر 4 أسئلة بس عشان الكوكي ما يكبر كثير

@app.route('/ai', methods=['GET', 'POST'])
def ai():
    """
    مساعد بحث ذكي بشكل محادثة (شات):
    1. العميل يكتب طلبه بكلامه العادي
    2. Claude/الذكاء يستخرج فلاتر منظمة (سعر، سنة، ماشية، مدينة...)
    3. نفلتر قاعدة البيانات فعلياً بهالفلاتر (SQL)
    4. الذكاء يرتب النتائج ويشرح ليش كل خيار مناسب
    5. كل سؤال ورد يضاف كفقاعة محادثة، ويبقى محفوظ بالسيشن
    """
    error = None
    history = session.get(AI_CHAT_SESSION_KEY, [])

    if request.method == 'POST':
        query = request.form.get('query', '').strip()

        if query:
            try:
                # 1) استخراج الفلاتر من كلام العميل (ويحدد هل هذا أصلاً طلب بحث)
                filters = ai_assistant.extract_filters(query)

                ai_message = ""
                turn_results = []

                if not filters.get("is_search", False):
                    # مو طلب بحث (سلام، شكر، كلام عادي) - نرد بشكل طبيعي بدون ما نطلع أي منتجات
                    ai_message = ai_assistant.respond_general(query)

                else:
                    # 2) فلترة فعلية من قاعدة البيانات
                    rows = database.search_listings_smart(filters, limit=20)
                    listings = [dict(row) for row in rows]

                    if listings:
                        # 3) رد طبيعي + ترتيب من الذكاء بنفس الطلب
                        ai_result = ai_assistant.respond_with_listings(query, listings)
                        ranking = ai_result.get("items", [])
                        ai_message = ai_result.get("reply", "")

                        reason_by_id = {r["id"]: r.get("reason", "") for r in ranking if "id" in r}
                        ordered_ids = [r["id"] for r in ranking if "id" in r]
                        listings_by_id = {l["id"]: l for l in listings}

                        ordered_results = []
                        for lid in ordered_ids:
                            if lid in listings_by_id:
                                item = listings_by_id[lid]
                                item["ai_reason"] = reason_by_id.get(lid, "")
                                ordered_results.append(item)
                        for l in listings:
                            if l["id"] not in ordered_ids:
                                l["ai_reason"] = ""
                                ordered_results.append(l)

                        # نعرض بالشات أول 5 نتائج بس عشان يضل الشكل مرتب
                        top_results = ordered_results[:5]

                        # نخزن بالسيشن أهم الحقول بس (اسم، سعر، مدينة، سبب، صورة) عشان الكوكي ما يكبر
                        turn_results = [
                            {
                                "id": item["id"],
                                "title": item["title"],
                                "price": item["price"],
                                "city": item["city"],
                                "first_image": item.get("first_image"),
                                "ai_reason": item.get("ai_reason", ""),
                            }
                            for item in top_results
                        ]
                    else:
                        ai_message = ai_assistant.respond_no_results(query)

                history.append({
                    "query": query,
                    "ai_message": ai_message,
                    "results": turn_results,
                })
                history = history[-AI_CHAT_MAX_TURNS:]
                session[AI_CHAT_SESSION_KEY] = history

            except Exception as e:
                print("AI SEARCH ERROR:", str(e))
                error = "صار خطأ أثناء معالجة طلبك بالذكاء الاصطناعي. تأكد إن مفتاح API مضبوط صح وفيه رصيد."

        return redirect(url_for('ai'))

    return render_template('ai.html', history=history, error=error)


@app.route('/ai/reset')
def ai_reset():
    session.pop(AI_CHAT_SESSION_KEY, None)
    return redirect(url_for('ai'))

@app.route('/listing/<int:listing_id>/edit', methods=['GET', 'POST'])
def edit_listing(listing_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    listing = database.get_listing(listing_id)
    if not listing:
        return "الإعلان غير موجود", 404
    if listing['owner_id'] != session['user_id']:
        return "ما تملك صلاحية تعديل هذا الإعلان", 403

    if request.method == 'POST':
        title = request.form.get('title', listing['title'])
        category = request.form.get('category', listing['category'])
        price = request.form.get('price', listing['price'])
        city = request.form.get('city', listing['city'])
        description = request.form.get('description', listing['description'])
        year = request.form.get('year') or None
        mileage = request.form.get('mileage') or None
        make = request.form.get('make') or None
        model = request.form.get('model') or None
        year = int(year) if year else None
        mileage = int(mileage) if mileage else None

        database.update_listing(
            listing_id, title, category, float(price) if price else 0.0,
            city, description, year=year, mileage=mileage, make=make, model=model
        )
        return redirect(url_for('my_listings'))

    return render_template('edit_listing.html', listing=listing)

@app.route('/listing/<int:listing_id>/delete', methods=['POST'])
def remove_listing(listing_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    listing = database.get_listing(listing_id)
    if not listing:
        return "الإعلان غير موجود", 404
    if listing['owner_id'] != session['user_id']:
        return "ما تملك صلاحية حذف هذا الإعلان", 403

    database.delete_listing(listing_id)
    return redirect(url_for('my_listings'))

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
    user = database.get_user(session['user_id'])
    listings_count = len(database.get_listings_by_owner(session['user_id']))
    return render_template('profile.html', user=user, listings_count=listings_count)

@app.route('/update-profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    name = request.form.get('name', '')
    phone = request.form.get('phone', '')
    bio = request.form.get('bio', '')

    # رفع صورة البروفايل/المتجر لو المستخدم اختار صورة جديدة
    avatar_file = request.files.get('avatar')
    if avatar_file and avatar_file.filename != '':
        upload_path = os.path.join(app.root_path, 'static', 'uploads')
        os.makedirs(upload_path, exist_ok=True)
        filename = secure_filename(f"avatar_{session['user_id']}_{avatar_file.filename}")
        avatar_file.save(os.path.join(upload_path, filename))
        database.update_user_avatar(session['user_id'], f'uploads/{filename}')

    connection = database.get_db()
    connection.execute("UPDATE users SET name = ?, phone = ?, bio = ? WHERE id = ?", (name, phone, bio, session['user_id']))
    connection.commit()
    connection.close()
    session['user_name'] = name
    return redirect(url_for('profile'))

@app.route('/store/<int:user_id>')
def store(user_id):
    """صفحة المتجر العامة لأي بائع - يقدر أي زائر يشوفها"""
    seller = database.get_user(user_id)
    if not seller:
        return "المتجر غير موجود", 404
    listings = database.get_listings_by_owner(user_id)
    return render_template('store.html', seller=seller, listings=listings)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)