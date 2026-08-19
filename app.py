from flask import Flask, render_template, request, redirect, url_for, flash
import os
import json
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'lvreen_secure_key_2026'

UPLOAD_FOLDER = 'static/uploads'
DATA_FILE = 'listings.json'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# دالة لقراءة الإعلانات من الملف
def load_listings():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

# دالة لحفظ الإعلانات في الملف
def save_listings(listings):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(listings, f, ensure_ascii=False, indent=4)

@app.route('/')
def index():
    listings = load_listings()
    return render_template('index.html', listings=listings)

# مسار استقبال وتخزين الإعلانات
@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if request.method == 'POST':
        try:
            title = request.form.get('title', 'بدون عنوان')
            category = request.form.get('category', 'عام')
            sub_category = request.form.get('sub_category', '')
            model = request.form.get('model', '')
            price = request.form.get('price', '0')
            city = request.form.get('city', 'غير محدد')
            description = request.form.get('description', '')
            
            image_path = ''
            if 'images' in request.files:
                file = request.files['images']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image_path = f'uploads/{filename}'

            listings = load_listings()
            new_listing = {
                'id': len(listings) + 1,
                'title': title,
                'category': category,
                'sub_category': sub_category,
                'model': model,
                'price': float(price) if price else 0.0,
                'city': city,
                'description': description,
                'image_path': image_path
            }
            listings.append(new_listing)
            save_listings(listings)
            
            return redirect(url_for('index'))
        except Exception as e:
            print(f"Error: {e}")
            return redirect(url_for('sell'))
        
    return render_template('sell.html')

# مسار عرض تفاصيل الإعلان (متطابق مع تصميمك /listing/)
@app.route('/listing/<int:item_id>')
def view_item(item_id):
    listings = load_listings()
    listing = next((item for item in listings if item['id'] == item_id), None)
    
    if not listing:
        return "الإعلان غير موجود", 404
        
    return render_template('item.html', listing=listing)

# مسار البحث
@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    listings = load_listings()
    if query:
        filtered = [item for item in listings if query in item.get('title', '').lower() or query in item.get('category', '').lower() or query in item.get('city', '').lower()]
    else:
        filtered = listings
    return render_template('index.html', listings=filtered)

@app.route('/ai')
def ai_page():
    return render_template('ai.html')

@app.route('/my-listings')
def my_listings():
    listings = load_listings()
    return render_template('my_listings.html', listings=listings)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)