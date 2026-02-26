import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from config import config_map

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates'),
                static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static'))

    app.config.from_object(config_map.get(config_name, config_map['development']))

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    CORS(app)

    login_manager.login_view = 'admin.login'
    login_manager.login_message_category = 'warning'

    # Ensure upload directory exists
    upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(os.path.join(upload_folder, 'images'), exist_ok=True)
    os.makedirs(os.path.join(upload_folder, 'videos'), exist_ok=True)

    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)

    # Setup logging
    if not app.debug and not app.testing:
        file_handler = RotatingFileHandler('logs/spkr.log', maxBytes=10240000, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('SasksVoice Platform startup')

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.webhook import webhook_bp
    from app.routes.cpanel import cpanel_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(webhook_bp, url_prefix='/webhook')
    app.register_blueprint(cpanel_bp, url_prefix='/admin')

    # Exempt webhook from CSRF
    csrf.exempt(webhook_bp)

    # User loader
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Create tables and seed admin
    with app.app_context():
        from app.models import User, Submission, Payment, ModerationLog, BlacklistedKeyword, SystemSetting
        db.create_all()
        _seed_admin(app)
        _seed_settings()

    # Custom Jinja filters
    import json
    app.jinja_env.filters['from_json'] = lambda s: json.loads(s) if s else []

    # Error handlers
    @app.errorhandler(413)
    def request_entity_too_large(e):
        from flask import flash, redirect, url_for
        flash('File too large! Maximum upload size is 100MB.', 'error')
        return redirect(url_for('main.index'))

    @app.errorhandler(500)
    def internal_server_error(e):
        from flask import flash, redirect, url_for
        app.logger.error(f'Internal Server Error: {e}')
        flash('An internal error occurred. Please try again.', 'error')
        return redirect(url_for('main.index'))

    return app


def _seed_admin(app):
    """Create default admin user if none exists."""
    from app.models import User
    import bcrypt

    admin = User.query.filter_by(role='admin').first()
    if not admin:
        hashed = bcrypt.hashpw(app.config['ADMIN_PASSWORD'].encode('utf-8'), bcrypt.gensalt())
        admin = User(
            email=app.config['ADMIN_EMAIL'],
            password_hash=hashed.decode('utf-8'),
            role='admin',
            is_active=True
        )
        db.session.add(admin)
        db.session.commit()


def _seed_settings():
    """Create default system settings."""
    from app.models import SystemSetting

    defaults = {
        'auto_publish': 'false',
        'require_approval': 'true',
        'free_post_limit_per_day': '5',
        'promo_price_min': '1.00',
        'promo_price_max': '2.00',
        'max_caption_length': '2200',
        'block_links': 'true',
    }

    for key, value in defaults.items():
        setting = SystemSetting.query.filter_by(key=key).first()
        if not setting:
            setting = SystemSetting(key=key, value=value)
            db.session.add(setting)

    db.session.commit()
