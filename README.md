# RippleMemento

RippleMemento is a modern, feature-rich web monitoring application inspired by changedetection.io. It tracks changes on web pages you care about with a beautiful, responsive UI and comprehensive monitoring capabilities.

## 🌟 Features

### Core Monitoring
- **Smart Content Detection**: Monitors any URL with optional CSS selectors
- **Flexible Scheduling**: Per-monitor intervals from minutes to hours
- **Visual Diff Engine**: HTML-based diff visualization showing exactly what changed
- **Hash-based Change Detection**: Efficient content comparison using SHA-256 hashing

### User Experience
- **Modern UI**: Clean, responsive design built with Tailwind CSS
- **Real-time Status**: Live monitoring status with visual indicators
- **Instant Actions**: "Check now" button for immediate manual checks
- **Comprehensive History**: Full snapshot history with timestamps

### Advanced Features (Enhanced Version)
- **Multi-channel Notifications**: Email, Discord, Slack, and webhook support
- **Smart Filtering**: Ignore specific text patterns or trigger only on keywords
- **Custom Headers**: Support for authenticated endpoints and API monitoring
- **Tagging System**: Organize monitors with custom colored tags
- **Analytics Dashboard**: Statistics, uptime tracking, and performance metrics
- **REST API**: Programmatic access to all monitoring functions
- **Error Handling**: Robust error tracking with retry logic and notifications

## 🚀 Quick Start

### 1. Setup Environment
```bash
cd /Users/gaurav/Desktop/RippleMemento
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python run.py
# Or alternatively:
export FLASK_APP=ripplememento
flask run --port 5050
```

### 3. Access the App
Open your browser to: **http://127.0.0.1:5050**

## 📊 Dashboard Overview

The main dashboard provides:
- **Quick Stats**: Total monitors, active counts, error summaries
- **Status Indicators**: Visual status for each monitor (active, paused, error, stale)
- **Tag Filtering**: Filter monitors by custom tags
- **Bulk Actions**: Manage multiple monitors efficiently

## 🛠️ Configuration Options

### Monitor Settings
- **URL**: Any HTTP/HTTPS endpoint
- **CSS Selector**: Target specific page elements (e.g., `#main-content`, `.article`)
- **Check Interval**: From 1 minute to any custom interval
- **Active/Inactive**: Pause monitoring without deletion

### Advanced Configuration (Enhanced)
- **Custom Headers**: JSON-formatted HTTP headers for authentication
- **Ignore Patterns**: Text to exclude from change detection
- **Trigger Keywords**: Only alert when specific words appear
- **Notification Settings**: Per-monitor notification preferences

## 📧 Notification Setup

Configure multiple notification channels:

### Email
```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "username": "your-email@gmail.com",
  "password": "your-app-password",
  "from_email": "alerts@yourapp.com",
  "to_email": "recipient@example.com",
  "use_tls": true
}
```

### Discord/Slack Webhooks
```json
{
  "webhook_url": "https://discord.com/api/webhooks/..."
}
```

### Custom Webhooks
```json
{
  "url": "https://your-api.com/webhook",
  "headers": {
    "Authorization": "Bearer your-token",
    "Content-Type": "application/json"
  }
}
```

## 🔧 Technical Architecture

### Core Components
- **Flask**: Web framework with blueprints for modular design
- **SQLAlchemy**: Database ORM with SQLite for simplicity
- **APScheduler**: Background task scheduling for automated checks
- **BeautifulSoup**: HTML parsing and content extraction
- **diff-match-patch**: Advanced diff algorithm for change visualization

### Database Schema
- **Monitors**: URL, settings, scheduling, and status tracking
- **Snapshots**: Historical content with hashes and timestamps
- **Tags**: Organizational system with custom colors
- **Notifications**: Multi-channel notification endpoints
- **History**: Event logging for debugging and analytics

### File Structure
```
RippleMemento/
├── ripplememento/
│   ├── __init__.py          # App factory
│   ├── models.py            # Database models
│   ├── routes.py            # Web routes and API
│   ├── services.py          # Core monitoring logic
│   ├── tasks.py             # Background scheduler
│   ├── extensions.py        # Flask extensions
│   └── templates/           # Jinja2 templates
├── requirements.txt         # Python dependencies
├── run.py                  # Development server
└── README.md               # This file
```

## 🚀 Deployment Options

### Development
```bash
python run.py
```

### Production (Basic)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5050 "ripplememento:create_app()"
```

### Docker (Future Enhancement)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5050", "ripplememento:create_app()"]
```

## 🔮 Roadmap

### Immediate Enhancements
- [ ] Screenshot monitoring for visual changes
- [ ] JavaScript rendering with Playwright/Selenium
- [ ] JSON API monitoring with JSONPath selectors
- [ ] Export/import monitor configurations
- [ ] User authentication and multi-tenancy

### Advanced Features
- [ ] Browser automation for complex scenarios
- [ ] Machine learning for intelligent change detection
- [ ] Performance monitoring and alerting
- [ ] Integration with monitoring platforms (Grafana, Prometheus)
- [ ] Mobile app for notifications

## 🤝 Contributing

RippleMemento is built with extensibility in mind:

1. **Add New Fetchers**: Extend `services.py` for different content types
2. **Custom Notifications**: Implement new notification channels in `notifications.py`
3. **UI Improvements**: Enhance templates with modern web technologies
4. **API Extensions**: Add new endpoints in `routes.py`

## 📄 License

MIT License - Feel free to use this project for personal or commercial purposes.

## 🙏 Acknowledgments

- Inspired by the excellent [changedetection.io](https://github.com/dgtlmoon/changedetection.io) project
- Built with modern web technologies and best practices
- Designed for simplicity, performance, and extensibility

---

**RippleMemento** - _"Catch every ripple of change across the web"_ 🌊
