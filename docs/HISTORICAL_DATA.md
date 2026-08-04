# Historical Data & Time-Series Metrics

Complete guide to historical data storage, querying, and visualization in VM Monitor.

---

## 📋 Overview

VM Monitor stores time-series metrics data for historical analysis and trending. This allows you to:
- View metric trends over time
- Identify performance patterns
- Perform capacity planning
- Investigate historical issues
- Generate reports

---

## 🗄️ Database Schema

### Historical Metrics Table

```sql
-- Create partitioned table for metrics history
CREATE TABLE IF NOT EXISTS vm_metrics_history (
    id BIGSERIAL,
    hostname VARCHAR(255) NOT NULL,
    cpu_usage FLOAT,
    memory_usage FLOAT,
    disk_usage FLOAT,
    swap_usage FLOAT,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_metrics_history_hostname_timestamp
    ON vm_metrics_history (hostname, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_metrics_history_timestamp
    ON vm_metrics_history (timestamp DESC);
```

### Monthly Partitions

```sql
-- Create partitions (run monthly)
CREATE TABLE vm_metrics_history_2026_08 PARTITION OF vm_metrics_history
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

CREATE TABLE vm_metrics_history_2026_09 PARTITION OF vm_metrics_history
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
```

### Automatic Archiving

```sql
-- Function to archive current metrics to history
CREATE OR REPLACE FUNCTION archive_vm_metrics()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO vm_metrics_history (
        hostname, cpu_usage, memory_usage, disk_usage, swap_usage, timestamp
    )
    VALUES (
        NEW.hostname, NEW.cpu_usage, NEW.memory_usage,
        NEW.disk_usage, NEW.swap_usage, NEW.timestamp
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger on every metric update
CREATE TRIGGER trigger_archive_metrics
    AFTER INSERT OR UPDATE ON vm_metrics
    FOR EACH ROW
    EXECUTE FUNCTION archive_vm_metrics();
```

### Aggregated Views

```sql
-- Hourly aggregates
CREATE MATERIALIZED VIEW vm_metrics_hourly AS
SELECT
    hostname,
    date_trunc('hour', timestamp) AS hour,
    AVG(cpu_usage) AS avg_cpu,
    MAX(cpu_usage) AS max_cpu,
    MIN(cpu_usage) AS min_cpu,
    AVG(memory_usage) AS avg_memory,
    MAX(memory_usage) AS max_memory,
    MIN(memory_usage) AS min_memory,
    AVG(disk_usage) AS avg_disk,
    MAX(disk_usage) AS max_disk,
    MIN(disk_usage) AS min_disk,
    COUNT(*) AS sample_count
FROM vm_metrics_history
GROUP BY hostname, date_trunc('hour', timestamp);

-- Daily aggregates
CREATE MATERIALIZED VIEW vm_metrics_daily AS
SELECT
    hostname,
    date_trunc('day', timestamp) AS day,
    AVG(cpu_usage) AS avg_cpu,
    MAX(cpu_usage) AS max_cpu,
    MIN(cpu_usage) AS min_cpu,
    AVG(memory_usage) AS avg_memory,
    MAX(memory_usage) AS max_memory,
    MIN(memory_usage) AS min_memory,
    AVG(disk_usage) AS avg_disk,
    MAX(disk_usage) AS max_disk,
    MIN(disk_usage) AS min_disk,
    COUNT(*) AS sample_count
FROM vm_metrics_history
GROUP BY hostname, date_trunc('day', timestamp);
```

---

## 📡 API Endpoints

### GET `/api/vms/{hostname}/history`

Get historical metrics for a VM.

**Query Parameters:**
- `range` - Time range (1h, 6h, 24h, 7d, 30d, 90d)
- `interval` - Aggregation interval (auto-selected if not provided)

**Example:**
```bash
curl "http://localhost:8001/api/vms/web-server-01/history?range=24h"
```

**Response:**
```json
{
  "hostname": "web-server-01",
  "time_range": "24h",
  "interval": "15 minutes",
  "start_time": "2026-08-04T15:30:00",
  "end_time": "2026-08-05T15:30:00",
  "data_points": 96,
  "timestamps": ["2026-08-04T15:30:00", ...],
  "metrics": {
    "cpu": [
      {"avg": 45.2, "max": 78.5, "min": 12.3},
      ...
    ],
    "memory": [...],
    "disk": [...]
  }
}
```

### GET `/api/fleet/metrics-history`

Get fleet-wide aggregated metrics.

**Query Parameters:**
- `range` - Time range

**Example:**
```bash
curl "http://localhost:8001/api/fleet/metrics-history?range=7d"
```

### GET `/api/vms/{hostname}/statistics`

Get statistical analysis of metrics.

**Query Parameters:**
- `metric` - cpu, memory, or disk
- `range` - Time range

**Example:**
```bash
curl "http://localhost:8001/api/vms/web-server-01/statistics?metric=cpu&range=7d"
```

**Response:**
```json
{
  "hostname": "web-server-01",
  "metric": "cpu",
  "time_range": "7d",
  "statistics": {
    "mean": 45.2,
    "median": 42.1,
    "p95": 78.5,
    "p99": 89.3,
    "max": 95.2,
    "min": 8.4,
    "stddev": 15.8,
    "samples": 10080
  }
}
```

