# CVE Tracking & Vulnerability Management

Complete guide to CVE vulnerability tracking, analysis, and remediation in VM Monitor.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [CVE Analysis](#cve-analysis)
- [Remediation Engine](#remediation-engine)
- [API Endpoints](#api-endpoints)
- [Risk Scoring](#risk-scoring)
- [Reports](#reports)
- [Best Practices](#best-practices)

---

## 🛡️ Overview

VM Monitor's CVE tracking system provides:
- **Automatic CVE matching** to installed packages
- **CVSS v3 scoring** for severity assessment
- **Remediation suggestions** with step-by-step guides
- **Fleet-wide reporting** for vulnerability trends
- **Risk scoring** to prioritize patching efforts

### Data Flow

```
NIST NVD API → CVE Database → Package Matching → Risk Analysis → Remediation
```

---

## ✨ Features

### 1. **Intelligent Package Matching**

- Normalizes package names for accurate matching
- Version comparison and range checking
- CPE (Common Platform Enumeration) parsing
- Multi-vendor product mapping

### 2. **Automated Remediation Suggestions**

- OS-specific patch commands (RHEL/Ubuntu/Alpine)
- Step-by-step remediation guides
- Batch update scripts
- Timeline recommendations based on CVSS scores

### 3. **Risk Scoring**

VM Monitor calculates a risk score for each VM:
```
Risk Score = (Critical CVEs × 10) + (High × 5) + (Medium × 2) + (Low × 1)
```

**Risk Levels:**
- **CRITICAL**: Score ≥ 50
- **HIGH**: Score ≥ 20
- **MEDIUM**: Score ≥ 10
- **LOW**: Score < 10

### 4. **Fleet-Wide Analytics**

- Most vulnerable VMs
- Widespread CVEs affecting multiple systems
- Package vulnerability hotspots
- Severity trending

---

## 🔍 CVE Analysis

### Per-VM Analysis

Get comprehensive vulnerability analysis for a single VM:

```python
from cve_analyzer import CVEAnalyzer

analyzer = CVEAnalyzer(db_pool)
report = await analyzer.analyze_vm_vulnerabilities('web-server-01')
```

**Response Structure:**
```json
{
  "hostname": "web-server-01",
  "os": "Red Hat Enterprise Linux 8.10",
  "analysis_date": "2026-08-05T15:30:00",
  "summary": {
    "total_cves": 45,
    "critical": 2,
    "high": 8,
    "medium": 20,
    "low": 15,
    "affected_packages": 12,
    "risk_score": 76,
    "risk_level": "CRITICAL"
  },
  "top_vulnerabilities": [...],
  "remediations": [...],
  "affected_packages": [...]
}
```

### CVE Details

Get detailed information about a specific CVE:

```python
details = await analyzer.get_cve_details('CVE-2024-1234')
```

**Response:**
```json
{
  "cve_id": "CVE-2024-1234",
  "cvss_score": 9.8,
  "severity": "CRITICAL",
  "description": "Remote code execution in OpenSSL...",
  "published_date": "2024-03-15T10:00:00",
  "affected_systems": 5,
  "affected_details": [
    {
      "hostname": "web-server-01",
      "package_name": "openssl",
      "cvss_score": 9.8
    }
  ],
  "references": [...]
}
```

---

## 🔧 Remediation Engine

### Single Package Remediation

Generate step-by-step remediation guide:

```python
from cve_analyzer import RemediationEngine

remediation = RemediationEngine.generate_remediation_steps(
    package_name='openssl',
    current_version='1.1.1k',
    cve_id='CVE-2024-1234',
    cvss_score=9.8,
    os_name='Red Hat Enterprise Linux 8'
)
```

**Response:**
```json
{
  "package": "openssl",
  "current_version": "1.1.1k",
  "cve_id": "CVE-2024-1234",
  "cvss_score": 9.8,
  "severity": "CRITICAL",
  "timeline": "Within 24 hours",
  "package_manager": "rpm",
  "steps": [
    {
      "step": 1,
      "action": "Assess Severity",
      "description": "CVE CVE-2024-1234 - CVSS Score: 9.8",
      "urgency": "CRITICAL - Patch immediately",
      "timeline": "Within 24 hours"
    },
    {
      "step": 2,
      "action": "Verify Current Version",
      "description": "Confirm openssl version 1.1.1k is installed",
      "command": "rpm -qa | grep openssl"
    },
    {
      "step": 3,
      "action": "Check for Updates",
      "description": "Query available updates for openssl",
      "command": "yum info openssl"
    },
    {
      "step": 4,
      "action": "Backup Configuration",
      "description": "Backup any configuration files before updating",
      "command": "cp -r /etc/openssl /root/backup_openssl_$(date +%Y%m%d) 2>/dev/null || echo 'No config to backup'"
    },
    {
      "step": 5,
      "action": "Update Package",
      "description": "Update openssl to patched version",
      "command": "yum update openssl",
      "note": "This will download and install the latest security-patched version"
    },
    {
      "step": 6,
      "action": "Verify Update",
      "description": "Confirm new version is installed and CVE is resolved",
      "command": "rpm -qa | grep openssl"
    }
  ],
  "references": [
    "https://nvd.nist.gov/vuln/detail/CVE-2024-1234",
    "https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2024-1234"
  ]
}
```

### Batch Remediation

Generate a shell script to patch multiple vulnerabilities:

```python
batch = RemediationEngine.generate_batch_remediation(
    vulnerabilities=[...],  # List of CVEs
    os_name='Red Hat Enterprise Linux 8'
)
```

**Generated Script:**
```bash
#!/bin/bash
# VM Monitor - Automated CVE Remediation Script
# Generated: 2026-08-05 15:30:00
# Total packages to update: 5

set -e  # Exit on error

echo '=== VM Monitor CVE Remediation ===='
echo 'Starting security updates...'

# Update package lists
yum check-update || true

# [1/5] Update openssl
# Resolves: CVE-2024-1234, CVE-2024-5678, CVE-2024-9012
echo 'Updating openssl...'
yum update -y openssl

# [2/5] Update kernel
# Resolves: CVE-2024-3456
echo 'Updating kernel...'
yum update -y kernel

# ... (remaining packages)

echo '=== Remediation Complete ==='
echo 'Updated 5 packages'
echo 'Please verify services and reboot if kernel was updated'
```

---

## 📡 API Endpoints

### GET `/api/cves`

Get all CVEs in database.

**Query Parameters:**
- `severity` - Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)
- `min_score` - Minimum CVSS score (0.0-10.0)
- `limit` - Maximum results

**Example:**
```bash
curl "http://localhost:8001/api/cves?severity=CRITICAL&limit=20"
```

### GET `/api/cves/{cve_id}`

Get details for specific CVE.

**Example:**
```bash
curl "http://localhost:8001/api/cves/CVE-2024-1234"
```

### GET `/api/vms/{hostname}/cves`

Get all CVEs affecting a specific VM.

**Query Parameters:**
- `severity` - Filter by severity
- `min_score` - Minimum CVSS score

**Example:**
```bash
curl "http://localhost:8001/api/vms/web-server-01/cves?severity=CRITICAL"
```

### GET `/api/vms/{hostname}/cve-analysis`

Get comprehensive vulnerability analysis for a VM.

**Example:**
```bash
curl "http://localhost:8001/api/vms/web-server-01/cve-analysis"
```

### GET `/api/vms/{hostname}/remediation`

Get remediation plan for a VM's vulnerabilities.

**Query Parameters:**
- `cve_id` - Specific CVE to remediate (optional)
- `batch` - Generate batch script (true/false)

**Example:**
```bash
# Single CVE remediation
curl "http://localhost:8001/api/vms/web-server-01/remediation?cve_id=CVE-2024-1234"

# Batch remediation script
curl "http://localhost:8001/api/vms/web-server-01/remediation?batch=true" > remediate.sh
chmod +x remediate.sh
```

### GET `/api/fleet/cve-report`

Get fleet-wide CVE report.

**Example:**
```bash
curl "http://localhost:8001/api/fleet/cve-report"
```

---

## 📊 Risk Scoring

### Severity Timelines

Based on CVSS score, VM Monitor recommends patching timelines:

| CVSS Score | Severity | Timeline | Urgency |
|------------|----------|----------|---------|
| 9.0 - 10.0 | CRITICAL | 24 hours | Immediate |
| 7.0 - 8.9  | HIGH     | 7 days   | High    |
| 4.0 - 6.9  | MEDIUM   | 30 days  | Medium  |
| 0.1 - 3.9  | LOW      | 90 days  | Low     |

### Risk Score Calculation

```
VM Risk Score = Σ (CVE Count × Weight)

Weights:
- Critical (CVSS ≥ 9.0): 10 points
- High (CVSS 7.0-8.9):   5 points
- Medium (CVSS 4.0-6.9): 2 points
- Low (CVSS < 4.0):      1 point
```

**Example:**
```
VM with:
- 2 Critical CVEs
- 5 High CVEs
- 10 Medium CVEs
- 3 Low CVEs

Risk Score = (2×10) + (5×5) + (10×2) + (3×1)
           = 20 + 25 + 20 + 3
           = 68 (CRITICAL)
```

---

## 📈 Reports

### VM Vulnerability Report

Comprehensive per-VM vulnerability analysis:

```json
{
  "hostname": "web-server-01",
  "os": "Red Hat Enterprise Linux 8.10",
  "summary": {
    "total_cves": 45,
    "critical": 2,
    "high": 8,
    "medium": 20,
    "low": 15,
    "risk_score": 76,
    "risk_level": "CRITICAL"
  },
  "top_vulnerabilities": [
    {
      "cve_id": "CVE-2024-1234",
      "package_name": "openssl",
      "version": "1.1.1k",
      "cvss_score": 9.8,
      "severity": "CRITICAL",
      "description": "Remote code execution...",
      "published_date": "2024-03-15T10:00:00"
    }
  ],
  "remediations": [...]
}
```

### Fleet CVE Report

Organization-wide vulnerability trends:

```json
{
  "report_date": "2026-08-05T15:30:00",
  "summary": {
    "total_unique_cves": 234,
    "severity_breakdown": {
      "CRITICAL": 15,
      "HIGH": 42,
      "MEDIUM": 98,
      "LOW": 79
    }
  },
  "most_vulnerable_vms": [
    {
      "hostname": "legacy-server-01",
      "cve_count": 87,
      "critical": 5,
      "high": 15
    }
  ],
  "widespread_cves": [
    {
      "cve_id": "CVE-2024-1234",
      "cvss_score": 9.8,
      "severity": "CRITICAL",
      "affected_vms": 25
    }
  ],
  "vulnerable_packages": [
    {
      "package_name": "openssl",
      "cve_count": 12,
      "affected_vms": 18
    }
  ]
}
```

---

## ✅ Best Practices

### 1. **Prioritize by Risk Score**

Focus on VMs with highest risk scores first:

```sql
SELECT hostname, risk_score
FROM vm_cve_analysis
ORDER BY risk_score DESC
LIMIT 10;
```

### 2. **Patch Critical CVEs Immediately**

Set up alerts for CVSS ≥ 9.0:

```bash
# In .env
ALERT_CVE_CRITICAL_COUNT=1
EMAIL_ENABLED=true
SLACK_ENABLED=true
```

### 3. **Regular Vulnerability Scanning**

Schedule daily CVE sync:

```bash
# In .env
CRON_SCHEDULE=0 2 * * *  # 2 AM daily
```

### 4. **Test Patches in Staging**

Never patch production directly:

1. Apply patches to staging VMs
2. Test for 24-48 hours
3. Monitor for regressions
4. Deploy to production if stable

### 5. **Track Remediation Progress**

Create a remediation tracking table:

```sql
CREATE TABLE remediation_log (
    id SERIAL PRIMARY KEY,
    hostname VARCHAR(255),
    cve_id VARCHAR(50),
    package_name VARCHAR(255),
    remediated_at TIMESTAMP DEFAULT NOW(),
    remediated_by VARCHAR(100),
    notes TEXT
);
```

### 6. **Automate Where Possible**

Use batch remediation scripts for non-critical systems:

```bash
# Generate script
curl "http://localhost:8001/api/vms/dev-server-01/remediation?batch=true" > patch.sh

# Review
cat patch.sh

# Execute
chmod +x patch.sh
./patch.sh
```

### 7. **Monitor for New CVEs**

Subscribe to security mailing lists:
- RHEL: https://access.redhat.com/security/updates/
- Ubuntu: https://ubuntu.com/security/notices
- NVD: https://nvd.nist.gov/general/email-list

---

## 🔄 Workflow

### Recommended CVE Management Workflow

```
1. Daily CVE Sync (Automated)
   ↓
2. Risk Assessment (VM Monitor)
   ↓
3. Alert on Critical CVEs (Automatic)
   ↓
4. Generate Remediation Plan (API)
   ↓
5. Test in Staging (Manual)
   ↓
6. Apply to Production (Manual/Automated)
   ↓
7. Verify Patching (VM Monitor)
   ↓
8. Document (Remediation Log)
```

---

## 🔗 References

- **NIST NVD**: https://nvd.nist.gov/
- **CVE MITRE**: https://cve.mitre.org/
- **CVSS Calculator**: https://nvd.nist.gov/vuln-metrics/cvss/v3-calculator
- **CPE Dictionary**: https://nvd.nist.gov/products/cpe

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/SAbdulra/vm-monitor/issues)
- **Documentation**: [Main README](../README.md)
- **API Docs**: [API.md](API.md)

---

**🛡️ Stay Secure!**
