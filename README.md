# VM Monitor - Enterprise Infrastructure Monitoring Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg)](https://fastapi.tiangolo.com/)
[![GitHub Stars](https://img.shields.io/github/stars/SAbdulra/vm-monitor?style=social)](https://github.com/SAbdulra/vm-monitor)
[![License](https://img.shields.io/github/license/SAbdulra/vm-monitor)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
> A containerized, real-time VM monitoring platform for enterprise Linux infrastructure with CVE vulnerability tracking.

## 🌟 Features

- **Real-time Metrics**: CPU, Memory, Disk, Swap monitoring (60-second intervals)
- **133+ VM Support**: Scalable to thousands of VMs
- **CVE Vulnerability Tracking**: Automatic package-to-CVE matching via NIST NVD
- **Containerized Architecture**: Docker/Podman ready with horizontal scaling
- **React Dashboard**: Modern, responsive web interface
- **WebSocket Updates**: Live metrics without page refresh
- **PostgreSQL Backend**: Robust data storage with connection pooling
- **Redis Caching**: Optional performance optimization layer

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Monitored VMs (N)                         │
│  Telegraf Agents → sjcd-syslog01l:8086 (Aggregator)         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Application Server (Containers)                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Telegraf Processor (×3) → PostgreSQL                  │ │
│  │  Backend (FastAPI) → Port 8001                         │ │
│  │  Redis Cache → 256MB                                   │ │
│  │  CVE Downloader → Daily sync (2 AM)                    │ │
│  └────────────────────────────────────────────────────────┘ │
│                            ↓                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Nginx (Port 443) → SSL/TLS → Static Files + API      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    User Browser (HTTPS)
```

## 🚀 Quick Start

### Prerequisites

- Docker or Podman
- PostgreSQL 13+ (external or containerized)
- Nginx (for production)
- Python 3.11+ (for development)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/YOUR_USERNAME/vm-monitor.git
cd vm-monitor
```

2. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your database credentials
```

3. **Start the container stack**
```bash
# Using Docker Compose
docker-compose up -d

# Or using Podman
podman-compose up -d
```

4. **Access the dashboard**
```
https://your-server.example.com
```

## 📁 Project Structure

```
vm-monitor/
├── docker/
│   ├── backend/                  # FastAPI application
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── postgres_backend.py
│   ├── telegraf-processor/       # Metrics processor workers
│   │   ├── Dockerfile
│   │   └── telegraf_metrics_to_postgres.py
│   ├── cve-downloader/           # CVE database sync
│   │   ├── Dockerfile
│   │   ├── nvd_cve_downloader_v2.py
│   │   └── cve_cron_entrypoint.sh
│   ├── fact-collector/           # Ansible facts collector
│   │   ├── Dockerfile
│   │   └── fact_collector_worker.py
│   └── docker-compose.yml
├── frontend/
│   └── static/
│       └── index.html            # React dashboard
├── nginx/
│   └── vm_monitor.conf           # Nginx configuration
├── scripts/
│   ├── deploy.sh                 # Deployment script
│   └── backup.sh                 # Backup script
├── docs/
│   ├── ARCHITECTURE.md           # Detailed architecture
│   ├── API.md                    # API documentation
│   └── DEPLOYMENT.md             # Deployment guide
├── .env.example                  # Environment template
├── .gitignore
└── README.md
```

## 🔧 Configuration

### Environment Variables

Create `.env` file:

```env
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=infra_monitor
DB_USER=vm_monitor
DB_PASSWORD=your_secure_password

# Telegraf User
TELEGRAF_PASSWORD=your_telegraf_password

# Application Settings
LOG_LEVEL=INFO
```

### Database Schema

```sql
-- Real-time metrics table
CREATE TABLE vm_metrics (
    hostname VARCHAR(255) PRIMARY KEY,
    cpu_usage FLOAT,
    memory_usage FLOAT,
    disk_usage FLOAT,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Static VM information
CREATE TABLE vm_static_info (
    hostname VARCHAR(255) PRIMARY KEY,
    os_pretty_name VARCHAR(255),
    kernel_version VARCHAR(100),
    architecture VARCHAR(50),
    cpu_cores INTEGER,
    ram_total_gb FLOAT,
    last_updated TIMESTAMP
);

-- Package inventory
CREATE TABLE vm_packages (
    id SERIAL PRIMARY KEY,
    hostname VARCHAR(255),
    package_name VARCHAR(255),
    version VARCHAR(100),
    release VARCHAR(100),
    architecture VARCHAR(50)
);

-- CVE database
CREATE TABLE cve_database (
    cve_id VARCHAR(50) PRIMARY KEY,
    cvss_v3_score FLOAT,
    severity VARCHAR(20),
    affected_products JSONB,
    published_date TIMESTAMP
);

-- Package-CVE mappings
CREATE TABLE vm_package_cves (
    id SERIAL PRIMARY KEY,
    hostname VARCHAR(255),
    package_name VARCHAR(255),
    cve_id VARCHAR(50),
    cvss_score FLOAT,
    severity VARCHAR(20)
);
```

## 🐳 Container Management

### Check Status
```bash
podman ps
```

### View Logs
```bash
# Backend logs
podman logs -f vm-monitor-backend-1

# CVE downloader
podman logs vm-monitor-cve-downloader

# All containers
podman-compose logs
```

### Restart Services
```bash
# Single container
podman restart vm-monitor-backend-1

# All containers
podman-compose restart
```

### Scale Workers
```bash
# Add more Telegraf processors
podman run -d --name vm-monitor-telegraf-processor-4 \
  --network docker_monitor-network \
  --env-file .env \
  vm-monitor-telegraf-processor:latest
```

## 📡 API Endpoints

### Dashboard Statistics
```bash
GET /api/dashboard/stats
```
Response:
```json
{
  "total_vms": 133,
  "online_vms": 133,
  "avg_cpu": 4.40,
  "avg_memory": 18.86,
  "health_score": 100.0
}
```

### VM List
```bash
GET /api/vms
```

### VM Details
```bash
GET /api/vms/{hostname}
```

### Package Details with CVEs
```bash
GET /api/vms/{hostname}/packages/detail
```

### WebSocket (Real-time Updates)
```bash
wss://your-server.example.com/ws/metrics
```

## 🔐 Security

- **Environment Variables**: All secrets in `.env` file (never committed)
- **SSL/TLS**: Nginx handles HTTPS termination
- **Container Isolation**: Each service runs in isolated container
- **PostgreSQL**: Connection pooling with credential management
- **Redis**: Memory limit with LRU eviction

## 📈 Performance

### Current Metrics
- **133 VMs**: ~4 metrics/VM = 532 data points/minute
- **Backend**: 2 uvicorn workers, handles 100+ req/s
- **Telegraf Processors**: 3 workers, ~200 metrics/s throughput
- **Redis Cache**: 256MB, ~10ms response time
- **PostgreSQL**: Connection pool (2-10 connections)

### Scaling
- **Horizontal**: Add more backend/processor containers
- **Vertical**: Increase container resource limits
- **Database**: PostgreSQL replication/sharding for 1000+ VMs

## 🛠️ Development

### Local Development Setup

```bash
# Install dependencies
cd docker/backend
pip install -r requirements.txt

# Run backend locally
uvicorn postgres_backend:app --reload --port 8000

# Run frontend (dev server)
cd frontend/static
python -m http.server 8080
```

### Running Tests
```bash
# Unit tests
pytest tests/

# Integration tests
pytest tests/integration/
```

## 📝 Deployment

### Production Deployment

1. **Build images**
```bash
podman build -t vm-monitor-backend:latest ./docker/backend
podman build -t vm-monitor-telegraf-processor:latest ./docker/telegraf-processor
podman build -t vm-monitor-cve-downloader:latest ./docker/cve-downloader
```

2. **Deploy stack**
```bash
podman-compose up -d
```

3. **Configure Nginx**
```bash
cp nginx/vm_monitor.conf /etc/nginx/conf.d/
nginx -t && systemctl reload nginx
```

4. **Verify**
```bash
curl -k https://localhost/api/dashboard/stats
```

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed instructions.

## 🔄 Backup & Recovery

### Backup Container Images
```bash
podman save vm-monitor-backend:latest | gzip > backup/backend.tar.gz
```

### Backup Database
```bash
pg_dump -h localhost -U vm_monitor infra_monitor > backup/db_$(date +%Y%m%d).sql
```

### Restore
```bash
# Restore images
podman load < backup/backend.tar.gz

# Restore database
psql -h localhost -U vm_monitor infra_monitor < backup/db_20260804.sql
```

## 🐛 Troubleshooting

### Container Won't Start
```bash
# Check logs
podman logs vm-monitor-backend-1

# Inspect container
podman inspect vm-monitor-backend-1
```

### Backend 502 Error
```bash
# Test direct connection
curl http://localhost:8001/api/dashboard/stats

# Check Nginx logs
tail -50 /var/log/nginx/error.log
```

### High Memory Usage
```bash
# Check resource usage
podman stats --no-stream

# Restart container
podman restart vm-monitor-backend-1
```

## 📚 Documentation

- [Architecture Deep Dive](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Contributing Guidelines](CONTRIBUTING.md)

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Telegraf** - Metrics collection agent
- **FastAPI** - Modern Python web framework
- **PostgreSQL** - Robust relational database
- **Redis** - In-memory cache
- **NIST NVD** - CVE vulnerability database
- **React** - Frontend UI framework

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/YOUR_USERNAME/vm-monitor/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_USERNAME/vm-monitor/discussions)

## 🗺️ Roadmap

- [ ] Grafana dashboards for advanced visualization
- [ ] Prometheus exporter for metrics
- [ ] Email/Slack alerts for critical events
- [ ] Historical metrics retention (time-series DB)
- [ ] Multi-tenant support
- [ ] Kubernetes deployment manifests
- [ ] Automated fact collection workers
- [ ] Package vulnerability remediation suggestions

---

**Made with ❤️ for Enterprise Infrastructure Monitoring**

*Deploy once, monitor forever!*
