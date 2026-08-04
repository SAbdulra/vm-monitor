# Troubleshooting Zero-Metric VMs

Complete guide to diagnosing and fixing VMs that report 0.0 for all metrics (CPU, Memory, Disk).

---

## 📋 Overview

**Problem**: Some VMs show as "online" but report **0.0% for all metrics** (CPU, Memory, and Disk).

**Impact**:
- Inaccurate monitoring data
- Misleading dashboard statistics
- Unable to detect actual resource issues
- False sense of "healthy" systems

**Root Causes**:
1. Telegraf agent not collecting metrics
2. Telegraf configuration missing input plugins
3. Permission issues reading system metrics
4. Telegraf service crashed or not running
5. VM powered off but sending heartbeat

---

## 🔍 Detection

### Automatic Detection

VM Monitor automatically detects zero-metric VMs:

1. **API Endpoint**: `GET /api/monitoring/zero-metrics`
   ```bash
   curl http://your-monitor-server:8001/api/monitoring/zero-metrics
   ```

2. **Automatic Alerts** (if enabled):
   - Email notifications
   - Slack messages
   - Alerts after 3 consecutive checks (default)
   - Check interval: 5 minutes (default)

### Manual Detection

**From Dashboard**:
- Look for VMs with CPU, Memory, and Disk all showing 0%
- Status may still show "online"

**From API**:
```bash
curl -s http://your-monitor-server:8001/api/vms | \
  grep -o '"name":"[^"]*","status":"online","cpu_usage":0.0,"memory_usage":0.0,"disk_usage":0.0'
```

**From Database**:
```sql
SELECT hostname, cpu_usage, memory_usage, disk_usage, timestamp
FROM vm_metrics
WHERE cpu_usage = 0.0
  AND memory_usage = 0.0
  AND disk_usage = 0.0
  AND status = 'online'
ORDER BY hostname;
```

---

## 🔧 Automated Fix Script

We provide a comprehensive fix script: `fix_zero_metrics.sh`

### Download and Run

```bash
# Copy the script
scp fix_zero_metrics.sh your-jump-host:/tmp/

# SSH to jump host
ssh your-jump-host

# Run the script
bash /tmp/fix_zero_metrics.sh
```

### Script Features

1. **Automatically identifies** all VMs with zero metrics from API
2. **Interactive options**:
   - Test one specific VM
   - Fix all affected VMs
   - Fix first 10 VMs (for testing)
   - Export list and exit

3. **For each VM, checks**:
   - Network connectivity (ping)
   - Telegraf installation
   - Telegraf service status
   - Telegraf configuration (input plugins)
   - Actual metric collection (test run)

4. **Automatic repairs**:
   - Installs Telegraf if missing
   - Starts/enables Telegraf service
   - Restarts Telegraf
   - Identifies configuration issues

---

## 🛠️ Manual Troubleshooting

### Step 1: Verify VM Connectivity

```bash
# Can you reach the VM?
ping -c 3 vm-hostname.ad.analog.com

# Can you SSH?
ssh vm-hostname.ad.analog.com
```

**If fails**: Network issue, VM powered off, or firewall blocking

---

### Step 2: Check Telegraf Installation

```bash
# SSH to the VM
ssh vm-hostname.ad.analog.com

# Check if Telegraf is installed
which telegraf
telegraf --version

# If not installed:
sudo yum install telegraf -y        # RHEL/CentOS
sudo apt install telegraf -y        # Ubuntu/Debian
sudo apk add telegraf               # Alpine
```

---

### Step 3: Check Telegraf Service Status

```bash
# Check service status
systemctl status telegraf

# If not running:
sudo systemctl start telegraf
sudo systemctl enable telegraf

# Check logs
journalctl -u telegraf -n 50
```

**Common issues**:
- Service failed to start → Check logs
- Service disabled → Run `systemctl enable telegraf`
- Permission errors → Check file ownership

---

### Step 4: Verify Telegraf Configuration

