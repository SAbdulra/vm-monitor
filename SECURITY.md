# Security Policy

## 🔒 Supported Versions

We release security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

---

## 🚨 Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please follow these steps:

### **DO NOT** open a public GitHub issue

Instead, please report security vulnerabilities responsibly:

1. **Email**: Send details to the repository maintainer
2. **GitHub Security Advisory**: Use [GitHub's private vulnerability reporting](https://github.com/SAbdulra/vm-monitor/security/advisories/new)

### What to Include

Please include the following information:
- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact
- Suggested fix (if you have one)
- Your contact information

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity
  - Critical: 1-7 days
  - High: 7-14 days
  - Medium: 14-30 days
  - Low: 30-90 days

---

## 🛡️ Security Best Practices

### Before Deployment

#### 1. **Change All Default Credentials**

```bash
# Generate secure database password
openssl rand -base64 32

# Generate JWT secret key
openssl rand -hex 32
```

Update `.env`:
```env
DB_PASSWORD=<generated_password>
JWT_SECRET_KEY=<generated_secret>
```

#### 2. **Review `.gitignore`**

Ensure these are excluded:
```
.env
*.key
*.pem
credentials/
secrets/
```

#### 3. **Enable HTTPS**

Never run in production without SSL/TLS:
```bash
# Generate self-signed certificate (for testing)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl.key -out nginx/ssl.crt

# For production, use Let's Encrypt
certbot certonly --nginx -d your-domain.com
```

#### 4. **Restrict Database Access**

PostgreSQL `pg_hba.conf`:
```conf
# Only allow connections from application server
host    infra_monitor    vm_monitor    10.0.0.0/24    scram-sha-256
host    infra_monitor    telegraf      10.0.0.0/24    scram-sha-256

# Deny all others
host    all              all           0.0.0.0/0      reject
```

#### 5. **Configure Firewall**

```bash
# Allow only necessary ports
firewall-cmd --permanent --add-port=443/tcp   # HTTPS
firewall-cmd --permanent --add-port=8086/tcp  # Telegraf aggregator (internal only)
firewall-cmd --permanent --add-port=5432/tcp  # PostgreSQL (internal only)

# Block direct backend access from internet
firewall-cmd --permanent --add-rich-rule='
  rule family="ipv4" source address="0.0.0.0/0" port port="8001" protocol="tcp" reject'

firewall-cmd --reload
```

---

## 🔐 Authentication & Authorization

### LDAP/AD Integration

Configure LDAP securely in `.env`:
```env
LDAP_SERVER=ldaps://ldap.example.com  # Use LDAPS (port 636) not LDAP (389)
LDAP_PORT=636
LDAP_BASE_DN=dc=example,dc=com
LDAP_DOMAIN=EXAMPLE
```

### JWT Token Security

- **Secret Key**: Must be cryptographically random (32+ bytes)
- **Expiration**: Default 8 hours, adjust based on your security needs
- **Storage**: Never store in localStorage, use httpOnly cookies or sessionStorage

```javascript
// BAD - vulnerable to XSS
localStorage.setItem('token', token);

// GOOD - httpOnly cookie (server-side)
Set-Cookie: token=...; HttpOnly; Secure; SameSite=Strict
```

### Password Policy

Enforce strong passwords:
- Minimum 12 characters
- Mix of uppercase, lowercase, numbers, symbols
- No dictionary words
- Different from username

---

## 🗄️ Database Security

### 1. **Use Principle of Least Privilege**

```sql
-- Backend user: full access to tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO vm_monitor;

-- Telegraf user: only INSERT on metrics tables
GRANT INSERT ON vm_metrics TO telegraf;
GRANT INSERT ON vm_static_info TO telegraf;
GRANT INSERT ON vm_packages TO telegraf;

-- Deny everything else
REVOKE ALL ON SCHEMA public FROM telegraf;
```

### 2. **Enable SSL Connections**

PostgreSQL `postgresql.conf`:
```conf
ssl = on
ssl_cert_file = '/path/to/server.crt'
ssl_key_file = '/path/to/server.key'
ssl_ca_file = '/path/to/ca.crt'
```

Application connection:
```env
DB_SSL_MODE=require  # or 'verify-full' for maximum security
```

### 3. **Encrypt Sensitive Data**

For PII or credentials in database:
```sql
-- Use PostgreSQL's pgcrypto extension
CREATE EXTENSION pgcrypto;

-- Encrypt sensitive columns
INSERT INTO users (username, password_hash)
VALUES ('user', crypt('password', gen_salt('bf')));
```

### 4. **Regular Backups**

```bash
# Automated daily backups
0 2 * * * pg_dump -U vm_monitor infra_monitor | \
  gpg --encrypt --recipient backups@example.com > \
  /backup/infra_monitor_$(date +\%Y\%m\%d).sql.gpg
```

---

## 🐳 Container Security

### 1. **Run as Non-Root User**

Dockerfile:
```dockerfile
# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Switch to non-root user
USER appuser

CMD ["uvicorn", "postgres_backend:app", "--host", "0.0.0.0"]
```

### 2. **Scan Images for Vulnerabilities**

```bash
# Scan with Trivy
trivy image vm-monitor-backend:latest

# Scan with Grype
grype vm-monitor-backend:latest
```

### 3. **Use Read-Only Filesystems**

`docker-compose.yml`:
```yaml
services:
  backend:
    image: vm-monitor-backend:latest
    read_only: true
    tmpfs:
      - /tmp
      - /var/run
```

### 4. **Limit Resources**

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

### 5. **Network Isolation**

```yaml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No internet access

services:
  backend:
    networks:
      - backend
  
  nginx:
    networks:
      - frontend
      - backend
```

---

## 🌐 Network Security

### 1. **Enable CORS Properly**

**BAD**:
```python
allow_origins=["*"]  # Allows any domain
```

**GOOD**:
```python
allow_origins=[
    "https://monitor.example.com",
    "https://dashboard.example.com"
]
```

### 2. **Rate Limiting**

Nginx configuration:
```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

location /api/ {
    limit_req zone=api burst=20 nodelay;
    proxy_pass http://backend:8000;
}
```

### 3. **Security Headers**

Nginx:
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
```

---

## 🔍 Monitoring & Logging

### 1. **Log Security Events**

```python
logger.warning(f"Failed login attempt: {username} from {request.client.host}")
logger.error(f"Unauthorized access attempt to {endpoint} by {user}")
logger.critical(f"SQL injection detected in query: {query}")
```

### 2. **Monitor Failed Logins**

```bash
# Alert on 5 failed logins in 5 minutes
grep "Failed login" /var/log/vm-monitor/app.log | \
  tail -n 100 | \
  awk '{print $1, $2}' | \
  uniq -c | \
  awk '$1 >= 5 {print "ALERT: Possible brute force from " $2}'
```

### 3. **Enable Audit Logging**

PostgreSQL:
```sql
-- Enable query logging for sensitive operations
CREATE EXTENSION IF NOT EXISTS pgaudit;

ALTER SYSTEM SET pgaudit.log = 'write, ddl';
ALTER SYSTEM SET pgaudit.log_catalog = off;
ALTER SYSTEM SET pgaudit.log_level = 'notice';
```

---

## 📋 Security Checklist

Before deploying to production:

### Environment

- [ ] All default passwords changed
- [ ] JWT secret key is cryptographically random
- [ ] `.env` file excluded from git
- [ ] No secrets in code or config files
- [ ] HTTPS/TLS enabled with valid certificates
- [ ] Database connections use SSL

### Authentication

- [ ] LDAP/AD uses LDAPS (not LDAP)
- [ ] JWT tokens have reasonable expiration
- [ ] Password policy enforced
- [ ] Failed login attempts monitored
- [ ] Account lockout after N failed attempts

### Network

- [ ] Firewall rules configured
- [ ] Only necessary ports exposed
- [ ] CORS configured correctly (not `*`)
- [ ] Rate limiting enabled
- [ ] Security headers configured

### Database

- [ ] Least privilege access enforced
- [ ] Separate users for backend/telegraf
- [ ] SSL connections required
- [ ] Regular backups configured
- [ ] Backup encryption enabled

### Containers

- [ ] Images scanned for vulnerabilities
- [ ] Running as non-root user
- [ ] Resource limits configured
- [ ] Read-only filesystems where possible
- [ ] Network isolation configured

### Monitoring

- [ ] Security event logging enabled
- [ ] Log rotation configured
- [ ] Alerts for suspicious activity
- [ ] Audit logging enabled
- [ ] Log retention policy defined

---

## 🔄 Update Policy

### Security Updates

Critical security patches are released immediately. Subscribe to notifications:
- Watch this repository on GitHub
- Enable security alerts
- Join discussions for announcements

### Updating

```bash
# Backup first
pg_dump infra_monitor > backup.sql

# Pull latest version
git pull origin main

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Verify
docker-compose ps
curl -k https://localhost/api/dashboard/stats
```

---

## 📚 Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

---

## 📞 Contact

For security concerns:
- GitHub Security Advisory: [Create Advisory](https://github.com/SAbdulra/vm-monitor/security/advisories/new)
- Issue Tracker: [Report Issue](https://github.com/SAbdulra/vm-monitor/issues)

**Please report security vulnerabilities responsibly.**
