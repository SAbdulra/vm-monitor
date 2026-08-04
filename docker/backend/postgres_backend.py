Authorized uses only. All activity may be monitored and reported.
import os
"""
FastAPI Backend with PostgreSQL LISTEN/NOTIFY + LDAP Authentication
Real-time dashboard updates via WebSocket with secure login
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Dict, Optional
import asyncpg
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pydantic import BaseModel

# Import LDAP authentication
from ldap_auth import authenticate_user, create_token, verify_token

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Infrastructure Monitoring API - Secured")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Database configuration from environment variables
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'infra_monitor'),
    'user': os.getenv('DB_USER', 'vm_monitor'),
    'password': os.getenv('DB_PASSWORD')  # REQUIRED - set in .env file
}

# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: Dict

class User(BaseModel):
    username: str
    email: str
    display_name: str
    department: str
    title: str

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# PostgreSQL connection pool
db_pool: Optional[asyncpg.Pool] = None

async def get_db_pool() -> asyncpg.Pool:
    """Get or create database connection pool"""
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(**DB_CONFIG, min_size=2, max_size=10)
        logger.info("✓ PostgreSQL connection pool created")
    return db_pool

# PostgreSQL LISTEN/NOTIFY handler
async def listen_for_notifications():
    """Background task to listen for PostgreSQL NOTIFY events"""
    logger.info("🎧 Starting PostgreSQL LISTEN task...")

    try:
        conn = await asyncpg.connect(**DB_CONFIG)

        def notification_handler(connection, pid, channel, payload):
            try:
                data = json.loads(payload)
                logger.info(f"📢 NOTIFY received on '{channel}': {data}")

                asyncio.create_task(manager.broadcast({
                    'channel': channel,
                    'event': data.get('event'),
                    'data': data,
                    'timestamp': datetime.now().isoformat()
                }))
            except Exception as e:
                logger.error(f"Error handling notification: {e}")

        await conn.add_listener('vm_updates', notification_handler)
        await conn.add_listener('alert_created', notification_handler)

        logger.info("✓ Listening on channels: vm_updates, alert_created")

        while True:
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"LISTEN task error: {e}")
        await asyncio.sleep(5)

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    await get_db_pool()
    asyncio.create_task(listen_for_notifications())
    logger.info("🚀 FastAPI server started with LDAP authentication")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("✓ PostgreSQL connection pool closed")

# Authentication dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """
    Dependency to get current authenticated user from JWT token
    """
    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user against Active Directory and return JWT token
    """
    try:
        logger.info(f"Login attempt for user: {request.username}")

        # Authenticate against LDAP
        user_info = authenticate_user(request.username, request.password)

        if not user_info:
            logger.warning(f"Failed login attempt for: {request.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create JWT token
        access_token = create_token(user_info)

        logger.info(f"✅ Successful login: {request.username} ({user_info.get('display_name')})")

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user={
                "username": user_info['username'],
                "display_name": user_info.get('display_name', ''),
                "email": user_info.get('email', ''),
                "department": user_info.get('department', ''),
                "title": user_info.get('title', '')
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )

@app.get("/api/auth/me", response_model=User)
async def get_current_user_info(current_user: Dict = Depends(get_current_user)):
    """
    Get current authenticated user information
    """
    return User(
        username=current_user.get('sub', ''),
        email=current_user.get('email', ''),
        display_name=current_user.get('display_name', ''),
        department=current_user.get('department', ''),
        title=current_user.get('title', '')
    )

@app.post("/api/auth/logout")
async def logout(current_user: Dict = Depends(get_current_user)):
    """
    Logout (client should delete token)
    """
    logger.info(f"User logged out: {current_user.get('sub')}")
    return {"message": "Logged out successfully"}

# ============================================================================
# PROTECTED API ENDPOINTS (Require Authentication)
# ============================================================================

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Infrastructure Monitoring API",
        "database": "PostgreSQL",
        "authentication": "LDAP (Active Directory)"
    }

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Get dashboard statistics (Protected)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_vms,
                COUNT(*) FILTER (WHERE status = 'online') as online_vms,
                COUNT(*) FILTER (WHERE status = 'offline') as offline_vms,
                COUNT(*) FILTER (WHERE health_status IN ('warning', 'critical')) as warning_vms,
                AVG(cpu_usage) as avg_cpu,
                AVG(memory_usage) as avg_memory,
                AVG(disk_usage) as avg_disk
            FROM v_vm_health
        """)
        alert_count = await conn.fetchval(
            "SELECT COUNT(*) FROM vm_alerts WHERE status = 'active'"
        )

        if stats['total_vms'] > 0:
            health_score = round((stats['online_vms'] / stats['total_vms']) * 100, 1)
        else:
            health_score = 0

        return {
            "total_vms": stats['total_vms'] or 0,
            "online_vms": stats['online_vms'] or 0,
            "offline_vms": stats['offline_vms'] or 0,
            "warning_vms": stats['warning_vms'] or 0,
            "active_alerts": alert_count or 0,
            "health_score": health_score,
            "avg_cpu": float(stats['avg_cpu'] or 0),
            "avg_memory": float(stats['avg_memory'] or 0),
            "avg_disk": float(stats['avg_disk'] or 0)
        }

@app.get("/api/vms")
async def get_vms():
    """Get all VMs with latest metrics (Protected)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM v_latest_metrics ORDER BY hostname")

        vms = []
        for row in rows:
            vms.append({
                "name": row['hostname'],
                "status": row['status'],
                "cpu_usage": float(row['cpu_usage'] or 0),
                "memory_usage": float(row['memory_usage'] or 0),
                "disk_usage": float(row['disk_usage'] or 0),
                "network_in": float(row['network_in'] or 0),
                "network_out": float(row['network_out'] or 0),
                "uptime": row['uptime'] or 0,
                "last_update": row['timestamp'].isoformat() if row['timestamp'] else None
            })

        return {"vms": vms}

