from datetime import datetime
from .extensions import db


class Monitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(2048), nullable=False, unique=False)
    css_selector = db.Column(db.String(512), nullable=True)
    headers = db.Column(db.Text, nullable=True)  # JSON string
    ignore_text = db.Column(db.Text, nullable=True)  # Text to ignore in diffs
    trigger_text = db.Column(db.Text, nullable=True)  # Only trigger on this text
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_checked = db.Column(db.DateTime, nullable=True)
    last_changed = db.Column(db.DateTime, nullable=True)
    interval_minutes = db.Column(db.Integer, default=30)
    active = db.Column(db.Boolean, default=True)
    notification_enabled = db.Column(db.Boolean, default=True)
    
    # Stats
    total_checks = db.Column(db.Integer, default=0)
    total_changes = db.Column(db.Integer, default=0)
    consecutive_failures = db.Column(db.Integer, default=0)
    
    # Relations
    snapshots = db.relationship(
        "Snapshot", backref="monitor", lazy=True, cascade="all, delete-orphan"
    )
    tags = db.relationship(
        "Tag", secondary="monitor_tags", back_populates="monitors"
    )

    @property
    def status(self):
        if not self.active:
            return "paused"
        if self.consecutive_failures > 3:
            return "error"
        if self.last_checked and (datetime.utcnow() - self.last_checked).total_seconds() > self.interval_minutes * 60 * 2:
            return "stale"
        return "active"


class Snapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monitor_id = db.Column(db.Integer, db.ForeignKey("monitor.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    content_hash = db.Column(db.String(64), index=True)
    content_text = db.Column(db.Text)
    error_message = db.Column(db.Text, nullable=True)
    response_time_ms = db.Column(db.Integer, nullable=True)
    status_code = db.Column(db.Integer, nullable=True)


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    color = db.Column(db.String(7), default="#6366f1")  # Hex color
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    monitors = db.relationship(
        "Monitor", secondary="monitor_tags", back_populates="tags"
    )


# Association table for many-to-many relationship
monitor_tags = db.Table(
    "monitor_tags",
    db.Column("monitor_id", db.Integer, db.ForeignKey("monitor.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
)


class NotificationEndpoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # email, webhook, discord, slack
    config = db.Column(db.Text, nullable=False)  # JSON config
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MonitorHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monitor_id = db.Column(db.Integer, db.ForeignKey("monitor.id"), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)  # change, error, check
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)