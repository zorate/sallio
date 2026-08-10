from flask import Blueprint

bp = Blueprint('settings', __name__, url_prefix='/settings')

from sallio.settings import routes  # noqa
