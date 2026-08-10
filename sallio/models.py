from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from bson.objectid import ObjectId
from sallio.db import get_db

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.email = user_data.get('email')
        self.phone = user_data.get('phone')
        self.owner_name = user_data.get('owner_name')
        self.business_id = str(user_data.get('business_id')) if user_data.get('business_id') else None
    
    @staticmethod
    def get(user_id):
        db = get_db()
        user_data = db.users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return User(user_data)
        return None
        
    @staticmethod
    def find_by_phone(phone):
        db = get_db()
        user_data = db.users.find_one({'phone': phone})
        if user_data:
            return User(user_data)
        return None

def create_user_and_business(owner_name, phone, password, business_name, email=None, address=None):
    db = get_db()
    
    # 1. Create Business
    # Calculate initial quota reset date (next Monday)
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    days_ahead = 0 - now.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_monday = now + datetime.timedelta(days=days_ahead)
    next_monday = next_monday.replace(hour=0, minute=0, second=0, microsecond=0)

    business_doc = {
        'name': business_name,
        'email': email,
        'address': address,
        'plan_type': 'free',
        'receipt_generation_count': 0,
        'receipt_quota_reset_date': next_monday,
        'paystack_customer_code': None,
        'paystack_subscription_code': None,
        'subscription_status': 'active'
    }
    business_result = db.businesses.insert_one(business_doc)
    
    # 2. Create User
    user_doc = {
        'owner_name': owner_name,
        'phone': phone,
        'password_hash': generate_password_hash(password),
        'email': email,
        'business_id': business_result.inserted_id
    }
    user_result = db.users.insert_one(user_doc)
    
    return User(db.users.find_one({'_id': user_result.inserted_id}))

def verify_user(phone, password):
    db = get_db()
    user_data = db.users.find_one({'phone': phone})
    if user_data and check_password_hash(user_data['password_hash'], password):
        return User(user_data)
    return None

import datetime
from pymongo import ReturnDocument

def get_wat_time():
    """Returns current Nigerian Time (WAT, UTC+1) as a naive datetime"""
    return datetime.datetime.utcnow() + datetime.timedelta(hours=1)

