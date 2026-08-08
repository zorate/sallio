import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev_secret_key'
    MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/sallio_db'
    SUPPORT_WHATSAPP_NUMBER = os.environ.get('SUPPORT_WHATSAPP_NUMBER', '2348000000000')
