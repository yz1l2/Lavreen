from flask import Flask, render_template, request, redirect, url_for, flash
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# قائمة تخزين الإعلانات مؤقتاً
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
        
        image_filename = ''
        if 'images' in request.files:
            file = request.files['images']
            if file and file.filename != '':
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
                image_filename = file.filename

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

# مسار تفاصيل الإعلان الفردي
@app.route('/item/<int:item_id>')
def view_item(item_id):
    listing = next((item for item in listings if item['id'] == item_id), None)
    
    if not listing:
        listing = {
            'id': item_id,
            'title': 'إعلان تجريبي',
            'category': 'سيارات',
            'sub_category': 'تويوتا',
            'model': 'كامري',
            'price': '50,000',
            'city': 'الرياض',
            'description': 'هذا إعلان تجريبي للتأكد من عمل الصفحة.',
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