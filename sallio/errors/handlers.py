from flask import render_template
from sallio.errors import bp

@bp.app_errorhandler(401)
def unauthorized_error(error):
    return render_template('errors/401.html'), 401

@bp.app_errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@bp.app_errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

@bp.app_errorhandler(503)
def service_unavailable_error(error):
    return render_template('errors/503.html'), 503
