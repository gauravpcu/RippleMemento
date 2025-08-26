import hashlib
import json
import re
from typing import Optional
import requests
from bs4 import BeautifulSoup
from diff_match_patch import diff_match_patch
from .models import Monitor, Snapshot
from .extensions import db


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)


def fetch_text(url: str, css_selector: Optional[str] = None, custom_headers: Optional[str] = None) -> str:
    headers = {"User-Agent": USER_AGENT}
    
    # Parse custom headers if provided
    if custom_headers:
        try:
            headers.update(json.loads(custom_headers))
        except:
            pass
    
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    
    if css_selector:
        node = soup.select_one(css_selector)
        if node:
            return resp.text, node.get_text("\n", strip=True)
        else:
            return resp.text, ""
    else:
        for s in soup(["script", "style", "noscript"]):
            s.decompose()
        return resp.text, soup.get_text("\n", strip=True)


def process_content_by_style(content: str, style: str, ignore_whitespace: bool = True, ignore_case: bool = False) -> str:
    """Process content based on monitoring style"""
    if ignore_case:
        content = content.lower()
    
    if style == 'words':
        # Split into words, optionally ignore whitespace changes
        words = content.split()
        return ' '.join(words) if ignore_whitespace else content
    
    elif style == 'lines':
        # Process line by line
        lines = content.split('\n')
        if ignore_whitespace:
            lines = [line.strip() for line in lines if line.strip()]
        return '\n'.join(lines)
    
    elif style == 'paragraphs':
        # Process paragraph by paragraph (double newlines separate paragraphs)
        paragraphs = re.split(r'\n\s*\n', content)
        if ignore_whitespace:
            paragraphs = [p.strip() for p in paragraphs if p.strip()]
        return '\n\n'.join(paragraphs)
    
    elif style == 'chars':
        # Character-level monitoring
        if ignore_whitespace:
            return re.sub(r'\s+', ' ', content).strip()
        return content
    
    elif style == 'json':
        # Try to parse and normalize JSON
        try:
            parsed = json.loads(content)
            return json.dumps(parsed, sort_keys=True, separators=(',', ':'))
        except:
            # If not valid JSON, fall back to text processing
            return content.strip()
    
    # Default fallback
    return content


def apply_filters(text: str, monitor: Monitor) -> str:
    """Apply ignore/trigger text filters"""
    if monitor.ignore_text:
        ignore_patterns = [p.strip() for p in monitor.ignore_text.split('\n') if p.strip()]
        for pattern in ignore_patterns:
            text = text.replace(pattern, '')
    
    if monitor.trigger_text:
        trigger_patterns = [p.strip() for p in monitor.trigger_text.split('\n') if p.strip()]
        # Only return text if it contains any trigger pattern
        if not any(pattern.lower() in text.lower() for pattern in trigger_patterns):
            return ""
    
    return text.strip()


def hash_text(text: str) -> str:
    """Calculate MD5 hash for change detection (new approach)"""
    import hashlib
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def calculate_content_hash(content: str, style: str, ignore_whitespace: bool = True, ignore_case: bool = False) -> str:
    """Calculate hash after applying style-specific processing (new approach)"""
    processed = process_content_by_style(content, style, ignore_whitespace, ignore_case)
    return hash_text(processed)


def compute_diff(prev: str, current: str, style: str = 'words') -> tuple[str, int]:
    """Generate HTML diff with change count based on style - new inspired approach"""
    
    # For JavaScript-based diff switching, we'll store both versions and let client handle rendering
    # But also provide server-side fallback
    
    if style == 'paragraphs':
        # Paragraph-aware diff with inline changes
        return compute_paragraph_diff(prev, current, diff_match_patch())
    elif style == 'lines':
        # Line-by-line diff with inline changes  
        return compute_line_diff(prev, current, diff_match_patch())
    elif style == 'chars':
        # Character-by-character diff
        return compute_char_diff(prev, current, diff_match_patch())
    elif style == 'words':
        # Word-based diff
        return compute_word_diff(prev, current, diff_match_patch())
    elif style == 'json':
        # JSON-aware diff
        return compute_json_diff(prev, current, diff_match_patch())
    else:
        # Default to word-based diff
        return compute_word_diff(prev, current, diff_match_patch())


