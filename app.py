from flask import Flask, render_template, request, redirect, url_for, flash
import os
from werkzeug.utils import secure_filename
import database

app = Flask(__name__)
app.secret_key = 'lvreen_secure_key_2026'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

database.create_database()
database.add_sample_listings()

@app.route('/')
def index():
    connection = database.get_db()
    listings = connection.execute("SELECT * FROM listings ORDER BY id DESC").fetchall()
    connection.close()
    return render_template('index.html', listings=listings)

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if request.method == 'POST':
        try:
            title = request.form.get('title', 'بدون عنوان')
            category = request.form.get('category', 'عام')
            price = request.form.get('price', '0')
            city = request.form.get('city', 'غير محدد')
            description = request.form.get('description', '')
            
            listing_id = database.add_listing(title, category, float(price), city, description, owner_id=None)
            
            if 'images' in request.files:
                file = request.files['images']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    database.add_listing_media(listing_id, 'image', f'uploads/{filename}')
            return redirect(url_for('index'))
        except Exception as e:
            return redirect(url_for('sell'))
    return render_template('sell.html')

@app.route('/listing/<int:item_id>')
def view_item(item_id):
    listing = database.get_listing(item_id)
    if not listing: return "الإعلان غير موجود", 404
    media = database.get_listing_media(item_id)
    # جلب الرسائل العامة لهذا الإعلان
    messages = database.get_messages_for_listing(item_id)
    return render_template('item.html', listing=listing, media=media, messages=messages)

# مسارات الرسائل الجديدة
@app.route('/send-message', methods=['POST'])
def send_message():
    listing_id = request.form.get('listing_id')
    sender = request.form.get('sender_name', 'مستخدم')
    receiver = request.form.get('receiver_name', 'المعلن')
    message = request.form.get('message')
    is_private = int(request.form.get('is_private', 0))
    
    if message:
        database.add_message(listing_id, sender, receiver, message, is_private)
        
    if is_private == 1:
        return redirect(url_for('messages_inbox'))
    return redirect(url_for('view_item', item_id=listing_id))

@app.route('/messages')
def messages_inbox():
    messages = database.get_private_messages()
    return render_template('messages.html', messages=messages)

@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    connection = database.get_db()
    if query:
        listings = connection.execute("SELECT * FROM listings WHERE lower(title) LIKE ? OR lower(category) LIKE ? OR lower(city) LIKE ?", (f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
    else:
        listings = connection.execute("SELECT * FROM listings").fetchall()
    connection.close()
    return render_template('index.html', listings=listings)

@app.route('/ai', methods=['GET', 'POST'])
def ai():
    query = ""
    results = []
    if request.method == 'POST':
        query = request.form.get('query', '')
        if query:
            q_lower = f"%{query.lower()}%"
            connection = database.get_db()
            results = connection.execute("SELECT * FROM listings WHERE lower(title) LIKE ? OR lower(description) LIKE ? OR lower(category) LIKE ? OR lower(city) LIKE ?", (q_lower, q_lower, q_lower, q_lower)).fetchall()
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

@app.route('/profile')
def profile():
    connection = database.get_db()
    user = connection.execute("SELECT * FROM users LIMIT 1").fetchone()
    connection.close()
    if not user:
        connection = database.get_db()
        connection.execute("INSERT OR IGNORE INTO users (id, name, email, password_hash, phone, bio) VALUES (1, 'متجر لافريين', 'test@lavreen.com', '123456', '0500000000', 'أهلاً بك في متجري الشخصي')")
        connection.commit()
        connection.close()
        connection = database.get_db()
        user = connection.execute("SELECT * FROM users LIMIT 1").fetchone()
        connection.close()
    return render_template('profile.html', user=user)

@app.route('/update-profile', methods=['POST'])
def update_profile():
    name = request.form.get('name', '')
    phone = request.form.get('phone', '')
    bio = request.form.get('bio', '')
    connection = database.get_db()
    connection.execute("UPDATE users SET name = ?, phone = ?, bio = ? WHERE id = 1", (name, phone, bio))
    connection.commit()
    connection.close()
    return redirect(url_for('profile'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)