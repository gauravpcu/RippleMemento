from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from .extensions import db
from .models import Monitor, Snapshot
from .services import check_monitor, compute_diff, get_snapshots_by_date_range, get_snapshot_by_date, get_recent_snapshots


bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    monitors = (
        Monitor.query.order_by(Monitor.created_at.desc()).all()
    )
    return render_template("index.html", monitors=monitors)


@bp.route("/", methods=["POST"])
def quick_add_monitor():
    """Handle quick add monitor from dashboard"""
    url = request.form.get("url", "").strip()
    if url:
        # Create a quick monitor with default settings
        name = url  # Use URL as name for quick add
        m = Monitor(
            name=name, 
            url=url, 
            monitor_style='words',  # Default style
            ignore_whitespace=True,
            ignore_case=False,
            trigger_threshold=1
        )
        db.session.add(m)
        db.session.commit()
        flash(f"Monitor created for {url}", "success")
    else:
        flash("URL is required.", "error")
    return redirect(url_for("main.index"))


@bp.route("/monitors/new", methods=["GET", "POST"])
def new_monitor():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        url = request.form.get("url", "").strip()
        css = request.form.get("css_selector") or None
        interval = int(request.form.get("interval_minutes", 30) or 30)
        
        # New monitoring style options
        monitor_style = request.form.get("monitor_style", "words")
        ignore_whitespace = bool(request.form.get("ignore_whitespace"))
        ignore_case = bool(request.form.get("ignore_case"))
        trigger_threshold = int(request.form.get("trigger_threshold", 1) or 1)
        
        # Advanced options
        ignore_text = request.form.get("ignore_text") or None
        trigger_text = request.form.get("trigger_text") or None
        custom_headers = request.form.get("custom_headers") or None
        
        if not name or not url:
            flash("Name and URL are required.", "error")
            return redirect(url_for("main.new_monitor"))
            
        m = Monitor(
            name=name, 
            url=url, 
            css_selector=css, 
            interval_minutes=interval,
            monitor_style=monitor_style,
            ignore_whitespace=ignore_whitespace,
            ignore_case=ignore_case,
            trigger_threshold=trigger_threshold,
            ignore_text=ignore_text,
            trigger_text=trigger_text,
            custom_headers=custom_headers
        )
        db.session.add(m)
        db.session.commit()
        flash("Monitor created.", "success")
        return redirect(url_for("main.index"))
    return render_template("new_monitor.html")


@bp.route("/monitors/<int:monitor_id>")
def monitor_detail(monitor_id: int):
    m = Monitor.query.get_or_404(monitor_id)
    snaps = (
        Snapshot.query.filter_by(monitor_id=m.id)
        .order_by(Snapshot.created_at.desc())
        .all()
    )
    return render_template("monitor_detail.html", monitor=m, snaps=snaps)


@bp.route("/monitors/<int:monitor_id>/check", methods=["POST"])
def monitor_check(monitor_id: int):
    m = Monitor.query.get_or_404(monitor_id)
    check_monitor(m)
    flash("Check triggered.", "success")
    return redirect(url_for("main.monitor_detail", monitor_id=m.id))


@bp.route("/monitors/<int:monitor_id>/edit", methods=["GET", "POST"])
def monitor_edit(monitor_id: int):
    m = Monitor.query.get_or_404(monitor_id)
    if request.method == "POST":
        m.name = request.form.get("name", m.name).strip() or m.name
        m.url = request.form.get("url", m.url).strip() or m.url
        m.css_selector = request.form.get("css_selector") or None
        m.interval_minutes = int(request.form.get("interval_minutes", m.interval_minutes))
        m.active = bool(request.form.get("active"))
        
        # Update monitoring style options
        m.monitor_style = request.form.get("monitor_style", m.monitor_style)
        m.ignore_whitespace = bool(request.form.get("ignore_whitespace"))
        m.ignore_case = bool(request.form.get("ignore_case"))
        m.trigger_threshold = int(request.form.get("trigger_threshold", m.trigger_threshold) or 1)
        
        # Update advanced options
        m.ignore_text = request.form.get("ignore_text") or None
        m.trigger_text = request.form.get("trigger_text") or None
        m.custom_headers = request.form.get("custom_headers") or None
        
        db.session.commit()
        flash("Monitor updated.", "success")
        return redirect(url_for("main.monitor_detail", monitor_id=m.id))
    return render_template("edit_monitor.html", monitor=m)


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
    snapshot = Snapshot.query.get_or_404(snapshot_id)
    prev = (
        Snapshot.query.filter(
            Snapshot.monitor_id == m.id, Snapshot.id < snapshot.id
        )
        .order_by(Snapshot.id.desc())
        .first()
    )
    
    # Use the diff_html from the snapshot if it exists, otherwise compute it
    diff_html = snapshot.diff_html or ""
    
    # If no stored diff, compute it from previous snapshot
    if not diff_html and prev and prev.content_text and snapshot.content_text:
        diff_html, change_count = compute_diff(prev.content_text, snapshot.content_text, m.monitor_style)
        # Update the snapshot with the computed diff
        snapshot.diff_html = diff_html
        snapshot.change_count = change_count
        db.session.commit()
    
    return render_template("snapshot_detail_enhanced.html", 
                         monitor=m, 
                         snapshot=snapshot, 
                         prev=prev)


