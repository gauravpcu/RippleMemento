import json
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
import requests
from .extensions import db
from .models_enhanced import NotificationEndpoint, MonitorHistory


class NotificationService:
    def __init__(self):
        pass

    def send_notification(self, monitor, snapshot, notification_type="change"):
        """Send notifications for a monitor change/error"""
        endpoints = NotificationEndpoint.query.filter_by(active=True).all()
        
        for endpoint in endpoints:
            try:
                config = json.loads(endpoint.config)
                
                if endpoint.type == "email":
                    self._send_email(monitor, snapshot, config, notification_type)
                elif endpoint.type == "webhook":
                    self._send_webhook(monitor, snapshot, config, notification_type)
                elif endpoint.type == "discord":
                    self._send_discord(monitor, snapshot, config, notification_type)
                elif endpoint.type == "slack":
                    self._send_slack(monitor, snapshot, config, notification_type)
                    
            except Exception as e:
                print(f"Failed to send notification via {endpoint.name}: {e}")

    def _send_email(self, monitor, snapshot, config: Dict[str, Any], notification_type: str):
        subject = f"RippleMemento: {monitor.name} - {notification_type.title()}"
        
        if notification_type == "change":
            body = f"""
            Monitor: {monitor.name}
            URL: {monitor.url}
            
            A change was detected on this page.
            
            View details: http://localhost:5050/monitors/{monitor.id}/snapshots/{snapshot.id}
            """
        else:
            body = f"""
            Monitor: {monitor.name}
            URL: {monitor.url}
            
            Error: {getattr(snapshot, 'error_message', 'Unknown error')}
            """

        msg = MIMEMultipart()
        msg['From'] = config['from_email']
        msg['To'] = config['to_email']
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(config['smtp_host'], config.get('smtp_port', 587))
        if config.get('use_tls', True):
            server.starttls()
        if config.get('username') and config.get('password'):
            server.login(config['username'], config['password'])
        server.send_message(msg)
        server.quit()

    def _send_webhook(self, monitor, snapshot, config: Dict[str, Any], notification_type: str):
        payload = {
            "monitor_name": monitor.name,
            "monitor_url": monitor.url,
            "notification_type": notification_type,
            "snapshot_id": snapshot.id if snapshot else None,
            "timestamp": time.time(),
            "details_url": f"http://localhost:5050/monitors/{monitor.id}"
        }
        
        if notification_type == "error" and snapshot:
            payload["error_message"] = getattr(snapshot, 'error_message', 'Unknown error')
            
        headers = config.get('headers', {})
        headers.setdefault('Content-Type', 'application/json')
        
        requests.post(
            config['url'],
            json=payload,
            headers=headers,
            timeout=10
        )

    def _send_discord(self, monitor, snapshot, config: Dict[str, Any], notification_type: str):
        if notification_type == "change":
            color = 0x00ff00  # Green
            description = f"🔄 **Change detected** in [{monitor.name}]({monitor.url})"
        else:
            color = 0xff0000  # Red
            description = f"❌ **Error** monitoring [{monitor.name}]({monitor.url})"
            if snapshot and hasattr(snapshot, 'error_message'):
                description += f"\n```{snapshot.error_message}```"

        embed = {
            "title": "RippleMemento Alert",
            "description": description,
            "color": color,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            "footer": {"text": "RippleMemento"}
        }

        payload = {"embeds": [embed]}
        
        requests.post(config['webhook_url'], json=payload, timeout=10)

    def _send_slack(self, monitor, snapshot, config: Dict[str, Any], notification_type: str):
        if notification_type == "change":
            color = "good"
            text = f":arrows_counterclockwise: Change detected in <{monitor.url}|{monitor.name}>"
        else:
            color = "danger" 
            text = f":x: Error monitoring <{monitor.url}|{monitor.name}>"
            if snapshot and hasattr(snapshot, 'error_message'):
                text += f"\n```{snapshot.error_message}```"

        payload = {
            "attachments": [{
                "color": color,
                "text": text,
                "footer": "RippleMemento",
                "ts": int(time.time())
            }]
        }

        requests.post(config['webhook_url'], json=payload, timeout=10)


def log_monitor_event(monitor_id: int, event_type: str, message: str = ""):
    """Log an event for monitoring history"""
    history = MonitorHistory(
        monitor_id=monitor_id,
        event_type=event_type,
        message=message
    )
    db.session.add(history)
    db.session.commit()


notification_service = NotificationService()