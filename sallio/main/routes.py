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
    from sallio.models import get_dashboard_stats, get_business
    stats = get_dashboard_stats(current_user.business_id)
    business = get_business(current_user.business_id)
    return render_template('dashboard.html', stats=stats, business=business)

@bp.route('/sale/new', methods=['GET', 'POST'])
@login_required
def new_sale():
    from sallio.models import get_products
    
    if request.method == 'POST':
        item_names = request.form.getlist('item_name[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')
        product_ids = request.form.getlist('product_id[]')
        payment_method = request.form.get('payment_method')
        customer_name = request.form.get('customer_name')
        customer_phone = request.form.get('customer_phone')
        
        items = []
        for i in range(len(item_names)):
            if item_names[i].strip():
                item_data = {
                    'name': item_names[i],
                    'quantity': quantities[i],
                    'price': prices[i]
                }
                # Safely get product_id if it exists for this row
                if i < len(product_ids) and product_ids[i].strip():
                    item_data['product_id'] = product_ids[i].strip()
                    
                items.append(item_data)
                
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
            
    products = get_products(current_user.business_id)
    return render_template('sale_new.html', products=products)

from sallio.models import get_sale, get_sales, get_business

@bp.route('/receipt/<receipt_number>')
@login_required
def receipt(receipt_number):
    sale = get_sale(receipt_number, current_user.business_id)
    if not sale:
        flash('Receipt not found or access denied.', 'error')
        return redirect(url_for('main.dashboard'))

    business = get_business(current_user.business_id)
    if not business:
        flash('Business not found.', 'error')
        return redirect(url_for('main.dashboard'))

    return render_template('receipt.html', sale=sale, business=business)


@bp.route('/receipt/<receipt_number>/print')
@login_required
def receipt_print(receipt_number):
    """Print-optimised view — Premium only. Auto-triggers browser print dialog."""
    business = get_business(current_user.business_id)
    if not business or business.get('plan_type') != 'premium':
        flash('PDF download is a Premium feature.', 'error')
        return redirect(url_for('main.receipt', receipt_number=receipt_number))

    sale = get_sale(receipt_number, current_user.business_id)
    if not sale:
        flash('Receipt not found.', 'error')
        return redirect(url_for('main.dashboard'))

    return render_template('receipt_print.html', sale=sale, business=business)


@bp.route('/history')
@login_required
def history():
    sales = get_sales(current_user.business_id)
    business = get_business(current_user.business_id)
    return render_template('history.html', sales=sales, business=business)

@bp.route('/products')
@login_required
def products():
    from sallio.models import get_product_stats
    products = get_product_stats(current_user.business_id, active_only=False)
    return render_template('products.html', products=products)

@bp.route('/products/new', methods=['POST'])
@login_required
def products_new():
    from sallio.models import create_product
    name = request.form.get('name')
    try:
        total_cost = float(request.form.get('total_cost', 0))
        unit_price = float(request.form.get('unit_price', 0))
    except ValueError:
        flash('Invalid cost or price values.', 'error')
        return redirect(url_for('main.products'))
        
    if not name:
        flash('Product name is required.', 'error')
        return redirect(url_for('main.products'))
        
    create_product(current_user.business_id, name, total_cost, unit_price)
    flash('Product created successfully!', 'success')
    return redirect(url_for('main.products'))

@bp.route('/products/<product_id>/sold_out', methods=['POST'])
@login_required
def product_sold_out(product_id):
    from sallio.models import mark_product_sold_out
    mark_product_sold_out(product_id, current_user.business_id)
    flash('Product marked as sold out.', 'success')
    return redirect(url_for('main.products'))

@bp.route('/products/<product_id>/delete', methods=['POST'])
@login_required
def product_delete(product_id):
    from sallio.models import delete_product
    delete_product(product_id, current_user.business_id)
    flash('Product deleted successfully.', 'success')
    return redirect(url_for('main.products'))
