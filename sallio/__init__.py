from flask import Flask
from sallio.config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize database
    from sallio import db
    db.init_app(app)

    # Initialize Login Manager
    from flask_login import LoginManager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    from sallio.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.get(user_id)

    # Register blueprints
    from sallio.errors import bp as errors_bp
    app.register_blueprint(errors_bp)
    
    from sallio.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    
    from sallio.main import bp as main_bp
    app.register_blueprint(main_bp)

    return app