```bash
# Check config file
sudo cat /etc/telegraf/telegraf.conf | grep -A 10 "\[\[inputs"

# Must have these input plugins:
# [[inputs.cpu]]
# [[inputs.mem]]
# [[inputs.disk]]
```

**If missing input plugins**, add them:

```bash
sudo tee -a /etc/telegraf/telegraf.conf > /dev/null <<'EOF'

# CPU Metrics
[[inputs.cpu]]
  percpu = false
  totalcpu = true
  collect_cpu_time = false
  report_active = false

# Memory Metrics
[[inputs.mem]]

# Disk Metrics
[[inputs.disk]]
  ignore_fs = ["tmpfs", "devtmpfs", "devfs", "iso9660", "overlay", "aufs", "squashfs"]
EOF

# Restart Telegraf
sudo systemctl restart telegraf
```

---

### Step 5: Test Metric Collection

```bash
# Test Telegraf (runs once and exits)
sudo telegraf --test --config /etc/telegraf/telegraf.conf 2>&1 | head -100

# Look for these lines:
# > cpu,cpu=cpu-total usage_idle=...
# > mem available=...,total=...
# > disk,device=...,path=/ free=...,used=...
```

**If no CPU/Memory/Disk metrics appear**:
- Configuration issue
- Permission problem
- Telegraf version incompatibility

---

### Step 6: Check Permissions

Telegraf needs to read system files:

```bash
# Check Telegraf user
ps aux | grep telegraf

# Telegraf should run as root or have access to:
ls -la /proc/stat         # CPU metrics
ls -la /proc/meminfo      # Memory metrics
df -h                     # Disk metrics

# If permission denied, check telegraf service file:
sudo cat /etc/systemd/system/telegraf.service.d/override.conf
```

---

### Step 7: Verify Telegraf Output

```bash
# Check where Telegraf is sending data
sudo cat /etc/telegraf/telegraf.conf | grep -A 10 "\[\[outputs"

# Should have InfluxDB or HTTP output configured
# Example for HTTP output to VM Monitor:
# [[outputs.http]]
#   url = "http://monitoring-server:8000/metrics"
#   method = "POST"
#   data_format = "influx"
```

---

### Step 8: Check Telegraf Logs

```bash
# Recent logs
journalctl -u telegraf -n 100 --no-pager

# Follow logs in real-time
journalctl -u telegraf -f

# Look for:
# - "Permission denied" → Permission issue
# - "Connection refused" → Network/output issue
# - "Error in plugin" → Configuration issue
```

---

## 🔄 After Fixes

### Verify Metrics Are Flowing

**Wait 2-3 minutes**, then:

1. **Check API**:
   ```bash
   curl -s http://monitoring-server:8001/api/vms | \
     grep "vm-hostname" | \
     jq '.cpu_usage, .memory_usage, .disk_usage'
   ```

2. **Check Dashboard**:
   - Open dashboard: `http://monitoring-server/`
   - Search for the VM
   - Verify CPU/Memory/Disk show non-zero values

3. **Check Database**:
   ```sql
   SELECT hostname, cpu_usage, memory_usage, disk_usage, timestamp
   FROM vm_metrics
   WHERE hostname = 'vm-hostname'
   ORDER BY timestamp DESC
   LIMIT 1;
   ```

---

## 📊 Monitoring Configuration

### Enable Zero-Metric Alerts

In `.env` file:

```bash
# Enable automatic monitoring
ZERO_METRIC_MONITORING_ENABLED=true

# Check every 5 minutes (300 seconds)
ZERO_METRIC_CHECK_INTERVAL=300

# Alert after 3 consecutive checks (15 minutes total)
ZERO_METRIC_THRESHOLD=3

# Email alerts
EMAIL_ENABLED=true
ALERT_EMAIL_TO=ops-team@company.com

# Slack alerts
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Check Zero-Metric Report

```bash
# Get current status
curl http://monitoring-server:8001/api/monitoring/zero-metrics

