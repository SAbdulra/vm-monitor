# VM Monitor - Architecture Documentation

## System Overview

VM Monitor is a containerized, real-time infrastructure monitoring platform designed for enterprise Linux environments. It collects metrics from multiple VMs, tracks CVE vulnerabilities, and provides a modern web dashboard for visualization.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         VM MONITORING ECOSYSTEM                          │
└─────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │       Monitored VMs (N)         │
                    │  Telegraf Agents (60s interval) │
                    └─────────────────────────────────┘
                                   │
                        ┌──────────┴──────────┐
                        │                     │
                   [Metrics]            [Facts/Packages]
                    (60s)                (15-30 days)
                        │                     │
                        ▼                     ▼
        ┌───────────────────────────────────────────────────┐
        │        Telegraf Aggregator (Port 8086)            │
        │  ┌─────────────────────────────────────────────┐  │
        │  │ /var/log/telegraf/metrics.log               │  │
        │  │ InfluxDB Line Protocol Format               │  │
        │  └─────────────────────────────────────────────┘  │
        └───────────────────────────────────────────────────┘
                                   │
                        ┌──────────┴──────────┐
                        │                     │
                  [Stream]              [Ansible]
                        │                     │
                        ▼                     ▼
        ┌───────────────────────────────────────────────────┐
        │          Application Server (Containers)          │
        │                                                    │
        │  ┌─────────────────────────────────────────────┐  │
        │  │  Telegraf Processor Workers (×3)            │  │
        │  │  - Parse InfluxDB line protocol             │  │
        │  │  - Extract: cpu, mem, disk, swap            │  │
        │  │  - Write to PostgreSQL                      │  │
        │  └─────────────────────────────────────────────┘  │
        │                       ↓                            │
        │  ┌─────────────────────────────────────────────┐  │
        │  │         PostgreSQL Database                 │  │
        │  │  - vm_metrics (real-time, 60s updates)      │  │
        │  │  - vm_static_info (facts, 15-30 days)       │  │
        │  │  - vm_packages (installed packages)         │  │
        │  │  - cve_database (NIST NVD data)             │  │
        │  │  - vm_package_cves (vulnerability matches)  │  │
        │  └─────────────────────────────────────────────┘  │
        │                       ↓                            │
        │  ┌─────────────────────────────────────────────┐  │
        │  │  Backend Container (FastAPI, Port 8001)     │  │
        │  │  - /api/dashboard/stats                     │  │
        │  │  - /api/vms                                 │  │
        │  │  - /api/vms/{hostname}/packages/detail      │  │
        │  │  - /ws/metrics (WebSocket)                  │  │
        │  └─────────────────────────────────────────────┘  │
        │                       ↓                            │
        │  ┌─────────────────────────────────────────────┐  │
        │  │  Redis Cache (256MB, LRU eviction)          │  │
        │  │  - Future: Dashboard stats caching          │  │
        │  └─────────────────────────────────────────────┘  │
        │                       ↓                            │
        │  ┌─────────────────────────────────────────────┐  │
        │  │  Nginx (Port 443, HTTPS/TLS)                │  │
        │  │  - SSL termination                          │  │
        │  │  - Static files: /                          │  │
        │  │  - API proxy: /api/* → backend:8001         │  │
        │  │  - WebSocket: /ws/* → backend:8001          │  │
        │  └─────────────────────────────────────────────┘  │
        └───────────────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │       User Browser          │
                    │  React Dashboard (SPA)      │
                    │  - Real-time metrics        │  
                    │  - VM cards & details       │
                    │  - CVE vulnerability view   │
                    └─────────────────────────────┘
```

## Data Flow

### 1. Real-Time Metrics Flow (Every 60 Seconds)

```
VM → Telegraf Agent → Telegraf Aggregator:8086
                          ↓
                   /var/log/telegraf/metrics.log
                          ↓
              Telegraf Processor Workers (×3)
                          ↓
                    PostgreSQL
                          ↓
                   Backend API
                          ↓
                   WebSocket Push
                          ↓
                    User Browser
```

**Timeline:**
- T+0s: VM sends metrics
- T+1s: Aggregator writes to log
- T+2s: Processor reads & parses
- T+3s: Database updated
- T+30s: WebSocket pushes to browser

### 2. Static Data Flow (Every 15-30 Days)

```
Ansible → VM Facts Collection → PostgreSQL
Package Manager (rpm/dpkg) → Package List → PostgreSQL
```

### 3. CVE Vulnerability Flow (Daily at 2 AM)

```
NIST NVD API → CVE Downloader Container → PostgreSQL (cve_database)
                                              ↓
                                        CVE Matcher
                                              ↓
                                  vm_package_cves table
                                              ↓
                                        Backend API
                                              ↓
                                      /api/vms/{host}/packages/detail
```

## Component Details

### Telegraf Agent (on each VM)

**Role**: Collect system metrics  
**Frequency**: Every 60 seconds  
**Metrics Collected**:
- CPU usage (per core + total)
- Memory usage (used, available, cached)
- Disk usage (per mount point)
- Swap usage

**Output**: InfluxDB line protocol to aggregator:8086

### Telegraf Aggregator

**Role**: Centralize metrics from all VMs  
**Input**: Port 8086 (InfluxDB protocol)  
**Output**: `/var/log/telegraf/metrics.log`  
**Format**: InfluxDB line protocol (plain text)

### Telegraf Processor Workers (×3)

**Role**: Parse metrics and write to database  
**Input**: Tail `/var/log/telegraf/metrics.log`  
**Processing**:
1. Parse InfluxDB line protocol
2. Extract hostname, measurement, fields
3. Filter for: cpu, mem, disk, swap only
4. Transform data (e.g., cpu_usage = 100 - idle)
5. Upsert into `vm_metrics` table

**Concurrency**: 3 workers process in parallel  
**Throughput**: ~200 metrics/second

### Backend Container (FastAPI)

**Role**: REST API server  
**Port**: 8001 (internal), exposed via Nginx  
**Workers**: 2 uvicorn workers  
**Database**: PostgreSQL connection pool (2-10 connections)  
**Cache**: Redis (future implementation)

**Key Endpoints**:
- `GET /api/dashboard/stats` - Aggregated statistics
- `GET /api/vms` - List all VMs with metrics
- `GET /api/vms/{hostname}` - Single VM details
- `GET /api/vms/{hostname}/packages/detail` - Packages + CVEs
- `WebSocket /ws/metrics` - Real-time updates (30s interval)

### PostgreSQL Database

**Tables**:

1. **vm_metrics** (real-time)
   - Primary key: hostname
   - Updated: Every 60 seconds
   - Retention: Last 5 minutes (for dashboard)

2. **vm_static_info**
   - OS version, kernel, architecture, CPU cores, RAM
   - Updated: Every 15-30 days

3. **vm_packages**
   - 42,000+ packages across all VMs
   - Package name, version, architecture

4. **cve_database**
   - 10,000+ CVEs from NIST NVD
   - CVE ID, CVSS score, severity, affected products

5. **vm_package_cves**
   - Joins packages with matching CVEs
   - 659+ vulnerability matches

### Redis Cache

**Role**: Cache frequently accessed data  
**Memory**: 256MB  
**Eviction**: LRU (Least Recently Used)  
**Usage**: Dashboard stats caching (future)

### CVE Downloader

**Role**: Sync CVE database from NIST NVD  
**Schedule**: Daily at 2 AM (cron)  
**Source**: https://services.nvd.nist.gov/rest/json/cves/2.0  
**Rate Limit**: 7 seconds between requests  
**Updates**: Incremental (only new/updated CVEs)

### Nginx

**Role**: Reverse proxy + static file server  
**Port**: 443 (HTTPS)  
**SSL**: TLS 1.2, TLS 1.3  

**Routing**:
- `/` → Static files (React app)
- `/api/*` → Backend:8001
- `/ws/*` → Backend:8001 (WebSocket upgrade)

## Scalability

### Horizontal Scaling

**Backend**:
```bash
# Add 2nd instance
docker run -d --name vm-monitor-backend-2 -p 8002:8000 ...

# Update Nginx upstream
upstream backend {
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}
```

**Telegraf Processors**:
```bash
# Add 4th worker
docker run -d --name vm-monitor-telegraf-processor-4 ...
```

### Vertical Scaling

**Increase Resources**:
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'     # Increase from 1.0
      memory: 1024M   # Increase from 512M
```

### Database Scaling

**For 1000+ VMs**:
- PostgreSQL replication (read replicas)
- Connection pooling (PgBouncer)
- Partitioning `vm_metrics` by time
- Time-series database (TimescaleDB) for historical data

## Performance Characteristics

### Current Load (133 VMs)

| Metric | Value |
|--------|-------|
| **Data points/minute** | 532 (4 metrics × 133 VMs) |
| **Database writes/minute** | 532 |
| **API requests/second** | 10-20 (dashboard polling) |
| **WebSocket connections** | 1-10 concurrent users |
| **Backend CPU** | ~5-10% |
| **Backend Memory** | ~125 MB |
| **PostgreSQL CPU** | ~2-5% |
| **PostgreSQL Memory** | ~200 MB |

### Capacity Estimates

| VMs | Data Points/min | PostgreSQL Size (30 days) | Backend Instances |
|-----|-----------------|---------------------------|-------------------|
| 100 | 400 | ~1.7 GB | 1 |
| 500 | 2,000 | ~8.6 GB | 2-3 |
| 1,000 | 4,000 | ~17 GB | 3-5 |
| 5,000 | 20,000 | ~86 GB | 10-15 |

## Security Architecture

### Network Security
- All containers on isolated bridge network
- Only backend exposed via Nginx reverse proxy
- PostgreSQL not exposed externally
- Redis not exposed externally

### Data Security
- Environment variables for secrets (never in code)
- SSL/TLS for all external communication
- LDAP/AD authentication support (optional)
- JWT tokens for API authentication

### Container Security
- Non-root users in containers
- Read-only filesystem where possible
- Resource limits enforced
- Security scanning via Trivy/Clair

## High Availability

### Container Auto-Restart
```yaml
restart: unless-stopped
```

### Health Checks
- Backend: HTTP health endpoint
- Redis: PING command
- PostgreSQL: Connection test

### Failure Scenarios

| Failure | Impact | Recovery |
|---------|--------|----------|
| Backend crash | Dashboard unavailable | Auto-restart (< 10s) |
| Processor crash | Metrics delayed | Auto-restart, catch up from log |
| PostgreSQL down | All services fail | Manual intervention required |
| Redis down | Slower responses | Backend continues without cache |
| Nginx down | Dashboard inaccessible | systemctl restart nginx |

## Monitoring & Observability

### Container Logs
```bash
podman logs -f vm-monitor-backend-1
podman logs vm-monitor-cve-downloader
```

### Metrics
```bash
podman stats
```

### Database Queries
```sql
-- Check metric freshness
SELECT hostname, timestamp, NOW() - timestamp as age
FROM vm_metrics
ORDER BY timestamp DESC;

-- CVE summary
SELECT severity, COUNT(*) 
FROM vm_package_cves 
GROUP BY severity;
```

## Future Enhancements

1. **Prometheus Integration**: Export metrics in Prometheus format
2. **Grafana Dashboards**: Advanced visualization
3. **Alerting**: Email/Slack notifications for critical events
4. **Historical Data**: Time-series database for long-term storage
5. **Multi-tenancy**: Support multiple organizations
6. **Kubernetes**: K8s deployment manifests
7. **Auto-scaling**: HPA based on load

---

**Last Updated**: August 2026  
**Architecture Version**: 1.0 (Containerized)