### GET `/api/top-consumers`

Get VMs with highest resource usage.

**Query Parameters:**
- `metric` - cpu, memory, or disk
- `range` - Time range
- `limit` - Number of results (default 10)

**Example:**
```bash
curl "http://localhost:8001/api/top-consumers?metric=cpu&range=24h&limit=5"
```

---

## 📊 Chart Visualization

Access the charts page at `/charts.html`.

**Features:**
- Interactive time-series charts
- Multiple time ranges (1h to 90d)
- Auto-scaled aggregation
- Min/Max/Average trend lines
- Real-time statistics

**Time Ranges:**
- **1 Hour**: 1-minute intervals
- **6 Hours**: 5-minute intervals
- **24 Hours**: 15-minute intervals
- **7 Days**: 1-hour intervals
- **30 Days**: 1-day intervals
- **90 Days**: 1-day intervals

---

## 🔄 Data Retention

### Configure Retention

Set retention period in `.env`:
```bash
METRICS_RETENTION_DAYS=90  # Keep 90 days of data
```

### Manual Cleanup

Run cleanup function:
```sql
SELECT cleanup_old_metrics(90);  -- Delete data older than 90 days
```

### Scheduled Cleanup

Add to cron:
```bash
# Daily at 3 AM
0 3 * * * psql -U vm_monitor -d infra_monitor -c "SELECT cleanup_old_metrics(90);"
```

---

## 📈 Aggregation Intervals

Intervals are auto-selected based on time range:

| Time Range | Interval | Data Points |
|------------|----------|-------------|
| 1 hour     | 1 minute | ~60         |
| 6 hours    | 5 minutes | ~72        |
| 24 hours   | 15 minutes | ~96       |
| 7 days     | 1 hour   | ~168        |
| 30 days    | 1 day    | ~30         |
| 90 days    | 1 day    | ~90         |

---

## 🛠️ Maintenance

### Refresh Materialized Views

Run hourly:
```sql
REFRESH MATERIALIZED VIEW vm_metrics_hourly;
REFRESH MATERIALIZED VIEW vm_metrics_daily;
```

Add to cron:
```bash
# Every hour
0 * * * * psql -U vm_monitor -d infra_monitor -c "REFRESH MATERIALIZED VIEW vm_metrics_hourly;"

# Daily
0 1 * * * psql -U vm_monitor -d infra_monitor -c "REFRESH MATERIALIZED VIEW vm_metrics_daily;"
```

### Monitor Table Size

```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename LIKE 'vm_metrics%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Vacuum Tables

```bash
# Analyze and vacuum
VACUUM ANALYZE vm_metrics_history;
```

---

## 💡 Best Practices

### 1. **Regular Maintenance**

Schedule these tasks:
- Refresh aggregates: Hourly/Daily
- Cleanup old data: Daily
- Vacuum tables: Weekly

### 2. **Partitioning**

Create next month's partition in advance:
```sql
CREATE TABLE vm_metrics_history_2026_10 PARTITION OF vm_metrics_history
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
```

### 3. **Query Optimization**

Use aggregated views for long time ranges:
```sql
-- Good: Use hourly view for 7-day query
SELECT * FROM vm_metrics_hourly
WHERE hostname = 'web-server-01'
  AND hour > NOW() - INTERVAL '7 days';

-- Bad: Raw data for 7-day query
SELECT * FROM vm_metrics_history
WHERE hostname = 'web-server-01'
  AND timestamp > NOW() - INTERVAL '7 days';
```

### 4. **Storage Management**

Monitor disk usage and adjust retention:
```bash
# Check database size
psql -c "SELECT pg_size_pretty(pg_database_size('infra_monitor'));"

# Adjust retention if needed
echo "METRICS_RETENTION_DAYS=60" >> .env
```

---

## 📊 Example Queries

### Peak Usage Last 24 Hours

```sql
SELECT
    hostname,
    MAX(cpu_usage) as peak_cpu,
    MAX(memory_usage) as peak_memory,
    MAX(disk_usage) as peak_disk
FROM vm_metrics_history
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hostname
ORDER BY peak_cpu DESC
LIMIT 10;
```

### Average Usage Per Hour Today

```sql
SELECT
    date_trunc('hour', timestamp) AS hour,
    AVG(cpu_usage) AS avg_cpu,
    AVG(memory_usage) AS avg_memory
FROM vm_metrics_history
WHERE timestamp > date_trunc('day', NOW())
GROUP BY hour
ORDER BY hour;
```

### Resource Trend (7-Day Moving Average)

```sql
SELECT
    hostname,
    timestamp,
    AVG(cpu_usage) OVER (
        PARTITION BY hostname
        ORDER BY timestamp
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS cpu_7day_avg
FROM vm_metrics_history
WHERE hostname = 'web-server-01'
  AND timestamp > NOW() - INTERVAL '30 days';
```

---

## 📞 Support

- **API Documentation**: [API.md](API.md)
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Issues**: [GitHub Issues](https://github.com/SAbdulra/vm-monitor/issues)

---

**📈 Track Your Infrastructure!**