def compute_paragraph_diff(prev: str, current: str, dmp) -> tuple[str, int]:
    """Generate paragraph-aware diff showing inline changes within paragraphs"""
    # Split into paragraphs
    prev_paragraphs = re.split(r'\n\s*\n', prev)
    current_paragraphs = re.split(r'\n\s*\n', current)
    
    html = []
    total_changes = 0
    
    # Use SequenceMatcher to find which paragraphs correspond
    from difflib import SequenceMatcher
    matcher = SequenceMatcher(None, prev_paragraphs, current_paragraphs)
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # Unchanged paragraphs
            for p in current_paragraphs[j1:j2]:
                if p.strip():
                    html.append(f"<p class='text-gray-700 mb-4'>{escape_html(p)}</p>")
        
        elif tag == 'replace':
            # Modified paragraphs - show inline changes
            for old_p, new_p in zip(prev_paragraphs[i1:i2], current_paragraphs[j1:j2]):
                para_diffs = dmp.diff_main(old_p, new_p)
                dmp.diff_cleanupSemantic(para_diffs)
                
                para_html = []
                para_changes = 0
                
                for op, data in para_diffs:
                    if op == 0:  # Equal
                        para_html.append(escape_html(data))
                    elif op == 1:  # Insertion
                        para_changes += len(data.split())
                        para_html.append(f"<span class='bg-green-100 text-green-800 px-1 rounded font-medium' title='Added'>{escape_html(data)}</span>")
                    else:  # Deletion
                        para_changes += len(data.split())
                        para_html.append(f"<span class='bg-red-100 text-red-800 px-1 rounded font-medium line-through' title='Removed'>{escape_html(data)}</span>")
                
                if para_changes > 0:
                    html.append(f"<p class='bg-yellow-50 border-l-4 border-yellow-400 pl-4 mb-4 text-gray-800'>{''.join(para_html)}</p>")
                    total_changes += para_changes
                else:
                    html.append(f"<p class='text-gray-700 mb-4'>{''.join(para_html)}</p>")
        
        elif tag == 'delete':
            # Deleted paragraphs
            for p in prev_paragraphs[i1:i2]:
                if p.strip():
                    total_changes += len(p.split())
                    html.append(f"<p class='bg-red-50 border-l-4 border-red-400 pl-4 mb-4'><span class='bg-red-100 text-red-800 px-1 rounded font-medium line-through' title='Removed paragraph'>{escape_html(p)}</span></p>")
        
        elif tag == 'insert':
            # Added paragraphs
            for p in current_paragraphs[j1:j2]:
                if p.strip():
                    total_changes += len(p.split())
                    html.append(f"<p class='bg-green-50 border-l-4 border-green-400 pl-4 mb-4'><span class='bg-green-100 text-green-800 px-1 rounded font-medium' title='Added paragraph'>{escape_html(p)}</span></p>")
    
    return "".join(html), total_changes


def compute_line_diff(prev: str, current: str, dmp) -> tuple[str, int]:
    """Generate line-aware diff showing inline changes within lines"""
    prev_lines = prev.split('\n')
    current_lines = current.split('\n')
    
    html = []
    total_changes = 0
    
    from difflib import SequenceMatcher
    matcher = SequenceMatcher(None, prev_lines, current_lines)
    
    html.append("<div class='font-mono text-sm'>")
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # Unchanged lines
            for line in current_lines[j1:j2]:
                html.append(f"<div class='text-gray-700 py-1'>{escape_html(line)}</div>")
        
        elif tag == 'replace':
            # Modified lines - show inline changes
            for old_line, new_line in zip(prev_lines[i1:i2], current_lines[j1:j2]):
                line_diffs = dmp.diff_main(old_line, new_line)
                dmp.diff_cleanupSemantic(line_diffs)
                
                line_html = []
                line_changes = 0
                
                for op, data in line_diffs:
                    if op == 0:  # Equal
                        line_html.append(escape_html(data))
                    elif op == 1:  # Insertion
                        line_changes += len(data)
                        line_html.append(f"<span class='bg-green-100 text-green-800 px-1 rounded' title='Added'>{escape_html(data)}</span>")
                    else:  # Deletion
                        line_changes += len(data)
                        line_html.append(f"<span class='bg-red-100 text-red-800 px-1 rounded line-through' title='Removed'>{escape_html(data)}</span>")
                
                if line_changes > 0:
                    html.append(f"<div class='bg-yellow-50 border-l-4 border-yellow-400 pl-2 py-1'>{''.join(line_html)}</div>")
                    total_changes += 1
                else:
                    html.append(f"<div class='text-gray-700 py-1'>{''.join(line_html)}</div>")
        
        elif tag == 'delete':
            # Deleted lines
            for line in prev_lines[i1:i2]:
                total_changes += 1
                html.append(f"<div class='bg-red-50 border-l-4 border-red-400 pl-2 py-1'><span class='bg-red-100 text-red-800 px-1 rounded line-through' title='Removed line'>{escape_html(line)}</span></div>")
        
        elif tag == 'insert':
            # Added lines
            for line in current_lines[j1:j2]:
                total_changes += 1
                html.append(f"<div class='bg-green-50 border-l-4 border-green-400 pl-2 py-1'><span class='bg-green-100 text-green-800 px-1 rounded' title='Added line'>{escape_html(line)}</span></div>")
    
    html.append("</div>")
    return "".join(html), total_changes