def generate_receipt_number():
    db = get_db()
    # Find the counter document for receipts, increment sequence value by 1
    # If it doesn't exist, insert one with sequence value 1000
    counter = db.counters.find_one_and_update(
        {'_id': 'receipt_id'},
        {'$inc': {'sequence_value': 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    # Generate receipt number in format: RCPT-YYYYMMDD-XXXX
    date_str = get_wat_time().strftime('%Y%m%d')
    # Use sequence_value + 1000 to start at a nice number
    seq = counter.get('sequence_value', 1) + 1000
    return f"RCPT-{date_str}-{seq}"

def create_sale(business_id, items, payment_method, customer_name=None, customer_phone=None):
    db = get_db()
    
    # Calculate totals securely on the backend
    subtotal = 0
    validated_items = []
    
    for item in items:
        # Basic validation
        name = item.get('name', '').strip()
        try:
            qty = int(item.get('quantity', 0))
            price = float(item.get('price', 0))
        except (ValueError, TypeError):
            continue
            
        if name and qty > 0 and price >= 0:
            item_total = qty * price
            subtotal += item_total
            validated_items.append({
                'name': name,
                'quantity': qty,
                'price': price,
                'total': item_total
            })
            
    if not validated_items:
        raise ValueError("No valid items in the sale.")
        
    receipt_number = get_next_business_receipt_number(business_id)
    
    sale_doc = {
        'business_id': ObjectId(business_id),
        'receipt_number': receipt_number,
        'date': get_wat_time(),
        'items': validated_items,
        'subtotal': subtotal,
        'total': subtotal, # MVP doesn't have discounts yet
        'payment_method': payment_method,
        'customer_name': customer_name,
        'customer_phone': customer_phone
    }
    
    result = db.sales.insert_one(sale_doc)
    return db.sales.find_one({'_id': result.inserted_id})

def get_sale(receipt_number, business_id):
    db = get_db()
    return db.sales.find_one({
        'receipt_number': receipt_number,
        'business_id': ObjectId(business_id)
    })

def get_sales(business_id, limit=50):
    db = get_db()
    return list(db.sales.find(
        {'business_id': ObjectId(business_id)}
    ).sort('date', -1).limit(limit))

def get_dashboard_stats(business_id):
    db = get_db()
    now = get_wat_time()
    
    # Calculate start of day, week, month
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = start_of_day - datetime.timedelta(days=now.weekday())
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    pipeline = [
        {'$match': {'business_id': ObjectId(business_id)}},
        {'$group': {
            '_id': None,
            'total_sales_count': {'$sum': 1},
            'today_total': {'$sum': {'$cond': [{'$gte': ['$date', start_of_day]}, '$total', 0]}},
            'week_total': {'$sum': {'$cond': [{'$gte': ['$date', start_of_week]}, '$total', 0]}},
            'month_total': {'$sum': {'$cond': [{'$gte': ['$date', start_of_month]}, '$total', 0]}}
        }}
    ]
    
    result = list(db.sales.aggregate(pipeline))
    if result:
        return result[0]
    return {
        'total_sales_count': 0,
        'today_total': 0,
        'week_total': 0,
        'month_total': 0
    }

# --- Billing Helpers ---

def get_business(business_id):
    db = get_db()
    return db.businesses.find_one({'_id': ObjectId(business_id)})

def can_generate_receipt(business_id):
    business = get_business(business_id)
    if not business:
        return False
        
    # Premium gets unlimited
    if business.get('plan_type') == 'premium':
        return True
        
    # Free gets 15/week
    now = get_wat_time()
    reset_date = business.get('receipt_quota_reset_date')
    
    # If past reset date, they can generate
    if not reset_date or now >= reset_date:
        return True
        
    return business.get('receipt_generation_count', 0) < 15

def increment_receipt_quota(business_id):
    db = get_db()
    business = get_business(business_id)
    if not business:
        return False
        
    now = get_wat_time()
    reset_date = business.get('receipt_quota_reset_date')
    
    # If past reset date, reset count and set new date
    if not reset_date or now >= reset_date:
        days_ahead = 0 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_monday = now + datetime.timedelta(days=days_ahead)
        next_monday = next_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        db.businesses.update_one(
            {'_id': ObjectId(business_id)},
            {
                '$set': {
                    'receipt_generation_count': 1,
                    'receipt_quota_reset_date': next_monday
                }
            }
        )
    else:
        db.businesses.update_one(
            {'_id': ObjectId(business_id)},
            {'$inc': {'receipt_generation_count': 1}}
        )
    return True

def upgrade_to_premium(business_id, reference):
    db = get_db()
    db.businesses.update_one(
        {'_id': ObjectId(business_id)},
        {
            '$set': {
                'plan_type': 'premium',
                'subscription_status': 'active',
                'paystack_reference': reference
            }
        }
    )
    return True


# ---------------------------------------------------------------------------
# Business Settings Helpers
# ---------------------------------------------------------------------------

def update_business_settings(business_id: str, data: dict) -> bool:
    """
    Update editable business profile fields.
    Accepts: bio, display_phone, head_office dict.
    """
    db = get_db()
    allowed_top = {'bio', 'display_phone', 'head_office'}
    update_data = {k: v for k, v in data.items() if k in allowed_top}

    # Enforce bio character limit server-side
    if 'bio' in update_data:
        update_data['bio'] = str(update_data['bio'])[:300]

    if not update_data:
        return False

    db.businesses.update_one(
        {'_id': ObjectId(business_id)},
        {'$set': update_data}
    )
    return True


def add_branch(business_id: str, branch: dict) -> bool:
    """Append a branch office to the branches array (Premium only, max 5)."""
    db = get_db()
    business = get_business(business_id)
    if not business:
        return False

    branches = business.get('branches', [])
    if len(branches) >= 5:
        return False  # hard cap

    allowed = {'label', 'address', 'city', 'state', 'phone'}
    clean = {k: str(v).strip() for k, v in branch.items() if k in allowed}

    db.businesses.update_one(
        {'_id': ObjectId(business_id)},
        {'$push': {'branches': clean}}
    )
    return True


def remove_branch(business_id: str, index: int) -> bool:
    """Remove branch at the given 0-based index."""
    db = get_db()
    business = get_business(business_id)
    if not business:
        return False

    branches = business.get('branches', [])
    if index < 0 or index >= len(branches):
        return False

    # MongoDB doesn't support remove-by-index directly;
    # use a temporary sentinel then pull it.
    sentinel = {'_sallio_delete_': True}
    db.businesses.update_one(
        {'_id': ObjectId(business_id)},
        {'$set': {f'branches.{index}': sentinel}}
    )
    db.businesses.update_one(
        {'_id': ObjectId(business_id)},
        {'$pull': {'branches': sentinel}}
    )
    return True


def save_logo(business_id: str, file_id: str, old_file_id: str = None) -> bool:
    """
    Store the GridFS file_id on the business document.
    Deletes the old logo from GridFS if one existed.
    """
    from sallio.storage import delete_file
    db = get_db()

    if old_file_id:
        delete_file(old_file_id)

    db.businesses.update_one(
        {'_id': ObjectId(business_id)},
        {'$set': {'logo_file_id': file_id}}
    )
    return True


def save_signature(business_id: str, file_id: str, old_file_id: str = None) -> bool:
    """
    Store the GridFS file_id for the signature on the business document.
    Deletes the old signature from GridFS if one existed.
    """
    from sallio.storage import delete_file
    db = get_db()

    if old_file_id:
        delete_file(old_file_id)

    db.businesses.update_one(
        {'_id': ObjectId(business_id)},
        {'$set': {'signature_file_id': file_id}}
    )
    return True


def get_next_business_receipt_number(business_id: str) -> str:
    """
    Atomically increment and return a per-business receipt number.
    Format: #0001, #0002, ...
    """
    db = get_db()
    result = db.businesses.find_one_and_update(
        {'_id': ObjectId(business_id)},
        {'$inc': {'receipt_counter': 1}},
        return_document=ReturnDocument.AFTER,
        upsert=False
    )
    seq = result.get('receipt_counter', 1) if result else 1
    return f'#{seq:04d}'
