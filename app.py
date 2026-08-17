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

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if request.method == 'POST':
        try:
            title = request.form.get('title', '')
            category = request.form.get('category', '')
            sub_category = request.form.get('sub_category', '')
            model = request.form.get('model', '')
            price = request.form.get('price', '0')
            city = request.form.get('city', '')
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
            
            flash('تم نشر إعلانك بنجاح!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'حدث خطأ أثناء النشر: {str(e)}', 'error')
            return redirect(url_for('sell'))
        
    return render_template('sell.html')

@app.route('/item/<int:item_id>')
def view_item(item_id):
    listings = load_listings()
    listing = next((item for item in listings if item['id'] == item_id), None)
    
    if not listing:
        listing = {
            'id': item_id,
            'title': 'الإعلان غير موجود',
            'category': '-',
            'sub_category': '-',
            'model': '-',
            'price': '0',
            'city': '-',
            'description': 'عفواً، هذا الإعلان غير موجود أو تم حذفه.',
            'image_filename': ''
        }
        
    return render_template('item.html', listing=listing)

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