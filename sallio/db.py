from pymongo import MongoClient
from flask import g, current_app

def get_db():
    if 'db' not in g:
        client = MongoClient(current_app.config['MONGO_URI'])
        # Extract database name from URI, default to sallio_db
        db_name = current_app.config['MONGO_URI'].split('/')[-1].split('?')[0] or 'sallio_db'
        g.db = client[db_name]
        g.mongo_client = client
    return g.db

def close_db(e=None):
    client = g.pop('mongo_client', None)
    if client is not None:
        client.close()

def init_app(app):
    app.teardown_appcontext(close_db)
