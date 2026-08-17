from flask import Flask, render_template, request, redirect, url_for, flash
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# مجلد حفظ الصور للإعلانات
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# قائمة مؤقتة لتخزين الإعلانات (أو قاعدة البيانات الخاصة بك)
# تأكد من ربطها بقاعدة البيانات الحقيقية لديك إذا كنت تستخدم SQLAlchemy
listings = []

@app.route('/')
def index():
    return render_template('index.html', listings=listings)

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        sub_category = request.form.get('sub_category')
        model = request.form.get('model')
        price = request.form.get('price')
        city = request.form.get('city')
        description = request.form.get('description')
        
        # معالجة رفع الصور
        image_filename = ''
        if 'images' in request.files:
            file = request.files['images']
            if file and file.filename != '':
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
                image_filename = file.filename

        # حفظ الإعلان (كمثال في القائمة المؤقتة مع إضافة ID رقمي)
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
        
    return render_template('sell.html')

# ⚠️ هذا هو المسار الجديد الخاص بفتح تفاصيل الإعلان والشات
@app.route('/item/<int:item_id>')
def view_item(item_id):
    # البحث عن الإعلان بواسطة الـ id الخاص به
    listing = next((item for item in listings if item['id'] == item_id), None)
    
    if not listing:
        # إذا لم يتم العثور على الإعلان (مثال تجريبي)
        listing = {
            'id': item_id,
            'title': 'إعلان تجريبي',
            'category': 'سيارات',
            'sub_category': 'تويوتا',
            'model': 'كامري',
            'price': '50,000',
            'city': 'الرياض',
            'description': 'هذا إعلان تجريبي للتأكد من عمل الصفحة والشات.',
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
    app.run(debug=True, port=10000)