def compute_word_diff(prev: str, current: str, dmp) -> tuple[str, int]:
    """Generate word-based diff with enhanced formatting"""
    diffs = dmp.diff_main(prev, current)
    dmp.diff_cleanupSemantic(diffs)
    
    html = []
    change_count = 0
    
    html.append("<div class='diff-content word-diff'>")
    
    for op, data in diffs:
        if op == 0:  # Equal
            # Truncate long unchanged sections for readability
            if len(data) > 300:
                words = data.split()
                if len(words) > 20:
                    context_start = ' '.join(words[:10])
                    context_end = ' '.join(words[-10:])
                    data = f"{context_start} <span class='text-center text-gray-400 text-sm px-2 py-1 bg-gray-100 rounded'>... ({len(words)-20} words unchanged) ...</span> {context_end}"
            html.append(f"<span class='text-gray-700'>{escape_html(data)}</span>")
        elif op == 1:  # Insertion
            word_count = len(data.split())
            change_count += word_count
            html.append(f"<span class='bg-green-100 text-green-800 px-1 rounded font-medium border-l-2 border-green-400' title='Added {word_count} word(s)'>{escape_html(data)}</span>")
        else:  # Deletion
            word_count = len(data.split())
            change_count += word_count
            html.append(f"<span class='bg-red-100 text-red-800 px-1 rounded font-medium line-through border-l-2 border-red-400' title='Removed {word_count} word(s)'>{escape_html(data)}</span>")
    
    html.append("</div>")
    return "".join(html), change_count


def compute_char_diff(prev: str, current: str, dmp) -> tuple[str, int]:
    """Generate character-based diff with enhanced formatting"""
    diffs = dmp.diff_main(prev, current)
    dmp.diff_cleanupSemantic(diffs)
    
    html = []
    change_count = 0
    
    html.append("<div class='diff-content char-diff font-mono text-sm'>")
    
    for op, data in diffs:
        if op == 0:  # Equal
            # Show more context for character diffs but truncate very long sections
            if len(data) > 500:
                visible_start = data[:200]
                visible_end = data[-200:]
                hidden_count = len(data) - 400
                data = f"{visible_start}<span class='text-center text-gray-400 text-xs px-2 py-1 bg-gray-100 rounded mx-1'>... ({hidden_count} chars unchanged) ...</span>{visible_end}"
            html.append(f"<span class='text-gray-600'>{escape_html(data)}</span>")
        elif op == 1:  # Insertion
            char_count = len(data)
            change_count += char_count
            # Highlight individual characters with subtle background
            html.append(f"<span class='bg-green-200 text-green-900 px-0.5 rounded font-bold border border-green-300' title='Added {char_count} character(s)'>{escape_html(data)}</span>")
        else:  # Deletion
            char_count = len(data)
            change_count += char_count
            html.append(f"<span class='bg-red-200 text-red-900 px-0.5 rounded font-bold line-through border border-red-300' title='Removed {char_count} character(s)'>{escape_html(data)}</span>")
    
    html.append("</div>")
    return "".join(html), change_count


def compute_json_diff(prev: str, current: str, dmp) -> tuple[str, int]:
    """Generate JSON-aware diff with enhanced formatting"""
    import json
    
    try:
        # Try to parse as JSON for intelligent comparison
        prev_json = json.loads(prev) if prev.strip() else {}
        current_json = json.loads(current) if current.strip() else {}
        
        # Pretty format for comparison
        prev_formatted = json.dumps(prev_json, indent=2, sort_keys=True)
        current_formatted = json.dumps(current_json, indent=2, sort_keys=True)
        
        # Use line-based diff for formatted JSON
        diffs = dmp.diff_main(prev_formatted, current_formatted)
        dmp.diff_cleanupSemantic(diffs)
        
        html = []
        change_count = 0
        
        html.append("<div class='diff-content json-diff font-mono text-sm'>")
        
        for op, data in diffs:
            if op == 0:  # Equal
                html.append(f"<span class='text-gray-600'>{escape_html(data)}</span>")
            elif op == 1:  # Insertion
                lines = data.split('\n')
                change_count += len([line for line in lines if line.strip()])
                html.append(f"<span class='bg-green-100 text-green-800 px-1 rounded font-medium border-l-2 border-green-400' title='Added JSON content'>{escape_html(data)}</span>")
            else:  # Deletion
                lines = data.split('\n')
                change_count += len([line for line in lines if line.strip()])
                html.append(f"<span class='bg-red-100 text-red-800 px-1 rounded font-medium line-through border-l-2 border-red-400' title='Removed JSON content'>{escape_html(data)}</span>")
        
        html.append("</div>")
        
    except (json.JSONDecodeError, TypeError):
        # Fall back to regular text diff if not valid JSON
        return compute_word_diff(prev, current, dmp)
    
    return "".join(html), change_count


