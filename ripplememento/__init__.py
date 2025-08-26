from flask import Flask
from .extensions import db
from .routes import bp as main_bp
from .tasks import init_scheduler
from datetime import datetime
import pytz
from flask import request


def local_datetime(dt):
    """Convert UTC datetime to local timezone"""
    if dt is None:
        return None
    
    # If the datetime is naive (no timezone), assume it's UTC
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    
    # Use Eastern Time as default (most common US timezone)
    # You can change this to your preferred timezone
    local_tz = pytz.timezone('America/New_York')
    
    # Convert to local timezone
    return dt.astimezone(local_tz)


def create_app():
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:///ripplememento.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY="dev-secret-key-change-in-production",
    )

    # Add custom Jinja2 filter for timezone conversion
    app.jinja_env.filters['local'] = local_datetime

    db.init_app(app)

    with app.app_context():
        # Import models to ensure they're registered
        from . import models
        db.create_all()

    init_scheduler(app)

    app.register_blueprint(main_bp)

    return app
