import os
import requests
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sallio.billing import bp
from sallio.models import get_business, upgrade_to_premium, can_generate_receipt, increment_receipt_quota

@bp.route('/upgrade')
@login_required
def upgrade():
    business = get_business(current_user.business_id)
    if business and business.get('plan_type') == 'premium':
        flash("You are already on the Premium plan!", "info")
        return redirect(url_for('main.dashboard'))
        
    paystack_public_key = os.environ.get('PAYSTACK_PUBLIC_KEY', '')
    return render_template('billing/upgrade.html', paystack_public_key=paystack_public_key, user_email=current_user.email or f"{current_user.phone}@sallio.app")

@bp.route('/verify', methods=['POST'])
@login_required
def verify():
    data = request.json
    reference = data.get('reference')
    if not reference:
        return jsonify({'status': 'error', 'message': 'No reference provided'}), 400
        
    secret_key = os.environ.get('PAYSTACK_SECRET_KEY')
    if not secret_key:
        return jsonify({'status': 'error', 'message': 'Server configuration error'}), 500
        
    headers = {
        'Authorization': f'Bearer {secret_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(f'https://api.paystack.co/transaction/verify/{reference}', headers=headers)
        response_data = response.json()
        
        if response_data.get('status') and response_data['data']['status'] == 'success':
            # Verification successful, upgrade the business
            upgrade_to_premium(current_user.business_id, reference)
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': 'Payment verification failed'}), 400
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/track_receipt', methods=['POST'])
@login_required
def track_receipt():
    if can_generate_receipt(current_user.business_id):
        increment_receipt_quota(current_user.business_id)
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Quota exceeded'}), 403

import hmac
import hashlib

@bp.route('/webhook', methods=['POST'])
def webhook():
    # Paystack sends the signature in the x-paystack-signature header
    paystack_signature = request.headers.get('x-paystack-signature')
    secret_key = os.environ.get('PAYSTACK_SECRET_KEY', '')
    
    # Verify the signature
    hash_obj = hmac.new(secret_key.encode('utf-8'), request.data, hashlib.sha512)
    if hash_obj.hexdigest() != paystack_signature:
        return jsonify({'status': 'error', 'message': 'Invalid signature'}), 400

    event = request.json
    # Handle subscription events (charge.success, subscription.create, etc.)
    # In a full implementation, this updates the subscription status in the DB
    # For now, just return 200 to acknowledge receipt
    
    return jsonify({'status': 'success'}), 200

