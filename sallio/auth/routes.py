from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from sallio.auth import bp
from sallio.models import create_user_and_business, verify_user

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        business_name = request.form.get('business_name')
        owner_name = request.form.get('owner_name')
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        # Simple validation
        if not all([business_name, owner_name, phone, password]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('auth.register'))
            
        # Check if phone already exists (simplified for MVP, should be in models)
        from sallio.models import User
        if User.find_by_phone(phone):
            flash('An account with this phone number already exists.', 'error')
            return redirect(url_for('auth.register'))
            
        user = create_user_and_business(owner_name, phone, password, business_name)
        login_user(user)
        flash('Registration successful! Welcome to Sallio.', 'success')
        return redirect(url_for('main.dashboard'))
        
    return render_template('auth/register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        user = verify_user(phone, password)
        if user:
            login_user(user)
            return redirect(url_for('main.dashboard'))
            
        flash('Invalid phone number or password.', 'error')
        
    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))
