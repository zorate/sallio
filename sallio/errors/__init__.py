from flask import Blueprint

bp = Blueprint('errors', __name__)

from sallio.errors import handlers
