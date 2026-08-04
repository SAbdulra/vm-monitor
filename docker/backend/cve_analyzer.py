"""
CVE Analyzer & Remediation Engine
Advanced CVE tracking with package matching and remediation suggestions
"""
import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import asyncpg

logger = logging.getLogger(__name__)


class CVEMatcher:
    """Intelligent CVE-to-Package matching"""

    @staticmethod
    def normalize_package_name(name: str) -> str:
        """Normalize package name for better matching"""
        # Remove common prefixes/suffixes
        name = name.lower().strip()
        name = re.sub(r'^(lib|python3?-|perl-|ruby-)', '', name)
        name = re.sub(r'(-dev|-devel|-doc|-common)$', '', name)
        return name

    @staticmethod
    def parse_version(version: str) -> Tuple[List[int], str]:
        """Parse version string into comparable parts"""
        # Extract numeric parts
        numeric = re.findall(r'\d+', version)
        numeric_parts = [int(x) for x in numeric] if numeric else [0]

        # Keep full version for exact matching
        return numeric_parts, version.lower()

    @staticmethod
    def version_in_range(pkg_version: str, cve_version_range: str) -> bool:
        """Check if package version falls within CVE affected range"""
        try:
            pkg_parts, pkg_full = CVEMatcher.parse_version(pkg_version)

            # Simple version comparison (can be enhanced)
            # For now, check if version strings match
            if cve_version_range.lower() in pkg_full or pkg_full in cve_version_range.lower():
                return True

            return False
        except Exception as e:
            logger.debug(f"Version comparison error: {e}")
            return False

    @staticmethod
    def extract_product_from_cpe(cpe: str) -> Optional[str]:
        """Extract product name from CPE string"""
        # CPE format: cpe:2.3:a:vendor:product:version:...
        try:
            parts = cpe.split(':')
            if len(parts) >= 5:
                return parts[4]  # product name
        except Exception:
            pass
        return None


