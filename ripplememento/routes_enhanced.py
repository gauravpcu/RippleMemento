from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import json
from .extensions import db
from .models_enhanced import Monitor, Snapshot, Tag, NotificationEndpoint, MonitorHistory
from .services_enhanced import check_monitor, compute_diff, get_monitor_stats


bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    tag_filter = request.args.get('tag')
    status_filter = request.args.get('status')
    
    query = Monitor.query
    
    if tag_filter:
        query = query.join(Monitor.tags).filter(Tag.name == tag_filter)
    
    monitors = query.order_by(Monitor.created_at.desc()).all()
    
    if status_filter:
        monitors = [m for m in monitors if m.status == status_filter]
    
    tags = Tag.query.all()
    
    # Stats for dashboard
    total_monitors = len(monitors)
    active_monitors = len([m for m in monitors if m.active])
    error_monitors = len([m for m in monitors if m.status == "error"])
    
    return render_template("index_enhanced.html", 
                         monitors=monitors, 
                         tags=tags,
                         stats={
                             'total': total_monitors,
                             'active': active_monitors,
                             'errors': error_monitors
                         })


@bp.route("/monitors/new", methods=["GET", "POST"])
def new_monitor():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        url = request.form.get("url", "").strip()
        css = request.form.get("css_selector") or None
        headers = request.form.get("headers") or None
        ignore_text = request.form.get("ignore_text") or None
        trigger_text = request.form.get("trigger_text") or None
        interval = int(request.form.get("interval_minutes", 30) or 30)
        notification_enabled = bool(request.form.get("notification_enabled"))
        
        # Validate headers JSON
        if headers:
            try:
                json.loads(headers)
            except:
                flash("Invalid JSON in headers field.", "error")
                return redirect(url_for("main.new_monitor"))
        
        if not name or not url:
            flash("Name and URL are required.", "error")
            return redirect(url_for("main.new_monitor"))
            
        m = Monitor(
            name=name, 
            url=url, 
            css_selector=css,
            headers=headers,
            ignore_text=ignore_text,
            trigger_text=trigger_text,
            interval_minutes=interval,
            notification_enabled=notification_enabled
        )
        
        # Handle tags
        tag_names = request.form.get("tags", "").split(",")
        for tag_name in tag_names:
            tag_name = tag_name.strip()
            if tag_name:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                m.tags.append(tag)
        
        db.session.add(m)
        db.session.commit()
        flash("Monitor created.", "success")
        return redirect(url_for("main.index"))
        
    tags = Tag.query.all()
    return render_template("new_monitor_enhanced.html", tags=tags)


