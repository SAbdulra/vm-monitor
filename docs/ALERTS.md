# VM Monitor - Alert & Notification System

Comprehensive guide to configuring and using the alert notification system.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Supported Channels](#supported-channels)
- [Alert Types](#alert-types)
- [Configuration](#configuration)
- [Alert Thresholds](#alert-thresholds)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Examples](#examples)

---

## 🔔 Overview

VM Monitor includes an intelligent alert system that notifies you of critical infrastructure events via:
- 📧 **Email** (SMTP)
- 💬 **Slack** (Webhook)

**Key Features:**
- Configurable thresholds for CPU, Memory, and Disk
- CVE vulnerability alerts
- VM offline detection
- Smart alert cooldown (prevents spam)
- HTML-formatted emails
- Rich Slack messages with formatted fields

---

## 📢 Supported Channels

### 1. Email (SMTP)

Sends HTML-formatted emails with detailed alert information.

**Supported Providers:**
- Gmail (with App Passwords)
- Office 365 / Outlook
- SendGrid
- Amazon SES
- Custom SMTP servers

### 2. Slack

Sends formatted messages to Slack channels via incoming webhooks.

**Features:**
- Color-coded by severity
- Structured field layout
- Clickable links
- Timestamps

---

## 🚨 Alert Types

### 1. **VM Critical Resource Alert**

Triggered when VM exceeds critical thresholds.

**Conditions:**
- CPU usage > 95% (configurable)
- Memory usage > 95% (configurable)
- Disk usage > 95% (configurable)

**Notification Includes:**
- Hostname
- Current CPU/Memory/Disk percentages
- Status (WARNING/CRITICAL) per metric
- Timestamp
- Link to dashboard

**Example Email:**

```
Subject: [VM Monitor] 🚨 CRITICAL: web-server-01 - High Resource Usage

⚠️ Critical Alert: VM web-server-01

The following VM has exceeded critical thresholds:

| Metric       | Value  | Status   |
|--------------|--------|----------|
| CPU Usage    | 97.2%  | CRITICAL |
| Memory Usage | 89.5%  | WARNING  |
| Disk Usage   | 78.3%  | OK       |

Time: 2026-08-05 14:30:15
Action Required: Investigate immediately
```

---

### 2. **VM Offline Alert**

Triggered when VM stops reporting metrics.

**Conditions:**
- No metrics received for 10+ minutes (configurable)

**Notification Includes:**
- Hostname
- Last seen timestamp
- Offline duration
- Possible causes

**Example Slack:**

```
⚠️ VM Offline: db-server-03

No metrics received for 15 minutes

Last Seen: 2026-08-05 14:15:00
```

---

### 3. **CVE Security Alert**

Triggered when critical vulnerabilities are detected.

**Conditions:**
- Critical CVEs (CVSS ≥ 9.0): >= 1
- High CVEs (CVSS 7.0-8.9): >= 5

**Notification Includes:**
- Hostname
- Count of Critical and High CVEs
- Severity breakdown
- Action recommendations

**Example:**

```
🛡️ Security Alert: app-server-02 - Critical CVEs Detected

Critical CVE vulnerabilities detected

| Severity             | Count |
|----------------------|-------|
| Critical (CVSS ≥ 9)  | 3     |
| High (CVSS 7-8.9)    | 7     |

Action Required:
- Review vulnerabilities in dashboard
- Apply security patches immediately
- Update affected packages
```

---

### 4. **System Startup Notification**

Informational alert when VM Monitor starts.

**Notification:**
- Simple "System Online" message
- Timestamp
- Sent to Slack only

---

## ⚙️ Configuration

### Step 1: Enable Notifications

Edit `.env` file:

```bash
# Enable email
EMAIL_ENABLED=true

# Enable Slack
SLACK_ENABLED=true
```

### Step 2: Configure Email (SMTP)

#### Gmail Example

1. **Enable 2-Factor Authentication** on your Google account
2. **Generate App Password:**
   - Go to: https://myaccount.google.com/apppasswords
   - Select "Mail" and "Other (Custom name)"
   - Name it "VM Monitor"
   - Copy the generated 16-character password

3. **Configure in `.env`:**

```bash
EMAIL_ENABLED=true
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop  # App Password (remove spaces)
SMTP_FROM_EMAIL=vm-monitor@yourcompany.com
ALERT_EMAIL_TO=admin@yourcompany.com,ops-team@yourcompany.com
```

#### Office 365 Example

```bash
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=alerts@yourcompany.com
SMTP_PASSWORD=your_password_here
```

#### SendGrid Example

```bash
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=SG.your_api_key_here
```

### Step 3: Configure Slack

1. **Create Incoming Webhook:**
   - Go to: https://api.slack.com/messaging/webhooks
   - Click "Create New App" → "From scratch"
   - Name: "VM Monitor Alerts"
   - Select your workspace
   - Click "Incoming Webhooks"
   - Toggle "Activate Incoming Webhooks" to **ON**
   - Click "Add New Webhook to Workspace"
   - Select channel (e.g., #infrastructure-alerts)
   - Copy the Webhook URL

2. **Configure in `.env`:**

```bash
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX
```

---

## 🎯 Alert Thresholds

Customize when alerts are triggered:

```bash
# CPU Thresholds
ALERT_CPU_WARNING=80   # Yellow alert at 80%
ALERT_CPU_CRITICAL=95  # Red alert at 95%

# Memory Thresholds
ALERT_MEMORY_WARNING=80
ALERT_MEMORY_CRITICAL=95

# Disk Thresholds
ALERT_DISK_WARNING=85
ALERT_DISK_CRITICAL=95

# CVE Thresholds
ALERT_CVE_CRITICAL_COUNT=1  # Alert if >= 1 critical CVE
ALERT_CVE_HIGH_COUNT=5      # Alert if >= 5 high CVEs

# Offline Detection
ALERT_VM_OFFLINE_MINUTES=10  # Alert after 10 min offline

# Cooldown (anti-spam)
ALERT_COOLDOWN_MINUTES=60  # Max 1 alert per hour per issue
```

### Recommended Thresholds

| Environment | CPU Critical | Memory Critical | Disk Critical |
|-------------|--------------|-----------------|---------------|
| Production  | 90%          | 90%             | 90%           |
| Staging     | 95%          | 95%             | 95%           |
| Development | 98%          | 98%             | 98%           |

---

## 🧪 Testing

### Test Email Configuration

```python
# Python test script
import smtplib
from email.mime.text import MIMEText

msg = MIMEText("Test alert from VM Monitor")
msg['Subject'] = '[VM Monitor] Test Alert'
msg['From'] = 'your.email@gmail.com'
msg['To'] = 'admin@yourcompany.com'

with smtplib.SMTP('smtp.gmail.com', 587) as server:
    server.starttls()
    server.login('your.email@gmail.com', 'app_password_here')
    server.send_message(msg)
    print("✓ Test email sent!")
```

### Test Slack Webhook

```bash
# Using curl
curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "🧪 Test alert from VM Monitor",
    "attachments": [{
      "color": "#36a64f",
      "title": "Test Successful",
      "text": "If you see this, Slack alerts are working!"
    }]
  }'
```

### Trigger Test Alert

Temporarily lower thresholds to trigger an alert:

```bash
# In .env
ALERT_CPU_CRITICAL=5  # Will alert on any VM with >5% CPU
```

Restart backend and wait for next metric update.

---

## 🔧 Troubleshooting

### Email Not Sending

**1. Check SMTP credentials:**
```bash
# Test connection
telnet smtp.gmail.com 587
```

**2. Gmail App Password issues:**
- Ensure 2FA is enabled
- Generate new App Password
- Remove spaces from password in .env

**3. Firewall blocking:**
```bash
# Allow SMTP port
firewall-cmd --permanent --add-port=587/tcp
firewall-cmd --reload
```

**4. Check logs:**
```bash
docker logs vm-monitor-backend-1 | grep -i "email"
```

---

### Slack Not Receiving

**1. Verify webhook URL:**
- Ensure no extra spaces
- Test with curl (see above)

**2. Check workspace permissions:**
- Webhook URL might be revoked
- Regenerate if needed

**3. Channel access:**
- Ensure bot has access to target channel

**4. Check logs:**
```bash
docker logs vm-monitor-backend-1 | grep -i "slack"
```

---

### Alerts Not Triggering

**1. Verify thresholds:**
```bash
# Check current VM metrics
curl http://localhost:8001/api/dashboard/metrics

# Are any VMs actually exceeding thresholds?
```

**2. Check cooldown:**
```bash
# Alert may be in cooldown period
# Wait ALERT_COOLDOWN_MINUTES before next alert
```

**3. Enable debug logging:**
```bash
# In .env
LOG_LEVEL=DEBUG
```

**4. Restart backend:**
```bash
docker-compose restart backend
```

---

## 📧 Email Providers Setup

### Gmail

1. Enable 2FA: https://myaccount.google.com/security
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Use settings above

### Office 365

```bash
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=alerts@yourcompany.com
SMTP_PASSWORD=your_o365_password
```

### AWS SES

```bash
SMTP_SERVER=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USERNAME=your_ses_smtp_username
SMTP_PASSWORD=your_ses_smtp_password
```

### SendGrid

```bash
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=SG.your_sendgrid_api_key
```

---

## 💡 Best Practices

### 1. **Use Dedicated Email**

Create a dedicated email for alerts:
```
vm-monitor-alerts@yourcompany.com
```

### 2. **Separate Slack Channels**

```
#infra-critical   - Critical alerts only
#infra-warnings   - Warning-level alerts
#infra-info       - System status updates
```

### 3. **Alert Routing**

Configure different recipients by severity:

```bash
# Critical -> PagerDuty + Email
# Warning -> Email only
# Info -> Slack only
```

### 4. **Monitor Alert Volume**

Too many alerts = alert fatigue

**Solutions:**
- Increase thresholds
- Increase cooldown
- Fix root causes
- Use aggregation

### 5. **Test Regularly**

Schedule monthly alert tests:
```bash
# First Monday of each month
0 9 1-7 * 1 /usr/local/bin/test-alerts.sh
```

---

## 🎛️ Advanced Configuration

### Alert Routing by Time

Only send critical alerts during business hours:

```python
# In notification_service.py
from datetime import datetime

def should_alert_now():
    hour = datetime.now().hour
    # Only alert 9 AM - 5 PM
    return 9 <= hour < 17
```

### Custom Alert Templates

Modify HTML templates in `notification_service.py`:

```python
email_body = f"""
<html>
<body style="font-family: 'Your Company Font';">
    <!-- Your custom template -->
</body>
</html>
"""
```

### Integration with PagerDuty

Add PagerDuty integration:

```python
import requests

def send_pagerduty_alert(title, details):
    payload = {
        "routing_key": os.getenv('PAGERDUTY_KEY'),
        "event_action": "trigger",
        "payload": {
            "summary": title,
            "severity": "critical",
            "source": "VM Monitor",
            "custom_details": details
        }
    }
    requests.post('https://events.pagerduty.com/v2/enqueue', json=payload)
```

---

## 📊 Alert Metrics

Track alert performance:

```sql
-- Create alert history table
CREATE TABLE alert_history (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50),
    hostname VARCHAR(255),
    severity VARCHAR(20),
    sent_at TIMESTAMP DEFAULT NOW(),
    channel VARCHAR(20)
);
```

**Query alert frequency:**
```sql
SELECT alert_type, COUNT(*) as count
FROM alert_history
WHERE sent_at > NOW() - INTERVAL '24 hours'
GROUP BY alert_type;
```

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/SAbdulra/vm-monitor/issues)
- **Documentation**: [Main README](../README.md)
- **Security**: [SECURITY.md](../SECURITY.md)

---

**⚡ Happy Monitoring!**