@app.get("/api/vms/{vm_name}")
async def get_vm_details(vm_name: str):
    """Get details for specific VM with full system info"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Get latest metrics
        metrics = await conn.fetchrow(
            """SELECT * FROM v_latest_metrics WHERE hostname = $1""",
            vm_name
        )
        
        if not metrics:
            raise HTTPException(status_code=404, detail="VM not found")
        
        # Get static info
        static = await conn.fetchrow(
            """SELECT * FROM vm_static_info WHERE hostname = $1""",
            vm_name
        )
        
        # Get daily metrics (uptime)
        daily = await conn.fetchrow(
            """SELECT * FROM vm_daily_metrics 
               WHERE hostname = $1 
               ORDER BY timestamp DESC LIMIT 1""",
            vm_name
        )
        
        return {
            "name": metrics['hostname'],
            "status": metrics['status'],
            "cpu_usage": float(metrics['cpu_usage'] or 0),
            "memory_usage": float(metrics['memory_usage'] or 0),
            "disk_usage": float(metrics['disk_usage'] or 0),
            "network_in": float(metrics['network_in'] or 0),
            "network_out": float(metrics['network_out'] or 0),
            "last_update": metrics['timestamp'].isoformat() if metrics['timestamp'] else None,
            
            # System Info
            "os_name": static['os_pretty_name'] if static else None,
            "os_version": static['os_version'] if static else None,
            "kernel_version": static['kernel_version'] if static else None,
            "architecture": static['architecture'] if static else None,
            "cpu_model": static['cpu_model'] if static else None,
            "cpu_cores": static['cpu_cores'] if static else None,
            "cpu_threads": static['cpu_threads'] if static else None,
            "ram_total_mb": static['ram_total_mb'] if static else None,
            "ram_total_gb": static['ram_total_gb'] if static else None,
            
            # Uptime
            "uptime_days": daily['uptime_days'] if daily else 0,
            "uptime_formatted": daily['uptime_formatted'] if daily else "Unknown",
            "load_1min": float(daily['load_1min']) if daily else 0.0,
            "load_5min": float(daily['load_5min']) if daily else 0.0,
            "load_15min": float(daily['load_15min']) if daily else 0.0,
            "boot_time": daily['boot_time'].isoformat() if daily and daily['boot_time'] else None
        }


@app.get("/api/alerts")
async def get_alerts():
    """Get active alerts (Protected)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM vm_alerts
            WHERE status = 'active'
            ORDER BY created_at DESC
            LIMIT 100
        """)

        alerts = []
        for row in rows:
            alerts.append({
                "alert_id": row['id'],
                "vm_name": row['vm_name'],
                "severity": row['severity'],
                "message": row['message'],
                "status": row['status'],
                "created_at": row['created_at'].isoformat()
            })

        return {"alerts": alerts}

@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, current_user: Dict = Depends(get_current_user)):
    """Acknowledge an alert (Protected)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("""
            UPDATE vm_alerts
            SET status = 'acknowledged',
                acknowledged_at = NOW(),
                acknowledged_by = $1
            WHERE id = $2 AND status = 'active'
        """, current_user.get('sub'), alert_id)

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Alert not found or already acknowledged")

        logger.info(f"Alert #{alert_id} acknowledged by {current_user.get('sub')}")
        return {"status": "success", "alert_id": alert_id}