@bp.route("/monitors/<int:monitor_id>")
def monitor_detail(monitor_id: int):
    m = Monitor.query.get_or_404(monitor_id)
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    snaps = (
        Snapshot.query.filter_by(monitor_id=m.id)
        .order_by(Snapshot.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    
    # Get monitor statistics
    stats = get_monitor_stats(monitor_id)
    
    # Get recent history
    history = (
        MonitorHistory.query.filter_by(monitor_id=monitor_id)
        .order_by(MonitorHistory.created_at.desc())
        .limit(10)
        .all()
    )
    
    return render_template("monitor_detail_enhanced.html", 
                         monitor=m, 
                         snaps=snaps, 
                         stats=stats, 
                         history=history)


@bp.route("/monitors/<int:monitor_id>/check", methods=["POST"])
def monitor_check(monitor_id: int):
    m = Monitor.query.get_or_404(monitor_id)
    try:
        result = check_monitor(m)
        if result and result.error_message:
            flash(f"Check failed: {result.error_message}", "error")
        elif result:
            flash("Change detected!", "success")
        else:
            flash("No changes detected.", "info")
    except Exception as e:
        flash(f"Check failed: {str(e)}", "error")
    
    return redirect(url_for("main.monitor_detail", monitor_id=m.id))


@bp.route("/monitors/<int:monitor_id>/edit", methods=["GET", "POST"])
def monitor_edit(monitor_id: int):
    m = Monitor.query.get_or_404(monitor_id)
    if request.method == "POST":
        m.name = request.form.get("name", m.name).strip() or m.name
        m.url = request.form.get("url", m.url).strip() or m.url
        m.css_selector = request.form.get("css_selector") or None
        m.headers = request.form.get("headers") or None
        m.ignore_text = request.form.get("ignore_text") or None
        m.trigger_text = request.form.get("trigger_text") or None
        m.interval_minutes = int(request.form.get("interval_minutes", m.interval_minutes))
        m.active = bool(request.form.get("active"))
        m.notification_enabled = bool(request.form.get("notification_enabled"))
        
        # Validate headers JSON
        if m.headers:
            try:
                json.loads(m.headers)
            except:
                flash("Invalid JSON in headers field.", "error")
                return redirect(url_for("main.monitor_edit", monitor_id=m.id))
        
        # Update tags
        m.tags.clear()
        tag_names = request.form.get("tags", "").split(",")
        for tag_name in tag_names:
            tag_name = tag_name.strip()
            if tag_name:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                m.tags.append(tag)
        
        db.session.commit()
        flash("Monitor updated.", "success")
        return redirect(url_for("main.monitor_detail", monitor_id=m.id))
        
    tags = Tag.query.all()
    return render_template("edit_monitor_enhanced.html", monitor=m, tags=tags)


@bp.route("/monitors/<int:monitor_id>/delete", methods=["POST"]) 
def monitor_delete(monitor_id: int):
    m = Monitor.query.get_or_404(monitor_id)
    db.session.delete(m)
    db.session.commit()
    flash("Monitor deleted.", "success")
    return redirect(url_for("main.index"))


@bp.route("/monitors/<int:monitor_id>/snapshots/<int:snapshot_id>")
def snapshot_detail(monitor_id: int, snapshot_id: int):
    m = Monitor.query.get_or_404(monitor_id)
    snap = Snapshot.query.get_or_404(snapshot_id)
    prev = (
        Snapshot.query.filter(
            Snapshot.monitor_id == m.id, 
            Snapshot.id < snap.id,
            Snapshot.content_hash.isnot(None)  # Only compare with non-error snapshots
        )
        .order_by(Snapshot.id.desc())
        .first()
    )
    
    diff_html = ""
    if prev and not snap.error_message:
        diff_html = compute_diff(prev.content_text if prev else "", snap.content_text)
    
    return render_template("snapshot_detail_enhanced.html", 
                         monitor=m, 
                         snap=snap, 
                         prev=prev, 
                         diff_html=diff_html)


@bp.route("/notifications")
def notifications():
    endpoints = NotificationEndpoint.query.all()
    return render_template("notifications.html", endpoints=endpoints)


@bp.route("/notifications/new", methods=["GET", "POST"])
def new_notification():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        notification_type = request.form.get("type")
        
        # Build config based on type
        config = {}
        if notification_type == "email":
            config = {
                "smtp_host": request.form.get("smtp_host"),
                "smtp_port": int(request.form.get("smtp_port", 587)),
                "username": request.form.get("username"),
                "password": request.form.get("password"),
                "from_email": request.form.get("from_email"),
                "to_email": request.form.get("to_email"),
                "use_tls": bool(request.form.get("use_tls"))
            }
        elif notification_type in ["discord", "slack"]:
            config = {"webhook_url": request.form.get("webhook_url")}
        elif notification_type == "webhook":
            config = {
                "url": request.form.get("webhook_url"),
                "headers": json.loads(request.form.get("headers", "{}"))
            }
        
        endpoint = NotificationEndpoint(
            name=name,
            type=notification_type,
            config=json.dumps(config)
        )
        db.session.add(endpoint)
        db.session.commit()
        flash("Notification endpoint created.", "success")
        return redirect(url_for("main.notifications"))
    
    return render_template("new_notification.html")


@bp.route("/analytics")
def analytics():
    # Overall stats
    total_monitors = Monitor.query.count()
    active_monitors = Monitor.query.filter_by(active=True).count()
    total_snapshots = Snapshot.query.count()
    total_changes = Snapshot.query.filter(Snapshot.content_hash.isnot(None)).count()
    
    # Recent activity
    recent_changes = (
        Snapshot.query.join(Monitor)
        .filter(Snapshot.content_hash.isnot(None))
        .order_by(Snapshot.created_at.desc())
        .limit(10)
        .all()
    )
    
    return render_template("analytics.html", stats={
        'total_monitors': total_monitors,
        'active_monitors': active_monitors,
        'total_snapshots': total_snapshots,
        'total_changes': total_changes,
        'recent_changes': recent_changes
    })


# API endpoints
@bp.route("/api/monitors")
def api_monitors():
    monitors = Monitor.query.all()
    return jsonify([{
        'id': m.id,
        'name': m.name,
        'url': m.url,
        'status': m.status,
        'last_checked': m.last_checked.isoformat() if m.last_checked else None,
        'total_changes': m.total_changes
    } for m in monitors])


@bp.route("/api/monitors/<int:monitor_id>/check", methods=["POST"])
def api_monitor_check(monitor_id: int):
    m = Monitor.query.get_or_404(monitor_id)
    try:
        result = check_monitor(m)
        return jsonify({
            'success': True,
            'changed': bool(result and result.content_hash),
            'error': result.error_message if result else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500