# Example response:
{
  "timestamp": "2026-08-05T10:30:00",
  "total_zero_metric_vms": 5,
  "vms": [
    {
      "hostname": "vm-01",
      "cpu": 0.0,
      "memory": 0.0,
      "disk": 0.0,
      "last_update": "2026-08-05T10:29:45",
      "status": "online"
    }
  ],
  "counters": {
    "vm-01": 3,
    "vm-02": 2
  },
  "alerted_vms": ["vm-01"]
}
```

---

## 🔬 Advanced Troubleshooting

### Check Telegraf Process

```bash
# Is Telegraf running?
ps aux | grep telegraf

# CPU/Memory usage of Telegraf
top -b -n 1 -p $(pgrep telegraf)

# Open files
lsof -p $(pgrep telegraf)
```

### Telegraf Debugging

```bash
# Run Telegraf in debug mode
sudo telegraf --config /etc/telegraf/telegraf.conf --debug

# Run with specific input plugins only
sudo telegraf --config /etc/telegraf/telegraf.conf --input-filter cpu:mem:disk --test
```

### Network Connectivity

```bash
# Test connection to monitoring server
telnet monitoring-server 8000

# Check if Telegraf can reach output
curl -X POST http://monitoring-server:8000/metrics -d "test"
```

### Check System Resources

```bash
# Verify actual system metrics
# CPU
top -b -n 1 | head -20
cat /proc/stat

# Memory
free -h
cat /proc/meminfo

# Disk
df -h
```

---

## 📚 Common Error Messages

### "Permission denied reading /proc/stat"

**Cause**: Telegraf doesn't have permission to read system files

**Fix**:
```bash
# Run Telegraf as root
sudo systemctl edit telegraf

# Add:
[Service]
User=root
Group=root

# Restart
sudo systemctl daemon-reload
sudo systemctl restart telegraf
```

### "Connection refused to output"

**Cause**: Cannot connect to monitoring server

**Fix**:
```bash
# Check network
ping monitoring-server

# Check firewall
sudo firewall-cmd --list-all

# Verify output URL in config
grep -A 5 "\[\[outputs.http\]\]" /etc/telegraf/telegraf.conf
```

### "Error in input plugin [cpu]"

**Cause**: CPU plugin configuration error

**Fix**:
```bash
# Test CPU plugin specifically
telegraf --input-filter cpu --test

# Check configuration
telegraf --config /etc/telegraf/telegraf.conf --test
```

---

## 🎯 Quick Reference

| Issue | Quick Fix |
|-------|-----------|
| Telegraf not running | `systemctl start telegraf` |
| Telegraf not installed | `yum install telegraf` |
| Missing config | Add `[[inputs.cpu]]`, `[[inputs.mem]]`, `[[inputs.disk]]` |
| Permission denied | Run as root: Edit service with `systemctl edit telegraf` |
| Not sending data | Check output config and restart |
| Old version | `yum update telegraf` |

---

## 📞 Support

If problems persist after these steps:

1. **Collect diagnostics**:
   ```bash
   # Create diagnostic bundle
   telegraf --version > /tmp/telegraf-diag.txt
   systemctl status telegraf >> /tmp/telegraf-diag.txt
   journalctl -u telegraf -n 100 >> /tmp/telegraf-diag.txt
   cat /etc/telegraf/telegraf.conf >> /tmp/telegraf-diag.txt
   ```

2. **Check GitHub Issues**: [vm-monitor/issues](https://github.com/SAbdulra/vm-monitor/issues)

3. **Contact Operations Team**

---

## ✅ Prevention

### Regular Maintenance

1. **Monitor zero-metric VMs weekly**
2. **Keep Telegraf updated**
3. **Test metric collection after VM changes**
4. **Document VM-specific configurations**

### Automated Checks

```bash
# Add to cron (daily check)
0 9 * * * curl -s http://monitoring-server:8001/api/monitoring/zero-metrics | \
  jq '.total_zero_metric_vms' | \
  mail -s "Zero-Metric VMs Report" ops@company.com
```

---

**Last Updated**: 2026-08-05  
**Version**: 1.3.0
