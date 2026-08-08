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
    business_doc = {
        'name': business_name,
        'email': email,
        'address': address
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
        
    receipt_number = generate_receipt_number()
    
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