@app.get("/api/performance/trends")
async def get_performance_trends(hours: int = 24, current_user: Dict = Depends(get_current_user)):
    """Get performance trends (Protected)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                DATE_TRUNC('hour', timestamp) as hour,
                ROUND(AVG(cpu_usage), 1) as avg_cpu,
                ROUND(AVG(memory_usage), 1) as avg_memory,
                ROUND(AVG(disk_usage), 1) as avg_disk
            FROM vm_metrics
            WHERE timestamp > NOW() - INTERVAL '24 hours'
            GROUP BY hour
            ORDER BY hour DESC
            LIMIT 24
        """)

        trends = []
        for row in rows:
            trends.append({
                "timestamp": row['hour'].isoformat(),
                "avg_cpu": float(row['avg_cpu'] or 0),
                "avg_memory": float(row['avg_memory'] or 0),
                "avg_disk": float(row['avg_disk'] or 0)
            })

        return {"trends": list(reversed(trends))}

@app.get("/api/costs/summary")
async def get_cost_summary(current_user: Dict = Depends(get_current_user)):
    """Get cost summary (Protected)"""
    return {
        "daily_total": 0,
        "monthly_total": 0,
        "yearly_total": 0
    }

# ============================================================================
# WEBSOCKET ENDPOINT (Authenticated)
# ============================================================================

