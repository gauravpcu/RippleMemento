from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
from .extensions import db
from .models import Monitor
from .services import check_monitor


scheduler = BackgroundScheduler()


def init_scheduler(app):
    if scheduler.state == 0:
        scheduler.configure(timezone="UTC")
        scheduler.start()

    def tick_all():
        with app.app_context():
            for m in Monitor.query.filter_by(active=True).all():
                try:
                    check_monitor(m)
                except Exception as e:
                    app.logger.exception("Error checking monitor %s: %s", m.id, e)

    # Global job to iterate monitors every minute and dispatch checks by interval
    @scheduler.scheduled_job("interval", minutes=1, id="ripplememento-global")
    def scheduled_tick():
        with app.app_context():
            now = datetime.utcnow()
            for m in Monitor.query.filter_by(active=True).all():
                due = not m.last_checked or (
                    (now - m.last_checked).total_seconds() >= m.interval_minutes * 60
                )
                if due:
                    try:
                        check_monitor(m)
                    except Exception:
                        current_app.logger.exception("Scheduled check failed for %s", m.id)

    return scheduler
