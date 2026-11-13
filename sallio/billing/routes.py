import os
import hmac
import hashlib
import requests
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from bson import ObjectId
from sallio.billing import bp
from sallio.models import (
    get_db,
    get_business,
    upgrade_to_premium,
    downgrade_to_free,
    can_generate_receipt,
    increment_receipt_quota
)

@bp.route('/upgrade')
@login_required
def upgrade():
    business = get_business(current_user.business_id)
    if business and business.get('plan_type') == 'premium':
        flash("You are already on the Premium plan!", "info")
        return redirect(url_for('main.dashboard'))
        
    paystack_public_key = os.environ.get('PAYSTACK_PUBLIC_KEY', '')
    paystack_plan_code = os.environ.get('PAYSTACK_PLAN_CODE', '')
    
    return render_template(
        'billing/upgrade.html',
        paystack_public_key=paystack_public_key,
        paystack_plan_code=paystack_plan_code,
        user_email=current_user.email or f"{current_user.phone}@sallio.app",
        business_id=str(current_user.business_id)
    )

@bp.route('/verify', methods=['POST'])
@login_required
def verify():
    data = request.json or {}
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
        response = requests.get(f'https://api.paystack.co/transaction/verify/{reference}', headers=headers, timeout=10)
        response_data = response.json()
        
        if response_data.get('status') and response_data.get('data', {}).get('status') == 'success':
            tx_data = response_data['data']
            # Extract subscription / customer info if created
            plan_object = tx_data.get('plan_object') or {}
            subscription_code = plan_object.get('subscriptions', [{}])[0].get('subscription_code') if plan_object.get('subscriptions') else None
            customer_code = tx_data.get('customer', {}).get('customer_code')
            
            # Upgrade business
            upgrade_to_premium(
                current_user.business_id,
                reference=reference,
                subscription_code=subscription_code,
                customer_code=customer_code
            )
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

@bp.route('/cancel_subscription', methods=['POST'])
@login_required
def cancel_subscription():
    business = get_business(current_user.business_id)
    if not business or business.get('plan_type') != 'premium':
        flash("You do not have an active Premium plan to cancel.", "info")
        return redirect(url_for('settings.index'))

    sub_code = business.get('paystack_subscription_code')
    secret_key = os.environ.get('PAYSTACK_SECRET_KEY')

    # If subscription code exists on Paystack, disable it on Paystack directly
    if sub_code and secret_key:
        try:
            # Paystack disable subscription endpoint
            headers = {
                'Authorization': f'Bearer {secret_key}',
                'Content-Type': 'application/json'
            }
            # Look up subscription token if needed or call disable
            disable_res = requests.post(
                'https://api.paystack.co/subscription/disable',
                headers=headers,
                json={'code': sub_code, 'token': business.get('paystack_email_token', '')},
                timeout=10
            )
        except Exception as e:
            # Continue with local downgrade even if Paystack network fails
            pass

    # Downgrade in Sallio database
    downgrade_to_free(current_user.business_id, reason="User cancelled via Settings")
    flash("Your Premium subscription has been cancelled. Your account is now on the Free plan.", "info")
    return redirect(url_for('settings.index'))

@bp.route('/webhook', methods=['POST'])
def webhook():
    paystack_signature = request.headers.get('x-paystack-signature')
    secret_key = os.environ.get('PAYSTACK_SECRET_KEY', '')
    
    if not secret_key:
        return jsonify({'status': 'error', 'message': 'Webhook secret not configured'}), 500

    hash_obj = hmac.new(secret_key.encode('utf-8'), request.data, hashlib.sha512)
    if hash_obj.hexdigest() != paystack_signature:
        return jsonify({'status': 'error', 'message': 'Invalid signature'}), 400

    payload = request.json or {}
    event = payload.get('event')
    data = payload.get('data', {})
    db = get_db()

    # 1. Recurring charge succeeded
    if event == 'charge.success':
        customer_code = data.get('customer', {}).get('customer_code')
        reference = data.get('reference')
        metadata = data.get('metadata') or {}
        business_id = metadata.get('business_id')

        # Find business by metadata or customer code
        business = None
        if business_id:
            try:
                business = db.businesses.find_one({'_id': ObjectId(business_id)})
            except Exception:
                pass
        if not business and customer_code:
            business = db.businesses.find_one({'paystack_customer_code': customer_code})

        if business:
            upgrade_to_premium(business['_id'], reference=reference, customer_code=customer_code)

    # 2. Subscription disabled / cancelled
    elif event in ('subscription.disable', 'subscription.not_renew'):
        sub_code = data.get('subscription_code')
        customer_code = data.get('customer', {}).get('customer_code')

        query = {}
        if sub_code:
            query = {'paystack_subscription_code': sub_code}
        elif customer_code:
            query = {'paystack_customer_code': customer_code}

        if query:
            biz = db.businesses.find_one(query)
            if biz:
                downgrade_to_free(biz['_id'], reason=f"Subscription cancelled ({event})")

    # 3. Invoice payment failed (card expired, insufficient funds, etc.)
    elif event == 'invoice.payment_failed':
        customer_code = data.get('customer', {}).get('customer_code')
        if customer_code:
            biz = db.businesses.find_one({'paystack_customer_code': customer_code})
            if biz:
                downgrade_to_free(biz['_id'], reason="Monthly recurring charge failed")

    return jsonify({'status': 'success'}), 200