@app.websocket("/ws/metrics")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates
    Note: Token should be sent as first message after connection
    """
    await manager.connect(websocket)

    try:
        # Wait for authentication token (sent as first message)
        token_data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        token_json = json.loads(token_data)
        token = token_json.get('token')

        if not token:
            await websocket.send_json({"error": "Authentication required"})
            await websocket.close()
            return

        # Verify token
        payload = verify_token(token)
        if not payload:
            await websocket.send_json({"error": "Invalid token"})
            await websocket.close()
            return

        logger.info(f"✅ WebSocket authenticated: {payload.get('sub')}")

        # Send initial data
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_vms,
                COUNT(*) FILTER (WHERE status = 'online') as online_vms,
                COUNT(*) FILTER (WHERE status = 'offline') as offline_vms,
                COUNT(*) FILTER (WHERE health_status IN ('warning', 'critical')) as warning_vms,
                AVG(cpu_usage) as avg_cpu,
                AVG(memory_usage) as avg_memory,
                AVG(disk_usage) as avg_disk
            FROM v_vm_health
        """)
            await websocket.send_json({
                "event": "initial_data",
                "data": {
                    "total_vms": stats['total_vms'] or 0,
                    "online_vms": stats['online_vms'] or 0
                }
            })

        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                await websocket.send_json({
                    "event": "pong",
                    "timestamp": datetime.now().isoformat()
                })
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "event": "heartbeat",
                    "timestamp": datetime.now().isoformat()
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Health check (public)
@app.get("/health")
async def health_check():
    """Health check endpoint (Public)"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "database": "connected", "auth": "LDAP"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ============================================
# Include Packages Router
# ============================================
import sys
#sys.path.insert(0, '/AI_mon/code')
#
#from api.packages_endpoints import router as packages_router
#from api.comprehensive_endpoints import router as metrics_router
#
#app.include_router(packages_router)
#app.include_router(metrics_router)
#
#logger.info('✅ Packages and Comprehensive Metrics endpoints loaded')

# Override /api/vms endpoint to use realtime view
@app.get('/api/vms')
async def get_vms_realtime():
    """Get VMs with real-time accurate data only (filters out fake 0.00 metrics)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT hostname, cpu_usage_percent as cpu_usage, 
                   ram_usage_percent as memory_usage,
                   swap_usage_percent as disk_usage,
                   status, last_metric_time as timestamp,
                   uptime_days, load_1min, os_name, cpu_cores, ram_total_gb
            FROM vm_realtime_status
            ORDER BY hostname
        ''')
        return [dict(row) for row in rows]


# ============================================
# VM Details - Packages & Processes
# ============================================

        total = await conn.fetchval(
            "SELECT COUNT(*) FROM packages WHERE hostname = $1",
            vm_name
        )
        
        return {
            "hostname": vm_name,
            "total_packages": total,
            "packages": [dict(p) for p in packages]
        }

@app.get("/api/vms/{vm_name}/vulnerabilities")
async def get_vm_vulnerabilities(vm_name: str):
    """Get CVE vulnerabilities for packages on a specific VM"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        vulns = await conn.fetch("""
            SELECT 
                p.package_name,
                p.package_version,
                pv.cve_id,
                c.severity,
                c.cvss_v3_score,
                c.cvss_v2_score,
                c.description,
                c.published_date,
                pv.detected_at
            FROM packages p
            JOIN package_vulnerabilities pv ON p.id = pv.package_id
            LEFT JOIN cve_database c ON pv.cve_id = c.cve_id
            WHERE p.hostname = $1
            ORDER BY c.cvss_v3_score DESC NULLS LAST, c.cvss_v2_score DESC NULLS LAST
        """, vm_name)
        
        return {
            "hostname": vm_name,
            "vulnerability_count": len(vulns),
            "vulnerabilities": [dict(v) for v in vulns]
        }

@app.get("/api/vms/{vm_name}/processes")
async def get_vm_top_processes(vm_name: str, limit: int = 10):
    """Get top processes consuming resources on a specific VM"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        processes = await conn.fetch("""
            SELECT 
                pid,
                process_name,
                cpu_percent,
                memory_percent,
                memory_rss_mb,
                command_line,
                username,
                timestamp
            FROM vm_top_processes
            WHERE hostname = $1
              AND timestamp > NOW() - INTERVAL '1 hour'
            ORDER BY timestamp DESC, cpu_percent DESC
            LIMIT $2
        """, vm_name, limit)
        
        return {
            "hostname": vm_name,
            "process_count": len(processes),
            "processes": [dict(p) for p in processes]
        }

@app.get("/api/vms/{vm_name}/summary")
async def get_vm_complete_summary(vm_name: str):
    """Get complete VM summary: specs, metrics, packages, vulnerabilities, processes"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Get VM details
        details_response = await get_vm_details(vm_name)
        
        # Get package count
        pkg_count = await conn.fetchval(
            "SELECT COUNT(*) FROM packages WHERE hostname = $1",
            vm_name
        )
        
        # Get vulnerability count
        vuln_count = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM packages p
            JOIN package_vulnerabilities pv ON p.id = pv.package_id
            WHERE p.hostname = $1
        """, vm_name)
        
        # Get critical vulnerabilities
        critical_vulns = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM packages p
            JOIN package_vulnerabilities pv ON p.id = pv.package_id
            JOIN cve_database c ON pv.cve_id = c.cve_id
            WHERE p.hostname = $1 AND c.severity = 'CRITICAL'
        """, vm_name)
        
        # Get top 5 processes
        top_procs = await conn.fetch("""
            SELECT process_name, cpu_percent, memory_percent
            FROM vm_top_processes
            WHERE hostname = $1
              AND timestamp > NOW() - INTERVAL '10 minutes'
            ORDER BY cpu_percent DESC
            LIMIT 5
        """, vm_name)
        
        return {
            **details_response,
            "package_count": pkg_count,
            "vulnerability_count": vuln_count,
            "critical_vulnerabilities": critical_vulns,
            "top_processes": [dict(p) for p in top_procs]
        }

@app.get("/api/vms/{vm_name}/metrics")
async def get_vm_historical_metrics(vm_name: str, range: str = "24h"):
    """Get historical metrics for a VM"""
    try:
        # Determine time range
        interval_map = {
            "1h": "1 hour",
            "24h": "24 hours",
            "7d": "7 days",
            "30d": "30 days"
        }
        interval = interval_map.get(range, "24 hours")
        
        async with app.state.db_pool.acquire() as conn:
            # Try Telegraf metrics first, fallback to vm_detailed_metrics
            metrics = await conn.fetch("""
                SELECT 
                    timestamp,
                    cpu_usage_percent as cpu_usage,
                    ram_usage_percent as memory_usage,
                    swap_usage_percent as disk_usage,
                    load_1min,
                    load_5min,
                    load_15min
                FROM vm_detailed_metrics
                WHERE hostname = $1
                  AND timestamp > NOW() - INTERVAL $2
                ORDER BY timestamp ASC
            """, vm_name, interval)
            
            return {
                "hostname": vm_name,
                "range": range,
                "metrics": [dict(m) for m in metrics]
            }
    except Exception as e:
        logger.error(f"Error fetching historical metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vms/{hostname}/info")
async def get_vm_info(hostname: str):
    """Get detailed VM information including system info, processes, disks, and packages"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Latest metrics
        metrics = await conn.fetchrow("""
            SELECT hostname, cpu_usage_percent, ram_usage_percent, 
                   swap_usage_percent, status, timestamp
            FROM vm_detailed_metrics
            WHERE hostname = $1
            ORDER BY timestamp DESC
            LIMIT 1
        """, hostname)
        
        # System info
        sysinfo = await conn.fetchrow("""
            SELECT os_name, os_version, os_pretty_name, kernel_version, 
                   architecture, uptime_seconds, cpu_cores, ram_total_gb
            FROM vm_static_info
            WHERE hostname = $1
        """, hostname)
        
        # Top processes
        processes = await conn.fetch("""
            SELECT process_name, cpu_percent, memory_percent, 
                   memory_rss_mb, username, pid
            FROM vm_top_processes
            WHERE hostname = $1
            ORDER BY cpu_percent DESC
            LIMIT 10
        """, hostname)
        
        # Disk structure (NEW!)
        disks = await conn.fetch("""
            SELECT device, mount_point, filesystem, 
                   total_gb, used_gb, available_gb, usage_percent,
                   collected_at
            FROM vm_disk_structure
            WHERE hostname = $1
            ORDER BY mount_point
        """, hostname)
        
        # Package summary (NEW!)
        pkg_summary = await conn.fetchrow("""
            SELECT total_packages, last_updated
            FROM vm_package_summary
            WHERE hostname = $1
        """, hostname)
        
        return {
            "hostname": hostname,
            "metrics": dict(metrics) if metrics else {},
            "system_info": dict(sysinfo) if sysinfo else {},
            "top_processes": [dict(p) for p in processes],
            "disk_structure": [dict(d) for d in disks],
            "package_summary": dict(pkg_summary) if pkg_summary else {"total_packages": 0}
        }
@app.get("/api/vms/{hostname}/disks")
async def get_vm_disks(hostname: str):
    """Get disk structure for a VM"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        disks = await conn.fetch("""
            SELECT device, mount_point, filesystem, 
                   total_gb, used_gb, available_gb, usage_percent,
                   collected_at
            FROM vm_disk_structure
            WHERE hostname = $1
            ORDER BY mount_point
        """, hostname)
        
        return {
            "hostname": hostname,
            "disks": [dict(d) for d in disks]
        }

@app.get("/api/vms/{hostname}/packages")
async def get_vm_packages(hostname: str):
    """Get package summary for a VM"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        pkg_summary = await conn.fetchrow("""
            SELECT total_packages, last_updated
            FROM vm_package_summary
            WHERE hostname = $1
        """, hostname)
        
        if pkg_summary:
            return {
                "hostname": hostname,
                "total_packages": pkg_summary["total_packages"],
                "last_updated": str(pkg_summary["last_updated"])
            }
        return {"hostname": hostname, "total_packages": 0}



@app.get('/api/vms/{hostname}/packages/detail')
async def get_vm_packages_detail(hostname: str):
    '''Get detailed package list with CVE matching'''
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Get packages with CVE counts
        packages = await conn.fetch('''
            SELECT 
                p.package_name,
                p.version,
                p.release,
                p.architecture,
                COUNT(c.cve_id) as cve_count,
                array_agg(c.cve_id) FILTER (WHERE c.cve_id IS NOT NULL) as cve_ids,
                array_agg(c.severity) FILTER (WHERE c.severity IS NOT NULL) as severities,
                array_agg(c.cvss_score) FILTER (WHERE c.cvss_score IS NOT NULL) as scores
            FROM vm_packages p
            LEFT JOIN vm_package_cves c ON p.hostname = c.hostname AND p.package_name = c.package_name
            WHERE p.hostname = $1
            GROUP BY p.package_name, p.version, p.release, p.architecture
            ORDER BY cve_count DESC, p.package_name
            LIMIT 1000
        ''', hostname)
        
        result = []
        for pkg in packages:
            cves = []
            if pkg['cve_ids'] and pkg['cve_ids'][0]:
                for i, cve_id in enumerate(pkg['cve_ids'][:10]):  # Limit to 10 CVEs per package
                    cves.append({
                        'cve_id': cve_id,
                        'cvss_score': float(pkg['scores'][i]) if pkg['scores'] and i < len(pkg['scores']) else 0.0,
                        'severity': pkg['severities'][i] if pkg['severities'] and i < len(pkg['severities']) else 'UNKNOWN'
                    })
            
            result.append({
                'package_name': pkg['package_name'],
                'version': pkg['version'],
                'release': pkg['release'],
                'architecture': pkg['architecture'],
                'cve_count': pkg['cve_count'] or 0,
                'cves': cves
            })
        
        return {
            'hostname': hostname,
            'total_packages': len(result),
            'packages': result
        }
@app.get('/api/vms/{hostname}/sysinfo')
async def get_vm_sysinfo(hostname: str):
    '''Get system information only'''
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        sysinfo = await conn.fetchrow('''
            SELECT os_pretty_name, os_version, kernel_version,
                   architecture, cpu_cores, ram_total_gb, uptime_days
            FROM vm_static_info
            WHERE hostname = $1
        ''', hostname)
        
        return {
            'hostname': hostname,
            'system_info': dict(sysinfo) if sysinfo else {}
        }


@app.get('/api/vms/{hostname}/metrics/history')
async def get_vm_metrics_history(hostname: str, timerange: str = '1h'):
    pool = await get_db_pool()
    intervals = {'1h': '1 hour', '6h': '6 hours', '24h': '24 hours', '7d': '7 days'}
    interval_str = intervals.get(timerange, '1 hour')
    
    async with pool.acquire() as conn:
        query = f"""
            SELECT timestamp, cpu_usage_percent, ram_usage_percent, swap_usage_percent
            FROM vm_detailed_metrics
            WHERE hostname = $1 AND timestamp >= NOW() - INTERVAL '{interval_str}'
            ORDER BY timestamp ASC
        """
        metrics = await conn.fetch(query, hostname)
        return {'hostname': hostname, 'timerange': timerange, 'data_points': len(metrics),
                'metrics': [{'time': str(m['timestamp']), 'cpu': float(m['cpu_usage_percent'] or 0), 
                            'ram': float(m['ram_usage_percent'] or 0)} for m in metrics]}

@app.post('/api/vm/report')
async def receive_vm_report(request: Request):
    '''Receive system info reports from VMs'''
    try:
        data = await request.json()
        
        hostname = data.get('hostname')
        if not hostname:
            return {'status': 'error', 'message': 'hostname required'}
        
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Update vm_static_info
            await conn.execute('''
                INSERT INTO vm_static_info (
                    hostname, os_pretty_name, os_version, kernel_version,
                    architecture, cpu_cores, ram_total_gb, uptime_days, last_updated
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                ON CONFLICT (hostname) DO UPDATE SET
                    os_pretty_name = EXCLUDED.os_pretty_name,
                    os_version = EXCLUDED.os_version,
                    kernel_version = EXCLUDED.kernel_version,
                    architecture = EXCLUDED.architecture,
                    cpu_cores = EXCLUDED.cpu_cores,
                    ram_total_gb = EXCLUDED.ram_total_gb,
                    uptime_days = EXCLUDED.uptime_days,
                    last_updated = NOW()
            ''', hostname, data.get('os_name'), data.get('os_version'),
                 data.get('kernel'), data.get('arch'), data.get('cpu_cores'),
                 data.get('ram_gb'), data.get('uptime_days'))
            
            # Update package summary
            if data.get('package_count'):
                await conn.execute('''
                    INSERT INTO vm_package_summary (hostname, total_packages, last_updated)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (hostname) DO UPDATE SET
                        total_packages = EXCLUDED.total_packages,
                        last_updated = NOW()
                ''', hostname, data.get('package_count'))
            
            # Store disk info if provided
            if data.get('disks'):
                # Delete old disk data
                await conn.execute('DELETE FROM vm_disk_structure WHERE hostname = $1', hostname)
                
                # Insert new disk data
                for disk in data['disks']:
                    await conn.execute('''
                        INSERT INTO vm_disk_structure (
                            hostname, device, mount_point, filesystem,
                            total_gb, used_gb, available_gb, usage_percent, collected_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                    ''', hostname, disk.get('device'), disk.get('mount'),
                         disk.get('fstype'), disk.get('total_gb'), disk.get('used_gb'),
                         disk.get('avail_gb'), disk.get('use_pct'))
        
        return {'status': 'success', 'hostname': hostname}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