class RemediationEngine:
    """Generate remediation suggestions for CVEs"""

    # Common package managers and their update commands
    PACKAGE_MANAGERS = {
        'rpm': {
            'check': 'rpm -qa | grep {package}',
            'update': 'yum update {package}',
            'info': 'yum info {package}'
        },
        'deb': {
            'check': 'dpkg -l | grep {package}',
            'update': 'apt-get update && apt-get install --only-upgrade {package}',
            'info': 'apt-cache show {package}'
        },
        'apk': {
            'check': 'apk info | grep {package}',
            'update': 'apk update && apk upgrade {package}',
            'info': 'apk info {package}'
        }
    }

    @staticmethod
    def detect_package_manager(os_name: str) -> str:
        """Detect package manager from OS name"""
        os_lower = os_name.lower()

        if any(x in os_lower for x in ['rhel', 'centos', 'fedora', 'rocky', 'alma']):
            return 'rpm'
        elif any(x in os_lower for x in ['ubuntu', 'debian']):
            return 'deb'
        elif 'alpine' in os_lower:
            return 'apk'

        return 'rpm'  # default

    @staticmethod
    def generate_remediation_steps(
        package_name: str,
        current_version: str,
        cve_id: str,
        cvss_score: float,
        os_name: str
    ) -> Dict:
        """Generate step-by-step remediation guide"""

        pkg_mgr = RemediationEngine.detect_package_manager(os_name)
        commands = RemediationEngine.PACKAGE_MANAGERS.get(pkg_mgr, RemediationEngine.PACKAGE_MANAGERS['rpm'])

        steps = []

        # Step 1: Assess severity
        if cvss_score >= 9.0:
            urgency = "CRITICAL - Patch immediately"
            timeline = "Within 24 hours"
        elif cvss_score >= 7.0:
            urgency = "HIGH - Patch within 7 days"
            timeline = "Within 1 week"
        elif cvss_score >= 4.0:
            urgency = "MEDIUM - Patch within 30 days"
            timeline = "Within 1 month"
        else:
            urgency = "LOW - Patch during next maintenance window"
            timeline = "Next maintenance cycle"

        steps.append({
            "step": 1,
            "action": "Assess Severity",
            "description": f"CVE {cve_id} - CVSS Score: {cvss_score}",
            "urgency": urgency,
            "timeline": timeline
        })

        # Step 2: Check current version
        steps.append({
            "step": 2,
            "action": "Verify Current Version",
            "description": f"Confirm {package_name} version {current_version} is installed",
            "command": commands['check'].format(package=package_name)
        })

        # Step 3: Check for updates
        steps.append({
            "step": 3,
            "action": "Check for Updates",
            "description": f"Query available updates for {package_name}",
            "command": commands['info'].format(package=package_name)
        })

        # Step 4: Backup (if critical service)
        steps.append({
            "step": 4,
            "action": "Backup Configuration",
            "description": "Backup any configuration files before updating",
            "command": f"cp -r /etc/{package_name} /root/backup_{package_name}_$(date +%Y%m%d) 2>/dev/null || echo 'No config to backup'"
        })

        # Step 5: Update package
        steps.append({
            "step": 5,
            "action": "Update Package",
            "description": f"Update {package_name} to patched version",
            "command": commands['update'].format(package=package_name),
            "note": "This will download and install the latest security-patched version"
        })

        # Step 6: Verify update
        steps.append({
            "step": 6,
            "action": "Verify Update",
            "description": "Confirm new version is installed and CVE is resolved",
            "command": commands['check'].format(package=package_name)
        })

        # Step 7: Restart services (if needed)
        if any(svc in package_name.lower() for svc in ['httpd', 'nginx', 'ssh', 'kernel', 'systemd']):
            steps.append({
                "step": 7,
                "action": "Restart Service",
                "description": f"Restart affected service to apply changes",
                "command": f"systemctl restart {package_name}",
                "note": "May cause brief service interruption"
            })

        return {
            "package": package_name,
            "current_version": current_version,
            "cve_id": cve_id,
            "cvss_score": cvss_score,
            "severity": urgency.split(' - ')[0],
            "timeline": timeline,
            "package_manager": pkg_mgr,
            "steps": steps,
            "references": [
                f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                f"https://cve.mitre.org/cgi-bin/cvename.cgi?name={cve_id}"
            ]
        }

    @staticmethod
    def generate_batch_remediation(vulnerabilities: List[Dict], os_name: str) -> Dict:
        """Generate batch remediation script for multiple CVEs"""

        pkg_mgr = RemediationEngine.detect_package_manager(os_name)

        # Group by package
        packages_to_update = {}
        for vuln in vulnerabilities:
            pkg = vuln['package_name']
            if pkg not in packages_to_update:
                packages_to_update[pkg] = {
                    'current_version': vuln['version'],
                    'cves': []
                }
            packages_to_update[pkg]['cves'].append(vuln['cve_id'])

        # Generate script
        script_lines = [
            "#!/bin/bash",
            "# VM Monitor - Automated CVE Remediation Script",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Total packages to update: {len(packages_to_update)}",
            "",
            "set -e  # Exit on error",
            "",
            "echo '=== VM Monitor CVE Remediation ===='",
            "echo 'Starting security updates...'",
            ""
        ]

        if pkg_mgr == 'rpm':
            script_lines.extend([
                "# Update package lists",
                "yum check-update || true",
                ""
            ])
        elif pkg_mgr == 'deb':
            script_lines.extend([
                "# Update package lists",
                "apt-get update",
                ""
            ])

        # Add package updates
        for idx, (pkg, info) in enumerate(packages_to_update.items(), 1):
            cve_list = ', '.join(info['cves'][:3])  # Show first 3 CVEs
            if len(info['cves']) > 3:
                cve_list += f" (+{len(info['cves']) - 3} more)"

            script_lines.extend([
                f"# [{idx}/{len(packages_to_update)}] Update {pkg}",
                f"# Resolves: {cve_list}",
                f"echo 'Updating {pkg}...'",
            ])

            if pkg_mgr == 'rpm':
                script_lines.append(f"yum update -y {pkg}")
            elif pkg_mgr == 'deb':
                script_lines.append(f"apt-get install --only-upgrade -y {pkg}")
            elif pkg_mgr == 'apk':
                script_lines.append(f"apk upgrade {pkg}")

            script_lines.append("")

        script_lines.extend([
            "echo '=== Remediation Complete ==='",
            f"echo 'Updated {len(packages_to_update)} packages'",
            "echo 'Please verify services and reboot if kernel was updated'",
            ""
        ])

        return {
            "total_packages": len(packages_to_update),
            "total_cves": len(vulnerabilities),
            "package_manager": pkg_mgr,
            "script": "\n".join(script_lines),
            "packages": list(packages_to_update.keys())
        }


