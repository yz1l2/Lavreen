from flask import Flask, render_template, request, redirect, url_for, flash
import os
import json
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'lvreen_final_secret_2026'

UPLOAD_FOLDER = 'static/uploads'
DATA_FILE = 'listings.json'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def load_listings():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_listings(listings):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(listings, f, ensure_ascii=False, indent=4)

@app.route('/')
def index():
    listings = load_listings()
    return render_template('index.html', listings=listings)

# مسار استقبال وتخزين الإعلانات (مع حماية كاملة ضد الإيرور)
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
            
            image_filename = ''
            if 'images' in request.files:
                file = request.files['images']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image_filename = filename

            listings = load_listings()
            new_listing = {
                'id': len(listings) + 1,
                'title': title,
                'category': category,
                'sub_category': sub_category,
                'model': model,
                'price': price,
                'city': city,
                'description': description,
                'image_filename': image_filename
            }
            listings.append(new_listing)
            save_listings(listings)
            
            return redirect(url_for('index'))
        except Exception as e:
            print(f"Error publishing listing: {e}")
            return redirect(url_for('sell'))
        
    return render_template('sell.html')

# مسار تفاصيل الإعلان الفردي
@app.route('/item/<int:item_id>')
def view_item(item_id):
    listings = load_listings()
    listing = next((item for item in listings if item['id'] == item_id), None)
    
    if not listing:
        listing = {
            'id': item_id,
            'title': 'إعلان غير موجود',
            'category': '-',
            'sub_category': '-',
            'model': '-',
            'price': '0',
            'city': '-',
            'description': 'عفواً، هذا الإعلان غير موجود.',
            'image_filename': ''
        }
        
    return render_template('item.html', listing=listing)

# مسارات الأزرار الـ 5 (تصنيفات السوق اللي بالصورة) عشان ما تعطي 404 أبد
@app.route('/category/<cat_name>')
def show_category(cat_name):
    listings = load_listings()
    # تصفية الإعلانات حسب التصنيف المضغط
    filtered = [item for item in listings if item.get('category') == cat_name or cat_name in item.get('title', '')]
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