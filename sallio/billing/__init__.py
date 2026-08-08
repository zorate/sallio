from flask import Blueprint

bp = Blueprint('billing', __name__, url_prefix='/billing')

from sallio.billing import routes