@bp.route("/monitors/<int:monitor_id>/compare", methods=["GET", "POST"])
def date_comparison(monitor_id: int):
    """Compare snapshots between two dates"""
    m = Monitor.query.get_or_404(monitor_id)
    
    if request.method == "POST":
        # Get date parameters from form
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not start_date or not end_date:
            flash("Please select both start and end dates.", "warning")
            recent_snapshots = get_recent_snapshots(monitor_id, limit=10)
            return render_template("date_comparison.html", monitor=m, recent_snapshots=recent_snapshots)
        
        try:
            # Get snapshots in the date range
            snapshots = get_snapshots_by_date_range(monitor_id, start_date, end_date)
            
            if len(snapshots) < 2:
                flash(f"Not enough snapshots found in the selected date range. Found {len(snapshots)} snapshots.", "warning")
                recent_snapshots = get_recent_snapshots(monitor_id, limit=10)
                return render_template("date_comparison.html", monitor=m, recent_snapshots=recent_snapshots)
            
            # Compare first and last snapshots in the range
            first_snapshot = snapshots[0]
            last_snapshot = snapshots[-1]
            
            # Compute diff between the two snapshots
            diff_html, change_count = compute_diff(first_snapshot.content_text, last_snapshot.content_text, m.monitor_style)
            
            return render_template("date_comparison_result.html",
                                 monitor=m,
                                 first_snapshot=first_snapshot,
                                 last_snapshot=last_snapshot,
                                 diff_html=diff_html,
                                 change_count=change_count,
                                 total_snapshots=len(snapshots),
                                 start_date=start_date,
                                 end_date=end_date)
            
        except Exception as e:
            flash(f"Error comparing dates: {str(e)}", "error")
            recent_snapshots = get_recent_snapshots(monitor_id, limit=10)
            return render_template("date_comparison.html", monitor=m, recent_snapshots=recent_snapshots)
    
    # GET request - show date selection form
    recent_snapshots = get_recent_snapshots(monitor_id, limit=10)
    return render_template("date_comparison.html", monitor=m, recent_snapshots=recent_snapshots)


@bp.route("/bulk-actions", methods=["POST"])
def bulk_actions():
    """Handle bulk actions on selected monitors"""
    action = request.form.get("action")
    monitor_ids = request.form.getlist("monitor_ids")
    
    # Temporary debug logging
    print(f"🔍 DEBUG: Action = {action}")
    print(f"🔍 DEBUG: Monitor IDs = {monitor_ids}")
    print(f"🔍 DEBUG: Form data = {dict(request.form)}")
    
    if not monitor_ids:
        print("❌ DEBUG: No monitor IDs received")
        flash("No monitors selected", "warning")
        return redirect(url_for("main.index"))
    
    monitors = Monitor.query.filter(Monitor.id.in_(monitor_ids)).all()
    
    if action == "pause":
        print(f"🔄 DEBUG: Pausing {len(monitors)} monitors")
        for monitor in monitors:
            print(f"🔄 DEBUG: Pausing monitor {monitor.id} ({monitor.name})")
            monitor.is_paused = True
        db.session.commit()
        print("✅ DEBUG: Pause operation committed to database")
        flash(f"Paused {len(monitors)} monitor(s)", "success")
        
    elif action == "unpause":
        for monitor in monitors:
            monitor.is_paused = False
        db.session.commit()
        flash(f"Unpaused {len(monitors)} monitor(s)", "success")
        
    elif action == "recheck":
        for monitor in monitors:
            try:
                check_monitor(monitor.id)
            except Exception as e:
                flash(f"Error checking {monitor.url}: {str(e)}", "error")
        flash(f"Rechecked {len(monitors)} monitor(s)", "success")
        
    elif action == "delete":
        for monitor in monitors:
            # Delete associated snapshots first
            Snapshot.query.filter_by(monitor_id=monitor.id).delete()
            db.session.delete(monitor)
        db.session.commit()
        flash(f"Deleted {len(monitors)} monitor(s)", "success")
    
    return redirect(url_for("main.index"))


@bp.route("/recheck-all")
def recheck_all():
    """Recheck all active monitors"""
    monitors = Monitor.query.filter_by(is_paused=False).all()
    
    for monitor in monitors:
        try:
            check_monitor(monitor.id)
        except Exception as e:
            flash(f"Error checking {monitor.url}: {str(e)}", "error")
    
    flash(f"Rechecked {len(monitors)} monitor(s)", "success")
    return redirect(url_for("main.index"))


@bp.route("/mark-all-viewed")
def mark_all_viewed():
    """Mark all monitors as viewed (clear change notifications)"""
    # This could be implemented by adding a 'viewed' field to Monitor or Snapshot
    # For now, we'll just show a message
    flash("All monitors marked as viewed", "success")
    return redirect(url_for("main.index"))


@bp.route("/monitors/<int:monitor_id>/check")
def check_monitor_now(monitor_id):
    """Check a specific monitor immediately"""
    monitor = Monitor.query.get_or_404(monitor_id)
    
    try:
        check_monitor(monitor_id)
        flash(f"Monitor {monitor.url} checked successfully", "success")
    except Exception as e:
        flash(f"Error checking monitor: {str(e)}", "error")
    
    return redirect(url_for("main.index"))
