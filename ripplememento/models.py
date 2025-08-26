from datetime import datetime
from .extensions import db


class Monitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(2048), nullable=False, unique=False)
    css_selector = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_checked = db.Column(db.DateTime, nullable=True)
    interval_minutes = db.Column(db.Integer, default=30)
    active = db.Column(db.Boolean, default=True)
    is_paused = db.Column(db.Boolean, default=False)  # Add paused state
    
    # Monitoring style options
    monitor_style = db.Column(db.String(20), default='lines')  # words, lines, chars, json
    ignore_whitespace = db.Column(db.Boolean, default=True)
    ignore_case = db.Column(db.Boolean, default=False)
    trigger_threshold = db.Column(db.Integer, default=1)  # minimum changes to trigger
    
    # Advanced filtering
    ignore_text = db.Column(db.Text, nullable=True)  # Text patterns to ignore
    trigger_text = db.Column(db.Text, nullable=True)  # Only trigger on specific text
    custom_headers = db.Column(db.Text, nullable=True)  # JSON string for headers

    snapshots = db.relationship(
        "Snapshot", backref="monitor", lazy=True, cascade="all, delete-orphan"
    )


class Snapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monitor_id = db.Column(db.Integer, db.ForeignKey("monitor.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    content_hash = db.Column(db.String(64), index=True)
    content_text = db.Column(db.Text)
    content_raw = db.Column(db.Text)  # Store raw content for different processing styles
    change_count = db.Column(db.Integer, default=0)  # Number of changes detected
    diff_html = db.Column(db.Text, nullable=True)  # Precomputed diff HTML
    error_message = db.Column(db.Text, nullable=True)