def escape_html(text: str) -> str:
    """Escape HTML characters"""
    import html
    return html.escape(text).replace('\n', '<br>')


def record_snapshot(monitor: Monitor, raw_content: str, processed_content: str, change_count: int = 0, error_message: str = None) -> Snapshot:
    """Record a new snapshot with proper hash calculation (new approach)"""
    content_hash = calculate_content_hash(processed_content, monitor.monitor_style, monitor.ignore_whitespace, monitor.ignore_case) if processed_content else None
    
    snap = Snapshot(
        monitor=monitor, 
        content_hash=content_hash, 
        content_text=processed_content,
        content_raw=raw_content,
        change_count=change_count,
        error_message=error_message
    )
    db.session.add(snap)
    db.session.commit()
    return snap


def check_monitor(monitor: Monitor) -> Optional[Snapshot]:
    """Enhanced monitor checking with new approach"""
    try:
        # Fetch content
        raw_content, text_content = fetch_text(monitor.url, monitor.css_selector, monitor.custom_headers)
        
        # Apply filters
        filtered_content = apply_filters(text_content, monitor)
        
        # Process based on monitoring style
        processed_content = process_content_by_style(
            filtered_content, 
            monitor.monitor_style, 
            monitor.ignore_whitespace, 
            monitor.ignore_case
        )
        
        # Get last snapshot for comparison
        last = (
            Snapshot.query.filter_by(monitor_id=monitor.id)
            .order_by(Snapshot.created_at.desc())
            .first()
        )
        
        # Update monitor timestamp
        monitor.last_checked = db.func.now()
        
        # Calculate MD5 hash for change detection (new approach)
        current_hash = calculate_content_hash(processed_content, monitor.monitor_style, monitor.ignore_whitespace, monitor.ignore_case)
        
        # Check for changes using MD5 comparison
        has_changed = not last or (last.content_hash != current_hash and processed_content)
        
        change_count = 0
        diff_html = ""
        
        if has_changed and last and last.content_text:
            # Calculate detailed diff only when MD5 hashes don't match (new approach)
            diff_html, change_count = compute_diff(last.content_text, processed_content, monitor.monitor_style)
            
            # Apply trigger threshold check
            if change_count < monitor.trigger_threshold:
                # Changes exist but below threshold - don't treat as significant change
                has_changed = False
                change_count = 0
                diff_html = ""
        
        # Always create a snapshot for monitoring history
        snap = record_snapshot(monitor, raw_content, processed_content, change_count)
        snap.content_hash = current_hash
        
        # Store the diff in the snapshot if there were significant changes
        if has_changed and diff_html:
            snap.diff_html = diff_html
        
        db.session.commit()
        return snap
        
    except Exception as e:
        # Handle errors
        monitor.last_checked = db.func.now()
        error_snap = record_snapshot(monitor, "", "", 0, str(e))
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


def get_snapshots_by_date_range(monitor_id: int, start_date: str, end_date: str) -> list[Snapshot]:
    """Get snapshots within a date range for comparison"""
    from datetime import datetime
    
    try:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except:
        # Fallback to simple date parsing
        start_dt = datetime.strptime(start_date.split('T')[0], '%Y-%m-%d')
        end_dt = datetime.strptime(end_date.split('T')[0], '%Y-%m-%d')
    
    return (
        Snapshot.query.filter(
            Snapshot.monitor_id == monitor_id,
            Snapshot.created_at >= start_dt,
            Snapshot.created_at <= end_dt,
            Snapshot.error_message.is_(None)  # Only include successful snapshots
        )
        .order_by(Snapshot.created_at.asc())
        .all()
    )


def get_snapshot_by_date(monitor_id: int, target_date: str) -> Optional[Snapshot]:
    """Get the closest snapshot to a specific date"""
    from datetime import datetime
    
    try:
        target_dt = datetime.fromisoformat(target_date.replace('Z', '+00:00'))
    except:
        target_dt = datetime.strptime(target_date.split('T')[0], '%Y-%m-%d')
    
    # Find the closest snapshot to the target date
    return (
        Snapshot.query.filter(
            Snapshot.monitor_id == monitor_id,
            Snapshot.created_at <= target_dt,
            Snapshot.error_message.is_(None)
        )
        .order_by(Snapshot.created_at.desc())
        .first()
    )


def get_recent_snapshots(monitor_id: int, limit: int = 10) -> list[Snapshot]:
    """Get recent snapshots for a monitor"""
    return (
        Snapshot.query.filter(
            Snapshot.monitor_id == monitor_id,
            Snapshot.error_message.is_(None)
        )
        .order_by(Snapshot.created_at.desc())
        .limit(limit)
        .all()
    )
