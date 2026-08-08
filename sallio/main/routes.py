from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from bson.objectid import ObjectId
from sallio.main import bp
from sallio.models import create_sale

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    from sallio.models import get_dashboard_stats
    stats = get_dashboard_stats(current_user.business_id)
    return render_template('dashboard.html', stats=stats)

@bp.route('/sale/new', methods=['GET', 'POST'])
@login_required
def new_sale():
    if request.method == 'POST':
        item_names = request.form.getlist('item_name[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')
        payment_method = request.form.get('payment_method')
        customer_name = request.form.get('customer_name')
        customer_phone = request.form.get('customer_phone')
        
        items = []
        for i in range(len(item_names)):
            if item_names[i].strip():
                items.append({
                    'name': item_names[i],
                    'quantity': quantities[i],
                    'price': prices[i]
                })
                
        try:
            sale = create_sale(
                business_id=current_user.business_id,
                items=items,
                payment_method=payment_method,
                customer_name=customer_name,
                customer_phone=customer_phone
            )
            flash('Sale recorded successfully.', 'success')
            return redirect(url_for('main.receipt', receipt_number=sale['receipt_number']))
        except ValueError as e:
            flash(str(e), 'error')
            
    return render_template('sale_new.html')

from sallio.models import get_sale, get_sales

@bp.route('/receipt/<receipt_number>')
@login_required
def receipt(receipt_number):
    sale = get_sale(receipt_number, current_user.business_id)
    if not sale:
        flash('Receipt not found or access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Fetch business name from DB
    from sallio.db import get_db
    db = get_db()
    business = db.businesses.find_one({'_id': ObjectId(current_user.business_id)})
    business_name = business['name'] if business else 'Our Shop'
        
    # Generate WhatsApp message text
    items_text = ", ".join([f"{item['quantity']}x {item['name']}" for item in sale['items']])
    wa_msg = f"Receipt from {business_name}%0A" \
             f"Receipt: {sale['receipt_number']}%0A" \
             f"Total: NGN {sale['total']:,.2f}%0A" \
             f"Items: {items_text}%0A" \
             f"Thank you for your business!"
             
    return render_template('receipt.html', sale=sale, wa_msg=wa_msg, business_name=business_name)

@bp.route('/history')
@login_required
def history():
    sales = get_sales(current_user.business_id)
    return render_template('history.html', sales=sales)
