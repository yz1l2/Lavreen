from flask import Flask, render_template, request, redirect, url_for, flash
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'lvreen_secure_key_2026'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# قائمة لتخزين الإعلانات
listings = []

@app.route('/')
def index():
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
                    # تأمين اسم الملف عشان ما يعطيني إيرور
                    filename = secure_filename(file.filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image_filename = filename

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
            
            flash('تم نشر إعلانك بنجاح!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'حدث خطأ أثناء النشر: {str(e)}', 'error')
            return redirect(url_for('sell'))
        
    return render_template('sell.html')

@app.route('/item/<int:item_id>')
def view_item(item_id):
    listing = next((item for item in listings if item['id'] == item_id), None)
    
    if not listing:
        # إعلان افتراضي عشان ما يعطي 404 لو ما انوجد بالذاكرة
        listing = {
            'id': item_id,
            'title': 'إعلان غير موجود أو تم تحديث الصفحة',
            'category': 'عام',
            'sub_category': 'غير محدد',
            'model': '-',
            'price': '0',
            'city': '-',
            'description': 'عفواً، قد تكون الذاكرة أُعيد تشغيلها. يرجى إضافة إعلان جديد.',
            'image_filename': ''
        }
        
    return render_template('item.html', listing=listing)

@app.route('/ai')
def ai_page():
    return render_template('ai.html')

@app.route('/my-listings')
def my_listings():
    return render_template('my_listings.html', listings=listings)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)