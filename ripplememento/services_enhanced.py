import hashlib
import json
import time
from typing import Optional, Dict, Any
import requests
from bs4 import BeautifulSoup
from diff_match_patch import diff_match_patch
from .models_enhanced import Monitor, Snapshot, MonitorHistory
from .extensions import db
from .notifications import notification_service, log_monitor_event


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)


def fetch_text(url: str, css_selector: Optional[str] = None, custom_headers: Optional[Dict[str, str]] = None) -> tuple[str, int, int]:
    """Fetch text content from URL and return (text, status_code, response_time_ms)"""
    headers = {"User-Agent": USER_AGENT}
    if custom_headers:
        headers.update(custom_headers)
    
    start_time = time.time()
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        response_time_ms = int((time.time() - start_time) * 1000)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        if css_selector:
            node = soup.select_one(css_selector)
            text = node.get_text("\n", strip=True) if node else ""
        else:
            # Remove script, style, and other non-content elements
            for s in soup(["script", "style", "noscript", "meta", "link"]):
                s.decompose()
            text = soup.get_text("\n", strip=True)
        
        return text, resp.status_code, response_time_ms
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        raise e


def apply_filters(text: str, monitor: Monitor) -> str:
    """Apply ignore/trigger text filters"""
    if monitor.ignore_text:
        ignore_patterns = [p.strip() for p in monitor.ignore_text.split('\n') if p.strip()]
        for pattern in ignore_patterns:
            text = text.replace(pattern, '')
    
    if monitor.trigger_text:
        trigger_patterns = [p.strip() for p in monitor.trigger_text.split('\n') if p.strip()]
        # Only return text if it contains any trigger pattern
        if not any(pattern in text for pattern in trigger_patterns):
            return ""
    
    return text.strip()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_diff(prev: str, current: str) -> str:
    """Generate HTML diff with better styling"""
    dmp = diff_match_patch()
    diffs = dmp.diff_main(prev, current)
    dmp.diff_cleanupSemantic(diffs)
    
    html = []
    for op, data in diffs:
        if op == 0:  # Equal
            # Show context but truncate long unchanged sections
            if len(data) > 200:
                lines = data.split('\n')
                if len(lines) > 6:
                    context_start = '\n'.join(lines[:3])
                    context_end = '\n'.join(lines[-3:])
                    data = f"{context_start}\n\n... ({len(lines)-6} lines unchanged) ...\n\n{context_end}"
            html.append(f"<span class='text-slate-600'>{data}</span>")
        elif op == 1:  # Insertion
            html.append(f"<span class='bg-green-200 text-green-900 px-1 rounded'>{data}</span>")
        else:  # Deletion
            html.append(f"<span class='bg-red-200 text-red-900 line-through px-1 rounded'>{data}</span>")
    
    return "".join(html)


def record_snapshot(monitor: Monitor, text: str, status_code: int = 200, response_time_ms: int = 0, error_message: str = None) -> Snapshot:
    """Record a new snapshot"""
    h = hash_text(text) if text else None
    snap = Snapshot(
        monitor=monitor,
        content_hash=h,
        content_text=text,
        status_code=status_code,
        response_time_ms=response_time_ms,
        error_message=error_message
    )
    db.session.add(snap)
    db.session.commit()
    return snap


def check_monitor(monitor: Monitor) -> Optional[Snapshot]:
    """Check a monitor for changes"""
    monitor.total_checks += 1
    
    try:
        # Parse custom headers if provided
        custom_headers = {}
        if monitor.headers:
            try:
                custom_headers = json.loads(monitor.headers)
            except:
                pass
        
        # Fetch content
        text, status_code, response_time_ms = fetch_text(
            monitor.url, 
            monitor.css_selector, 
            custom_headers
        )
        
        # Apply filters
        filtered_text = apply_filters(text, monitor)
        
        # Get last snapshot for comparison
        last = (
            Snapshot.query.filter_by(monitor_id=monitor.id)
            .order_by(Snapshot.created_at.desc())
            .first()
        )
        
        # Update monitor timestamps
        monitor.last_checked = db.func.now()
        monitor.consecutive_failures = 0
        
        # Check for changes
        h = hash_text(filtered_text) if filtered_text else None
        has_changed = not last or (last.content_hash != h and filtered_text)
        
        if has_changed:
            monitor.last_changed = db.func.now()
            monitor.total_changes += 1
            
            snap = record_snapshot(monitor, filtered_text, status_code, response_time_ms)
            
            # Log and notify
            log_monitor_event(monitor.id, "change", f"Content changed (hash: {h[:12]})")
            
            if monitor.notification_enabled:
                notification_service.send_notification(monitor, snap, "change")
            
            db.session.commit()
            return snap
        else:
            # No change, just log the check
            log_monitor_event(monitor.id, "check", f"No change detected")
            db.session.commit()
            return None
            
    except Exception as e:
        # Handle errors
        monitor.consecutive_failures += 1
        monitor.last_checked = db.func.now()
        
        error_snap = record_snapshot(
            monitor, 
            "", 
            status_code=0, 
            response_time_ms=0, 
            error_message=str(e)
        )
        
        log_monitor_event(monitor.id, "error", str(e))
        
        if monitor.notification_enabled and monitor.consecutive_failures == 1:
            notification_service.send_notification(monitor, error_snap, "error")
        
        db.session.commit()
        return error_snap


def get_previous_snapshot(monitor_id: int, snapshot_id: int) -> Optional[Snapshot]:
    return (
        Snapshot.query.filter(
            Snapshot.monitor_id == monitor_id, Snapshot.id < snapshot_id
        )
        .order_by(Snapshot.id.desc())
        .first()
    )


def get_monitor_stats(monitor_id: int) -> Dict[str, Any]:
    """Get comprehensive stats for a monitor"""
    monitor = Monitor.query.get(monitor_id)
    if not monitor:
        return {}
    
    snapshots = Snapshot.query.filter_by(monitor_id=monitor_id).all()
    changes = [s for s in snapshots if s.content_hash]
    errors = [s for s in snapshots if s.error_message]
    
    response_times = [s.response_time_ms for s in snapshots if s.response_time_ms]
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    return {
        "total_snapshots": len(snapshots),
        "total_changes": len(changes),
        "total_errors": len(errors),
        "avg_response_time_ms": int(avg_response_time),
        "uptime_percentage": ((monitor.total_checks - len(errors)) / monitor.total_checks * 100) if monitor.total_checks > 0 else 100,
        "last_error": errors[-1].error_message if errors else None,
        "status": monitor.status
    }