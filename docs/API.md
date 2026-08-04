# VM Monitor API Documentation

Complete REST API reference for the VM Monitor backend.

**Base URL**: `http://your-server:8001/api`

**Authentication**: JWT Bearer token (for protected endpoints)

---

## 📋 Table of Contents

- [Authentication](#authentication)
- [Dashboard Endpoints](#dashboard-endpoints)
- [VM Endpoints](#vm-endpoints)
- [CVE Endpoints](#cve-endpoints)
- [WebSocket](#websocket)
- [Error Responses](#error-responses)

---

## 🔐 Authentication

### POST `/auth/login`

Authenticate user and receive JWT token.

**Request Body**:
```json
{
  "username": "user@example.com",
  "password": "your_password"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "username": "user",
    "display_name": "John Doe",
    "email": "user@example.com",
    "department": "IT",
    "title": "DevOps Engineer"
  }
}
```

**Error** (401 Unauthorized):
```json
{
  "detail": "Incorrect username or password"
}
```

---

### POST `/auth/logout`

Logout current user (client should delete token).

**Headers**:
```
Authorization: Bearer <token>
```

**Response** (200 OK):
```json
{
  "message": "Logged out successfully"
}
```

---

### GET `/auth/me`

Get current authenticated user information.

**Headers**:
```
Authorization: Bearer <token>
```

**Response** (200 OK):
```json
{
  "username": "user",
  "email": "user@example.com",
  "display_name": "John Doe",
  "department": "IT",
  "title": "DevOps Engineer"
}
```

---

## 📊 Dashboard Endpoints

### GET `/dashboard/stats`

Get aggregated statistics for all VMs.

**Response** (200 OK):
```json
{
  "total": 133,
  "online": 128,
  "warning": 4,
  "critical": 1,
  "avg_cpu": 23.5,
  "avg_memory": 45.2,
  "avg_disk": 62.8,
  "high_severity_cves": 12,
  "critical_severity_cves": 3,
  "last_updated": "2026-08-05T10:30:00"
}
```

**Fields**:
- `total`: Total number of VMs
- `online`: VMs reporting metrics in last 5 minutes
- `warning`: VMs with CPU/Memory/Disk > 80%
- `critical`: VMs with CPU/Memory/Disk > 95%
- `avg_cpu`: Average CPU usage across all VMs (%)
- `avg_memory`: Average memory usage (%)
- `avg_disk`: Average disk usage (%)
- `high_severity_cves`: Count of CVEs with CVSS ≥ 7.0
- `critical_severity_cves`: Count of CVEs with CVSS ≥ 9.0

---

### GET `/dashboard/metrics`

Get real-time metrics for all VMs.

**Response** (200 OK):
```json
[
  {
    "hostname": "web-server-01",
    "cpu_usage": 45.2,
    "memory_usage": 62.8,
    "disk_usage": 78.5,
    "swap_usage": 12.3,
    "timestamp": "2026-08-05T10:30:15",
    "status": "online"
  },
  {
    "hostname": "db-server-01",
    "cpu_usage": 78.9,
    "memory_usage": 85.4,
    "disk_usage": 92.1,
    "swap_usage": 5.2,
    "timestamp": "2026-08-05T10:30:12",
    "status": "warning"
  }
]
```

**Query Parameters**:
- `limit` (optional): Limit number of results (default: all)
- `status` (optional): Filter by status (`online`, `warning`, `critical`)

Example:
```
GET /api/dashboard/metrics?status=warning&limit=10
```

---

## 💻 VM Endpoints

### GET `/vms`

Get list of all VMs with current metrics.

**Response** (200 OK):
```json
[
  {
    "hostname": "web-server-01",
    "os_pretty_name": "Red Hat Enterprise Linux 8.10",
    "kernel_version": "4.18.0-513.5.1.el8_9.x86_64",
    "architecture": "x86_64",
    "cpu_cores": 4,
    "ram_total_gb": 16.0,
    "uptime_days": 45,
    "cpu_usage": 45.2,
    "memory_usage": 62.8,
    "disk_usage": 78.5,
    "swap_usage": 12.3,
    "timestamp": "2026-08-05T10:30:15",
    "status": "online",
    "total_packages": 1234,
    "vulnerable_packages": 8,
    "high_severity_cves": 3,
    "critical_severity_cves": 1
  }
]
```

---

### GET `/vms/{hostname}`

Get detailed information for a specific VM.

**Path Parameters**:
- `hostname`: VM hostname

**Response** (200 OK):
```json
{
  "hostname": "web-server-01",
  "static_info": {
    "os_pretty_name": "Red Hat Enterprise Linux 8.10",
    "kernel_version": "4.18.0-513.5.1.el8_9.x86_64",
    "architecture": "x86_64",
    "cpu_cores": 4,
    "ram_total_gb": 16.0,
    "uptime_days": 45,
    "last_updated": "2026-08-05T10:00:00"
  },
  "current_metrics": {
    "cpu_usage": 45.2,
    "memory_usage": 62.8,
    "disk_usage": 78.5,
    "swap_usage": 12.3,
    "timestamp": "2026-08-05T10:30:15"
  },
  "packages": {
    "total": 1234,
    "vulnerable": 8
  },
  "cves": {
    "total": 12,
    "critical": 1,
    "high": 3,
    "medium": 5,
    "low": 3
  }
}
```

**Error** (404 Not Found):
```json
{
  "detail": "VM not found"
}
```

---

### GET `/vms/{hostname}/packages`

Get installed packages for a specific VM.

**Path Parameters**:
- `hostname`: VM hostname

**Response** (200 OK):
```json
[
  {
    "package_name": "kernel",
    "version": "4.18.0",
    "release": "513.5.1.el8_9",
    "architecture": "x86_64",
    "install_date": "2026-07-15T08:30:00",
    "vulnerable": true,
    "cve_count": 2
  },
  {
    "package_name": "openssl",
    "version": "1.1.1k",
    "release": "12.el8",
    "architecture": "x86_64",
    "install_date": "2026-06-20T14:22:00",
    "vulnerable": false,
    "cve_count": 0
  }
]
```

**Query Parameters**:
- `vulnerable_only` (optional): Show only vulnerable packages (`true`/`false`)

Example:
```
GET /api/vms/web-server-01/packages?vulnerable_only=true
```

---

## 🛡️ CVE Endpoints

### GET `/cves`

Get all CVEs in database.

**Response** (200 OK):
```json
[
  {
    "cve_id": "CVE-2024-1234",
    "cvss_v3_score": 9.8,
    "severity": "CRITICAL",
    "description": "Remote code execution vulnerability in...",
    "published_date": "2024-03-15T10:00:00",
    "affected_vms": 3
  }
]
```

**Query Parameters**:
- `severity` (optional): Filter by severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)
- `min_score` (optional): Minimum CVSS score (0.0 - 10.0)
- `limit` (optional): Limit results

Example:
```
GET /api/cves?severity=CRITICAL&limit=20
```

---

### GET `/cves/{cve_id}`

Get details for a specific CVE.

**Path Parameters**:
- `cve_id`: CVE identifier (e.g., CVE-2024-1234)

**Response** (200 OK):
```json
{
  "cve_id": "CVE-2024-1234",
  "cvss_v3_score": 9.8,
  "severity": "CRITICAL",
  "description": "Remote code execution vulnerability in OpenSSL...",
  "published_date": "2024-03-15T10:00:00",
  "affected_products": [
    "cpe:2.3:a:openssl:openssl:1.1.1:*:*:*:*:*:*:*",
    "cpe:2.3:a:openssl:openssl:1.1.1k:*:*:*:*:*:*:*"
  ],
  "affected_vms": [
    {
      "hostname": "web-server-01",
      "package_name": "openssl",
      "version": "1.1.1k-12.el8"
    },
    {
      "hostname": "app-server-02",
      "package_name": "openssl",
      "version": "1.1.1k-12.el8"
    }
  ],
  "references": [
    "https://nvd.nist.gov/vuln/detail/CVE-2024-1234",
    "https://www.openssl.org/news/secadv/20240315.txt"
  ]
}
```

---

### GET `/vms/{hostname}/cves`

Get CVEs affecting a specific VM.

**Path Parameters**:
- `hostname`: VM hostname

**Response** (200 OK):
```json
[
  {
    "cve_id": "CVE-2024-1234",
    "package_name": "openssl",
    "version": "1.1.1k-12.el8",
    "cvss_score": 9.8,
    "severity": "CRITICAL",
    "description": "Remote code execution vulnerability...",
    "published_date": "2024-03-15T10:00:00"
  }
]
```

**Query Parameters**:
- `severity` (optional): Filter by severity
- `min_score` (optional): Minimum CVSS score

---

## 🔌 WebSocket

### WS `/ws/metrics`

Real-time metrics stream via WebSocket.

**Connection**:
```javascript
const ws = new WebSocket('ws://your-server:8001/ws/metrics');

// First message: send authentication token
ws.onopen = () => {
  ws.send(JSON.stringify({
    token: 'your_jwt_token_here'
  }));
};

// Receive real-time updates
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Metrics update:', data);
};
```

**Authentication Message** (first message after connection):
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Server Messages**:

**1. Metrics Update**:
```json
{
  "type": "metrics_update",
  "data": {
    "hostname": "web-server-01",
    "cpu_usage": 45.2,
    "memory_usage": 62.8,
    "disk_usage": 78.5,
    "swap_usage": 12.3,
    "timestamp": "2026-08-05T10:30:15"
  }
}
```

**2. VM Status Change**:
```json
{
  "type": "status_change",
  "data": {
    "hostname": "web-server-01",
    "old_status": "online",
    "new_status": "warning",
    "reason": "CPU usage > 80%"
  }
}
```

**3. New CVE Alert**:
```json
{
  "type": "cve_alert",
  "data": {
    "cve_id": "CVE-2024-5678",
    "severity": "CRITICAL",
    "affected_vms": 5,
    "cvss_score": 9.8
  }
}
```

**Error Messages**:
```json
{
  "type": "error",
  "message": "Authentication failed",
  "code": "AUTH_FAILED"
}
```

---

## ❌ Error Responses

All API errors follow this format:

**400 Bad Request**:
```json
{
  "detail": "Invalid input",
  "errors": [
    {
      "field": "username",
      "message": "Username is required"
    }
  ]
}
```

**401 Unauthorized**:
```json
{
  "detail": "Could not validate credentials"
}
```

**403 Forbidden**:
```json
{
  "detail": "Not enough permissions"
}
```

**404 Not Found**:
```json
{
  "detail": "Resource not found"
}
```

**429 Too Many Requests**:
```json
{
  "detail": "Rate limit exceeded. Retry after 60 seconds"
}
```

**500 Internal Server Error**:
```json
{
  "detail": "Internal server error",
  "request_id": "abc123"
}
```

---

## 📈 Rate Limiting

- **Anonymous**: 60 requests per minute
- **Authenticated**: 600 requests per minute
- **WebSocket**: No limit (maintained connection)

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 595
X-RateLimit-Reset: 1722848400
```

---

## 🔍 Filtering & Pagination

Most list endpoints support filtering and pagination:

**Query Parameters**:
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum records to return (default: 100, max: 1000)
- `sort_by`: Field to sort by
- `order`: Sort order (`asc` or `desc`)

Example:
```
GET /api/vms?skip=20&limit=10&sort_by=cpu_usage&order=desc
```

---

## 📝 Examples

### cURL Examples

**Login**:
```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"pass"}'
```

**Get Dashboard Stats**:
```bash
curl http://localhost:8001/api/dashboard/stats
```

**Get VMs (Authenticated)**:
```bash
curl http://localhost:8001/api/vms \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Python Example

```python
import requests

# Login
response = requests.post(
    'http://localhost:8001/api/auth/login',
    json={'username': 'user', 'password': 'pass'}
)
token = response.json()['access_token']

# Get metrics
headers = {'Authorization': f'Bearer {token}'}
metrics = requests.get(
    'http://localhost:8001/api/dashboard/metrics',
    headers=headers
).json()

print(f"Total VMs: {len(metrics)}")
```

### JavaScript Example

```javascript
// Login
const login = async () => {
  const response = await fetch('http://localhost:8001/api/auth/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username: 'user', password: 'pass'})
  });
  const data = await response.json();
  return data.access_token;
};

// Get VMs
const getVMs = async (token) => {
  const response = await fetch('http://localhost:8001/api/vms', {
    headers: {'Authorization': `Bearer ${token}`}
  });
  return await response.json();
};

// Usage
const token = await login();
const vms = await getVMs(token);
console.log(`Total VMs: ${vms.length}`);
```

---

## 🛠️ Development

### Running Locally

```bash
# Install dependencies
pip install -r docker/backend/requirements.txt

# Set environment variables
export DB_HOST=localhost
export DB_PASSWORD=your_password

# Run development server
uvicorn postgres_backend:app --reload --port 8000
```

### API Documentation (Interactive)

Once the server is running, visit:
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

---

## 📚 Additional Resources

- [Architecture Documentation](ARCHITECTURE.md)
- [Quick Start Guide](../QUICKSTART.md)
- [Contributing Guidelines](../CONTRIBUTING.md)
- [Security Policy](../SECURITY.md)

---

**Need help?** Open an issue on [GitHub](https://github.com/SAbdulra/vm-monitor/issues)