class CVEAnalyzer:
    """Main CVE analysis and reporting engine"""

    def __init__(self, db_pool):
        self.db = db_pool

    async def analyze_vm_vulnerabilities(self, hostname: str) -> Dict:
        """Comprehensive vulnerability analysis for a VM"""

        async with self.db.acquire() as conn:
            # Get VM OS info
            vm_info = await conn.fetchrow(
                "SELECT os_pretty_name FROM vm_static_info WHERE hostname = $1",
                hostname
            )

            if not vm_info:
                return {"error": "VM not found"}

            os_name = vm_info['os_pretty_name'] or "Unknown"

            # Get all CVEs for this VM
            cves = await conn.fetch("""
                SELECT
                    vpc.cve_id,
                    vpc.package_name,
                    vp.version,
                    vp.release,
                    vpc.cvss_score,
                    vpc.severity,
                    cd.description,
                    cd.published_date
                FROM vm_package_cves vpc
                JOIN vm_packages vp ON vpc.hostname = vp.hostname
                    AND vpc.package_name = vp.package_name
                LEFT JOIN cve_database cd ON vpc.cve_id = cd.cve_id
                WHERE vpc.hostname = $1
                ORDER BY vpc.cvss_score DESC
            """, hostname)

            vulnerabilities = [dict(row) for row in cves]

            # Categorize by severity
            categories = {
                'critical': [v for v in vulnerabilities if v['cvss_score'] >= 9.0],
                'high': [v for v in vulnerabilities if 7.0 <= v['cvss_score'] < 9.0],
                'medium': [v for v in vulnerabilities if 4.0 <= v['cvss_score'] < 7.0],
                'low': [v for v in vulnerabilities if v['cvss_score'] < 4.0]
            }

            # Generate risk score
            risk_score = (
                len(categories['critical']) * 10 +
                len(categories['high']) * 5 +
                len(categories['medium']) * 2 +
                len(categories['low']) * 1
            )

            # Determine overall risk level
            if risk_score >= 50:
                risk_level = "CRITICAL"
            elif risk_score >= 20:
                risk_level = "HIGH"
            elif risk_score >= 10:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

            # Top 5 most critical CVEs
            top_cves = vulnerabilities[:5] if vulnerabilities else []

            # Generate remediation for top CVEs
            remediations = []
            for cve in top_cves:
                remediation = RemediationEngine.generate_remediation_steps(
                    package_name=cve['package_name'],
                    current_version=cve['version'],
                    cve_id=cve['cve_id'],
                    cvss_score=cve['cvss_score'],
                    os_name=os_name
                )
                remediations.append(remediation)

            # Package summary
            affected_packages = list(set([v['package_name'] for v in vulnerabilities]))

            return {
                "hostname": hostname,
                "os": os_name,
                "analysis_date": datetime.now().isoformat(),
                "summary": {
                    "total_cves": len(vulnerabilities),
                    "critical": len(categories['critical']),
                    "high": len(categories['high']),
                    "medium": len(categories['medium']),
                    "low": len(categories['low']),
                    "affected_packages": len(affected_packages),
                    "risk_score": risk_score,
                    "risk_level": risk_level
                },
                "categories": {
                    "critical": [{"cve_id": v['cve_id'], "package": v['package_name'], "cvss": v['cvss_score']} for v in categories['critical']],
                    "high": [{"cve_id": v['cve_id'], "package": v['package_name'], "cvss": v['cvss_score']} for v in categories['high']],
                    "medium": [{"cve_id": v['cve_id'], "package": v['package_name'], "cvss": v['cvss_score']} for v in categories['medium'][:10]],  # Limit
                    "low": [{"cve_id": v['cve_id'], "package": v['package_name'], "cvss": v['cvss_score']} for v in categories['low'][:10]]  # Limit
                },
                "top_vulnerabilities": top_cves,
                "remediations": remediations,
                "affected_packages": affected_packages
            }

    async def generate_fleet_cve_report(self) -> Dict:
        """Generate CVE report for entire VM fleet"""

        async with self.db.acquire() as conn:
            # Total CVEs across fleet
            total_cves = await conn.fetchval(
                "SELECT COUNT(DISTINCT cve_id) FROM vm_package_cves"
            )

            # CVEs by severity
            severity_breakdown = await conn.fetch("""
                SELECT severity, COUNT(DISTINCT cve_id) as count
                FROM vm_package_cves
                GROUP BY severity
            """)

            # Most vulnerable VMs
            vulnerable_vms = await conn.fetch("""
                SELECT
                    hostname,
                    COUNT(*) as cve_count,
                    SUM(CASE WHEN cvss_score >= 9.0 THEN 1 ELSE 0 END) as critical,
                    SUM(CASE WHEN cvss_score >= 7.0 AND cvss_score < 9.0 THEN 1 ELSE 0 END) as high
                FROM vm_package_cves
                GROUP BY hostname
                ORDER BY cve_count DESC
                LIMIT 10
            """)

            # Most common CVEs
            common_cves = await conn.fetch("""
                SELECT
                    cve_id,
                    cvss_score,
                    severity,
                    COUNT(DISTINCT hostname) as affected_vms
                FROM vm_package_cves
                GROUP BY cve_id, cvss_score, severity
                HAVING COUNT(DISTINCT hostname) > 1
                ORDER BY affected_vms DESC, cvss_score DESC
                LIMIT 10
            """)

            # Packages with most CVEs
            vulnerable_packages = await conn.fetch("""
                SELECT
                    package_name,
                    COUNT(DISTINCT cve_id) as cve_count,
                    COUNT(DISTINCT hostname) as affected_vms
                FROM vm_package_cves
                GROUP BY package_name
                ORDER BY cve_count DESC
                LIMIT 10
            """)

            return {
                "report_date": datetime.now().isoformat(),
                "summary": {
                    "total_unique_cves": total_cves,
                    "severity_breakdown": {row['severity']: row['count'] for row in severity_breakdown}
                },
                "most_vulnerable_vms": [dict(row) for row in vulnerable_vms],
                "widespread_cves": [dict(row) for row in common_cves],
                "vulnerable_packages": [dict(row) for row in vulnerable_packages]
            }

    async def get_cve_details(self, cve_id: str) -> Optional[Dict]:
        """Get detailed information about a specific CVE"""

        async with self.db.acquire() as conn:
            cve = await conn.fetchrow(
                "SELECT * FROM cve_database WHERE cve_id = $1",
                cve_id
            )

            if not cve:
                return None

            # Get affected VMs and packages
            affected = await conn.fetch("""
                SELECT hostname, package_name, cvss_score
                FROM vm_package_cves
                WHERE cve_id = $1
                ORDER BY hostname
            """, cve_id)

            return {
                "cve_id": cve['cve_id'],
                "cvss_score": cve['cvss_v3_score'],
                "severity": cve['severity'],
                "description": cve['description'],
                "published_date": cve['published_date'].isoformat() if cve['published_date'] else None,
                "affected_systems": len(affected),
                "affected_details": [dict(row) for row in affected],
                "references": [
                    f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    f"https://cve.mitre.org/cgi-bin/cvename.cgi?name={cve_id}"
                ]
            }


# Helper function for easy access
def create_cve_analyzer(db_pool):
    """Create CVE analyzer instance"""
    return CVEAnalyzer(db_pool)
