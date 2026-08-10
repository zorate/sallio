from flask import Blueprint

bp = Blueprint('uploads', __name__, url_prefix='/uploads')

from sallio.uploads import routes  # noqa
