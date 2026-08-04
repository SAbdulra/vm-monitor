# VM Monitor - Quick Start Guide

Get VM Monitor up and running in under 10 minutes!

## Prerequisites

- **Linux server** with Docker or Podman installed
- **PostgreSQL 13+** (local or remote)
- **Root or sudo access**
- **At least 2GB RAM** and 10GB disk space

## Quick Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/vm-monitor.git
cd vm-monitor
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

**Minimum required settings:**
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=infra_monitor
DB_USER=vm_monitor
DB_PASSWORD=your_secure_password_here
TELEGRAF_PASSWORD=your_telegraf_password_here
```

### 3. Create Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database and user
CREATE DATABASE infra_monitor;
CREATE USER vm_monitor WITH PASSWORD 'your_secure_password_here';
CREATE USER telegraf WITH PASSWORD 'your_telegraf_password_here';

GRANT ALL PRIVILEGES ON DATABASE infra_monitor TO vm_monitor;
GRANT INSERT, UPDATE, SELECT ON ALL TABLES IN SCHEMA public TO telegraf;

\q
```

### 4. Initialize Database Schema

```sql
-- Connect to database
psql -U vm_monitor -d infra_monitor

-- Create tables
CREATE TABLE vm_metrics (
    hostname VARCHAR(255) PRIMARY KEY,
    cpu_usage FLOAT,
    memory_usage FLOAT,
    disk_usage FLOAT,
    swap_usage FLOAT,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE vm_static_info (
    hostname VARCHAR(255) PRIMARY KEY,
    os_pretty_name VARCHAR(255),
    kernel_version VARCHAR(100),
    architecture VARCHAR(50),
    cpu_cores INTEGER,
    ram_total_gb FLOAT,
    uptime_days INTEGER,
    last_updated TIMESTAMP DEFAULT NOW()
);

CREATE TABLE vm_packages (
    id SERIAL PRIMARY KEY,
    hostname VARCHAR(255),
    package_name VARCHAR(255),
    version VARCHAR(100),
    release VARCHAR(100),
    architecture VARCHAR(50),
    install_date TIMESTAMP
);

CREATE TABLE cve_database (
    cve_id VARCHAR(50) PRIMARY KEY,
    cvss_v3_score FLOAT,
    severity VARCHAR(20),
    affected_products JSONB,
    description TEXT,
    published_date TIMESTAMP
);

CREATE TABLE vm_package_cves (
    id SERIAL PRIMARY KEY,
    hostname VARCHAR(255),
    package_name VARCHAR(255),
    cve_id VARCHAR(50),
    cvss_score FLOAT,
    severity VARCHAR(20),
    FOREIGN KEY (cve_id) REFERENCES cve_database(cve_id)
);

-- Grant permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO vm_monitor;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO vm_monitor;
GRANT INSERT, UPDATE, SELECT ON vm_metrics TO telegraf;
```

### 5. Deploy Containers

```bash
# Run deployment script
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

**Or manually:**
```bash
cd docker

# Build images
podman build -t vm-monitor-backend:latest ./backend
podman build -t vm-monitor-telegraf-processor:latest ./telegraf-processor
podman build -t vm-monitor-cve-downloader:latest ./cve-downloader

# Start stack
podman-compose up -d
```

### 6. Verify Installation

```bash
# Check container status
podman ps

# Expected output:
# vm-monitor-backend-1
# vm-monitor-redis
# vm-monitor-telegraf-processor-1
# vm-monitor-telegraf-processor-2
# vm-monitor-telegraf-processor-3
# vm-monitor-cve-downloader

# Test backend API
curl http://localhost:8001/api/dashboard/stats

# Should return JSON with VM statistics
```

### 7. Configure Nginx (Optional for HTTPS)

```bash
# Copy Nginx configuration
sudo cp nginx/vm_monitor.conf /etc/nginx/conf.d/

# Update server_name in the config
sudo nano /etc/nginx/conf.d/vm_monitor.conf

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### 8. Access Dashboard

Open your browser:
- **HTTP**: http://your-server:8001
- **HTTPS** (with Nginx): https://your-server

## Configure Telegraf Agents on VMs

On each VM you want to monitor:

### 1. Install Telegraf

```bash
# RHEL/CentOS
sudo yum install telegraf

# Ubuntu/Debian
sudo apt-get install telegraf
```

### 2. Configure Telegraf

```bash
sudo nano /etc/telegraf/telegraf.conf
```

Add:
```toml
[global_tags]
  environment = "production"

[agent]
  interval = "60s"
  hostname = "your-vm-hostname"

# Outputs
[[outputs.influxdb]]
  urls = ["http://your-aggregator:8086"]

# Inputs
[[inputs.cpu]]
  percpu = false
  totalcpu = true

[[inputs.mem]]

[[inputs.disk]]
  ignore_fs = ["tmpfs", "devtmpfs", "devfs"]

[[inputs.swap]]
```

### 3. Start Telegraf

```bash
sudo systemctl enable telegraf
sudo systemctl start telegraf
sudo systemctl status telegraf
```

## Troubleshooting

### Backend Won't Start

```bash
# Check logs
podman logs vm-monitor-backend-1

# Common issues:
# - Database connection failed → Check DB_HOST, DB_PASSWORD in .env
# - Port already in use → Change port in docker-compose.yml
```

### No Metrics Appearing

```bash
# Check if Telegraf agents are sending data
tail -f /var/log/telegraf/metrics.log  # on aggregator

# Check processor logs
podman logs vm-monitor-telegraf-processor-1

# Verify database has data
psql -U vm_monitor -d infra_monitor -c "SELECT * FROM vm_metrics LIMIT 5;"
```

### CVE Download Failing

```bash
# Check CVE downloader logs
podman logs vm-monitor-cve-downloader

# Manually trigger sync
podman exec vm-monitor-cve-downloader python3 /app/nvd_cve_downloader_v2.py
```

## Next Steps

1. **Add More VMs**: Install Telegraf on additional VMs
2. **Customize Dashboard**: Modify `frontend/static/index.html`
3. **Set Up Alerts**: Configure email/Slack notifications
4. **Enable HTTPS**: Configure SSL certificates in Nginx
5. **Scale Backend**: Add more backend instances for load balancing

## Useful Commands

```bash
# View all containers
podman ps

# Stop all
podman-compose down

# Restart all
podman-compose restart

# View logs (follow)
podman logs -f vm-monitor-backend-1

# Check resource usage
podman stats

# Access backend shell
podman exec -it vm-monitor-backend-1 /bin/bash

# Access database
psql -U vm_monitor -h localhost -d infra_monitor
```

## Default Ports

| Service | Port | Protocol |
|---------|------|----------|
| Backend API | 8001 | HTTP |
| Nginx | 443 | HTTPS |
| PostgreSQL | 5432 | TCP |
| Redis | 6379 | TCP |
| Telegraf Aggregator | 8086 | HTTP |

## Support

- **Documentation**: See `/docs` folder
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

---

**You're all set! 🎉**

Your VM Monitor is now running and ready to collect metrics from your infrastructure.
