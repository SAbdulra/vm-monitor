# Multi-Platform Monitoring Expansion Plan

**Date:** 2026-08-05  
**Sponsor:** Infrastructure Team  
**Scope:** Extend VM Monitor to support Windows, Cloud Linux, vCenter, and NetApp

---

## 🎯 Expansion Goals

### Current State
- **Platform:** Linux on-premise VMs only
- **Count:** 133 VMs
- **Collection Method:** SSH-based pull
- **Coverage:** 85%

### Target State
- **Platforms:** 
  - ✅ Linux on-premise (current)
  - 🆕 Cloud Linux (AWS, Azure, GCP)
  - 🆕 Windows on-premise
  - 🆕 Windows cloud
  - 🆕 VMware vCenter
  - 🆕 NetApp storage systems

### Business Drivers
- **Complete visibility** across all infrastructure
- **Unified monitoring** - single pane of glass
- **Cloud migration readiness** - monitor hybrid environments
- **Storage monitoring** - NetApp capacity and performance
- **Windows support** - complete enterprise coverage

---

## 🏗️ Architecture Design

### Multi-Platform Collection Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    VM Monitor Platform                          │
│                  (Multi-Platform Collector)                      │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┬─────────────────┐
        ▼                   ▼                   ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐
│ Linux VMs    │  │ Windows VMs  │  │   vCenter    │  │   NetApp    │
│ (SSH)        │  │ (WinRM/SSH)  │  │   (API)      │  │   (API)     │
└──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘
    │                   │                  │                 │
    ▼                   ▼                  ▼                 ▼
┌────────────────────────────────────────────────────────────────┐
│              Unified PostgreSQL Database                        │
│  - platform_type column (linux, windows, vmware, netapp)       │
│  - platform_metrics table (platform-specific data)             │
│  - unified_metrics view (normalized across platforms)          │
└────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                  Enhanced Dashboard                             │
│  - Platform filter (Linux/Windows/vCenter/NetApp)              │
│  - Platform-specific views                                     │
│  - Unified search across all platforms                         │
└────────────────────────────────────────────────────────────────┘
```

---

## 📋 Platform-Specific Implementation

### 1. Cloud Linux (AWS, Azure, GCP)

**Collection Methods:**

**Option A: Agent-Based (Recommended)**
```python
# Deploy lightweight agent on cloud VMs
# Agent collects metrics and pushes to central endpoint

class CloudLinuxCollector:
    def __init__(self, cloud_provider):
        self.provider = cloud_provider  # 'aws', 'azure', 'gcp'
        self.agent_endpoint = "https://monitor.company.com/api/metrics"
    
    async def collect_metrics(self):
        """Collect standard Linux metrics + cloud metadata"""
        metrics = await self.get_linux_metrics()
        cloud_meta = await self.get_cloud_metadata()
        
        return {
            **metrics,
            'cloud_provider': self.provider,
            'instance_id': cloud_meta['instance_id'],
            'region': cloud_meta['region'],
            'instance_type': cloud_meta['instance_type'],
            'vpc_id': cloud_meta.get('vpc_id'),
            'availability_zone': cloud_meta['az']
        }
```

**Option B: Cloud API-Based**
```python
# Use cloud provider APIs (AWS CloudWatch, Azure Monitor, GCP Monitoring)

class AWSCloudWatchCollector:
    async def collect_ec2_metrics(self, instance_id):
        """Collect from CloudWatch API"""
        metrics = await cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            Statistics=['Average'],
            Period=300
        )
        return metrics
```

**Recommendation:** **Hybrid Approach**
- Agent-based for detailed OS metrics
- Cloud API for cloud-specific metadata and billing
- Best of both worlds

**Database Schema:**
```sql
CREATE TABLE cloud_vm_metadata (
    hostname VARCHAR(255) PRIMARY KEY,
    cloud_provider VARCHAR(50),  -- 'aws', 'azure', 'gcp'
    instance_id VARCHAR(255),
    region VARCHAR(100),
    instance_type VARCHAR(100),
    vpc_id VARCHAR(100),
    availability_zone VARCHAR(100),
    public_ip INET,
    private_ip INET,
    tags JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

### 2. Windows Systems (On-Premise & Cloud)

**Collection Methods:**

**Option A: WinRM (Windows Remote Management)**
```python
class WindowsCollector:
    def __init__(self, hostname, username, password):
        self.session = winrm.Session(
            hostname, 
            auth=(username, password),
            transport='ntlm'
        )
    
    async def collect_metrics(self):
        """Collect Windows performance counters"""
        
        # CPU Usage
        cpu_cmd = """
        Get-Counter '\\Processor(_Total)\\% Processor Time' | 
        Select-Object -ExpandProperty CounterSamples | 
        Select-Object -ExpandProperty CookedValue
        """
        
        # Memory
        memory_cmd = """
        $os = Get-WmiObject Win32_OperatingSystem
        $total = $os.TotalVisibleMemorySize / 1MB
        $free = $os.FreePhysicalMemory / 1MB
        $used = $total - $free
        $percent = ($used / $total) * 100
        Write-Output "$percent"
        """
        
        # Disk
        disk_cmd = """
        Get-WmiObject Win32_LogicalDisk | 
        Where-Object {$_.DriveType -eq 3} | 
        Select-Object DeviceID, 
            @{n='UsedSpace';e={($_.Size - $_.FreeSpace) / 1GB}},
            @{n='PercentUsed';e={
                (($_.Size - $_.FreeSpace) / $_.Size) * 100
            }}
        """
        
        cpu = await self.run_ps(cpu_cmd)
        memory = await self.run_ps(memory_cmd)
        disks = await self.run_ps(disk_cmd)
        
        return {
            'cpu_usage': float(cpu.strip()),
            'memory_usage': float(memory.strip()),
            'disks': self.parse_disk_output(disks)
        }
```

**Option B: SSH (Windows 10+/Server 2019+)**
```python
# Windows now supports OpenSSH natively
# Same SSH approach as Linux, but use PowerShell commands

class WindowsSSHCollector:
    async def collect_via_ssh(self, hostname):
        async with asyncssh.connect(hostname) as conn:
            # Run PowerShell commands via SSH
            cpu = await conn.run('powershell -c "...')
```

**Option C: Agent (Telegraf, Prometheus Exporter)**
```toml
# Telegraf agent on Windows
[[inputs.win_perf_counters]]
  [[inputs.win_perf_counters.object]]
    ObjectName = "Processor"
    Instances = ["_Total"]
    Counters = ["% Processor Time"]
    
  [[inputs.win_perf_counters.object]]
    ObjectName = "Memory"
    Counters = ["Available MBytes", "% Committed Bytes In Use"]
    
  [[inputs.win_perf_counters.object]]
    ObjectName = "LogicalDisk"
    Instances = ["*"]
    Counters = ["% Free Space"]

[[outputs.http]]
  url = "http://monitor.company.com:8000/api/windows/metrics"
  method = "POST"
  data_format = "json"
```

**Recommendation:** **WinRM for on-premise, Agent for cloud**
- WinRM: Enterprise standard, works everywhere
- Agent: Better for cloud, handles firewalls
- SSH: Fallback for modern Windows versions

**Windows-Specific Metrics:**
```sql
CREATE TABLE windows_metrics (
    hostname VARCHAR(255),
    timestamp TIMESTAMP DEFAULT NOW(),
    
    -- Standard metrics
    cpu_usage DECIMAL(5,2),
    memory_usage DECIMAL(5,2),
    disk_usage DECIMAL(5,2),
    
    -- Windows-specific
    windows_version VARCHAR(100),
    build_number VARCHAR(50),
    uptime_seconds BIGINT,
    
    -- Services
    services_total INT,
    services_running INT,
    services_stopped INT,
    
    -- Performance
    page_faults_per_sec INT,
    context_switches_per_sec INT,
    
    -- Events
    event_errors_24h INT,
    event_warnings_24h INT,
    
    PRIMARY KEY (hostname, timestamp)
);
```

---

### 3. VMware vCenter

**Collection Method: vCenter API (pyVmomi)**

```python
from pyVim.connect import SmartConnect
from pyVmomi import vim

class VCenterCollector:
    def __init__(self, vcenter_host, username, password):
        self.si = SmartConnect(
            host=vcenter_host,
            user=username,
            pwd=password,
            port=443
        )
        self.content = self.si.RetrieveContent()
    
    async def collect_all_vms(self):
        """Collect metrics for all VMs in vCenter"""
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, 
            [vim.VirtualMachine], 
            True
        )
        
        vms_data = []
        for vm in container.view:
            if vm.runtime.powerState != "poweredOn":
                continue
                
            metrics = {
                'hostname': vm.name,
                'platform': 'vmware',
                'power_state': vm.runtime.powerState,
                'guest_os': vm.config.guestFullName,
                
                # Resources
                'cpu_count': vm.config.hardware.numCPU,
                'memory_mb': vm.config.hardware.memoryMB,
                'cpu_usage': vm.summary.quickStats.overallCpuUsage,
                'memory_usage_mb': vm.summary.quickStats.guestMemoryUsage,
                'memory_usage_percent': (
                    vm.summary.quickStats.guestMemoryUsage / 
                    vm.config.hardware.memoryMB * 100
                ),
                
                # Storage
                'storage_committed_gb': (
                    vm.summary.storage.committed / 1024**3
                ),
                'storage_uncommitted_gb': (
                    vm.summary.storage.uncommitted / 1024**3
                ),
                
                # Network
                'ip_address': vm.guest.ipAddress,
                'tools_status': vm.guest.toolsRunningStatus,
                'tools_version': vm.guest.toolsVersion,
                
                # Host
                'esxi_host': vm.runtime.host.name,
                'cluster': vm.runtime.host.parent.name,
                'datastore': [ds.name for ds in vm.datastore],
                
                # Snapshots
                'has_snapshots': vm.snapshot is not None,
                'snapshot_count': (
                    len(vm.snapshot.rootSnapshotList) 
                    if vm.snapshot else 0
                )
            }
            vms_data.append(metrics)
        
        return vms_data
    
    async def collect_esxi_hosts(self):
        """Collect ESXi host metrics"""
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder,
            [vim.HostSystem],
            True
        )
        
        hosts_data = []
        for host in container.view:
            metrics = {
                'hostname': host.name,
                'platform': 'esxi',
                
                # Hardware
                'cpu_model': host.hardware.cpuInfo.name,
                'cpu_cores': host.hardware.cpuInfo.numCpuCores,
                'cpu_threads': host.hardware.cpuInfo.numCpuThreads,
                'cpu_mhz': host.hardware.cpuInfo.hz / 1_000_000,
                'memory_gb': host.hardware.memorySize / 1024**3,
                
                # Usage
                'cpu_usage_mhz': host.summary.quickStats.overallCpuUsage,
                'memory_usage_mb': host.summary.quickStats.overallMemoryUsage,
                'cpu_usage_percent': (
                    host.summary.quickStats.overallCpuUsage / 
                    (host.hardware.cpuInfo.hz / 1_000_000 * 
                     host.hardware.cpuInfo.numCpuCores) * 100
                ),
                
                # VMs
                'vm_count': len(host.vm),
                'vm_running': sum(
                    1 for vm in host.vm 
                    if vm.runtime.powerState == 'poweredOn'
                ),
                
                # Status
                'connection_state': host.runtime.connectionState,
                'maintenance_mode': host.runtime.inMaintenanceMode,
                'uptime_seconds': host.summary.quickStats.uptime
            }
            hosts_data.append(metrics)
        
        return hosts_data
```

**Database Schema:**
```sql
CREATE TABLE vcenter_vms (
    vm_id VARCHAR(255) PRIMARY KEY,
    vm_name VARCHAR(255),
    vcenter_instance VARCHAR(255),
    
    -- Config
    guest_os VARCHAR(255),
    cpu_count INT,
    memory_mb INT,
    
    -- Metrics
    cpu_usage_mhz INT,
    memory_usage_mb INT,
    storage_committed_gb DECIMAL(10,2),
    
    -- Location
    esxi_host VARCHAR(255),
    cluster VARCHAR(255),
    datacenter VARCHAR(255),
    datastores TEXT[],
    
    -- State
    power_state VARCHAR(50),
    tools_status VARCHAR(50),
    has_snapshots BOOLEAN,
    snapshot_count INT,
    
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE vcenter_hosts (
    host_id VARCHAR(255) PRIMARY KEY,
    host_name VARCHAR(255),
    vcenter_instance VARCHAR(255),
    
    -- Hardware
    cpu_model VARCHAR(255),
    cpu_cores INT,
    cpu_threads INT,
    cpu_mhz INT,
    memory_gb INT,
    
    -- Metrics
    cpu_usage_percent DECIMAL(5,2),
    memory_usage_percent DECIMAL(5,2),
    
    -- VMs
    vm_count INT,
    vm_running INT,
    
    -- Status
    connection_state VARCHAR(50),
    maintenance_mode BOOLEAN,
    uptime_seconds BIGINT,
    
    timestamp TIMESTAMP DEFAULT NOW()
);
```

---

### 4. NetApp Storage Systems

**Collection Method: NetApp ONTAP REST API**

```python
import requests
from requests.auth import HTTPBasicAuth

class NetAppCollector:
    def __init__(self, cluster_mgmt_ip, username, password):
        self.base_url = f"https://{cluster_mgmt_ip}/api"
        self.auth = HTTPBasicAuth(username, password)
        self.headers = {'Accept': 'application/json'}
    
    async def collect_cluster_info(self):
        """Collect NetApp cluster overview"""
        response = requests.get(
            f"{self.base_url}/cluster",
            auth=self.auth,
            headers=self.headers,
            verify=False
        )
        return response.json()
    
    async def collect_storage_metrics(self):
        """Collect storage capacity and performance"""
        
        # Aggregates (storage pools)
        aggrs = requests.get(
            f"{self.base_url}/storage/aggregates",
            auth=self.auth,
            headers=self.headers,
            verify=False
        ).json()
        
        # Volumes
        volumes = requests.get(
            f"{self.base_url}/storage/volumes",
            auth=self.auth,
            headers=self.headers,
            params={'fields': 'space,state,type'},
            verify=False
        ).json()
        
        # Performance
        perf = requests.get(
            f"{self.base_url}/cluster/counter/tables/system:node",
            auth=self.auth,
            headers=self.headers,
            verify=False
        ).json()
        
        metrics = {
            'aggregates': [],
            'volumes': [],
            'performance': {}
        }
        
        # Process aggregates
        for aggr in aggrs.get('records', []):
            metrics['aggregates'].append({
                'name': aggr['name'],
                'total_gb': aggr['space']['block_storage']['size'] / 1024**3,
                'used_gb': aggr['space']['block_storage']['used'] / 1024**3,
                'available_gb': aggr['space']['block_storage']['available'] / 1024**3,
                'usage_percent': (
                    aggr['space']['block_storage']['used'] / 
                    aggr['space']['block_storage']['size'] * 100
                ),
                'state': aggr['state']
            })
        
        # Process volumes
        for vol in volumes.get('records', []):
            metrics['volumes'].append({
                'name': vol['name'],
                'svm': vol.get('svm', {}).get('name'),
                'total_gb': vol['space']['size'] / 1024**3,
                'used_gb': vol['space']['used'] / 1024**3,
                'available_gb': vol['space']['available'] / 1024**3,
                'usage_percent': (
                    vol['space']['used'] / vol['space']['size'] * 100
                ),
                'state': vol['state'],
                'type': vol['type']
            })
        
        return metrics
    
    async def collect_node_metrics(self):
        """Collect per-node metrics"""
        nodes = requests.get(
            f"{self.base_url}/cluster/nodes",
            auth=self.auth,
            headers=self.headers,
            params={'fields': 'statistics,uptime,model,version'},
            verify=False
        ).json()
        
        metrics = []
        for node in nodes.get('records', []):
            metrics.append({
                'name': node['name'],
                'model': node.get('model'),
                'version': node.get('version', {}).get('full'),
                'uptime_seconds': node.get('uptime'),
                
                # Statistics
                'cpu_busy_percent': node.get('statistics', {}).get('processor_utilization_raw', 0),
                'avg_latency_ms': node.get('statistics', {}).get('latency_raw', 0) / 1000,
                'iops': node.get('statistics', {}).get('iops_raw', 0),
                'throughput_mbps': node.get('statistics', {}).get('throughput_raw', 0) / 1024**2,
                
                'state': node.get('state')
            })
        
        return metrics
```

**Database Schema:**
```sql
CREATE TABLE netapp_clusters (
    cluster_id VARCHAR(255) PRIMARY KEY,
    cluster_name VARCHAR(255),
    mgmt_ip INET,
    ontap_version VARCHAR(100),
    node_count INT,
    
    -- Capacity
    total_capacity_tb DECIMAL(10,2),
    used_capacity_tb DECIMAL(10,2),
    available_capacity_tb DECIMAL(10,2),
    usage_percent DECIMAL(5,2),
    
    -- Performance
    total_iops INT,
    total_throughput_gbps DECIMAL(10,2),
    avg_latency_ms DECIMAL(10,2),
    
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE netapp_aggregates (
    aggregate_id VARCHAR(255) PRIMARY KEY,
    cluster_id VARCHAR(255) REFERENCES netapp_clusters(cluster_id),
    name VARCHAR(255),
    node_name VARCHAR(255),
    
    -- Capacity
    total_gb DECIMAL(10,2),
    used_gb DECIMAL(10,2),
    available_gb DECIMAL(10,2),
    usage_percent DECIMAL(5,2),
    
    -- Config
    raid_type VARCHAR(50),
    disk_count INT,
    state VARCHAR(50),
    
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE netapp_volumes (
    volume_id VARCHAR(255) PRIMARY KEY,
    cluster_id VARCHAR(255) REFERENCES netapp_clusters(cluster_id),
    name VARCHAR(255),
    svm VARCHAR(255),
    aggregate VARCHAR(255),
    
    -- Capacity
    total_gb DECIMAL(10,2),
    used_gb DECIMAL(10,2),
    available_gb DECIMAL(10,2),
    usage_percent DECIMAL(5,2),
    
    -- Config
    volume_type VARCHAR(50),
    state VARCHAR(50),
    junction_path TEXT,
    
    -- Snapshot
    snapshot_policy VARCHAR(100),
    snapshot_used_gb DECIMAL(10,2),
    
    timestamp TIMESTAMP DEFAULT NOW()
);
```

---

## 🗄️ Unified Data Model

### Platform Abstraction Layer

```sql
-- Unified platform table
CREATE TABLE monitored_platforms (
    platform_id VARCHAR(255) PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL,
    platform_type VARCHAR(50) NOT NULL,  -- 'linux', 'windows', 'vmware', 'netapp'
    environment VARCHAR(50),  -- 'on-premise', 'aws', 'azure', 'gcp'
    
    -- Discovery
    discovered_at TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP,
    status VARCHAR(50),  -- 'online', 'offline', 'unreachable'
    
    -- Location
    datacenter VARCHAR(100),
    rack VARCHAR(100),
    region VARCHAR(100),
    availability_zone VARCHAR(100),
    
    -- Tags
    tags JSONB,
    owner VARCHAR(255),
    application VARCHAR(255),
    environment_tier VARCHAR(50),  -- 'production', 'staging', 'dev'
    
    UNIQUE(hostname, platform_type)
);

-- Unified metrics view
CREATE OR REPLACE VIEW v_unified_metrics AS
-- Linux VMs
SELECT 
    hostname,
    'linux' as platform_type,
    cpu_usage as cpu_percent,
    memory_usage as memory_percent,
    disk_usage as disk_percent,
    uptime_seconds,
    timestamp,
    'on-premise' as environment
FROM v_latest_metrics_enhanced

UNION ALL

-- Windows VMs
SELECT 
    hostname,
    'windows' as platform_type,
    cpu_usage as cpu_percent,
    memory_usage as memory_percent,
    disk_usage as disk_percent,
    uptime_seconds,
    timestamp,
    CASE 
        WHEN tags->>'cloud_provider' IS NOT NULL THEN tags->>'cloud_provider'
        ELSE 'on-premise'
    END as environment
FROM windows_metrics
WHERE timestamp > NOW() - INTERVAL '30 minutes'

UNION ALL

-- VMware VMs
SELECT 
    vm_name as hostname,
    'vmware' as platform_type,
    (cpu_usage_mhz::float / (cpu_count * 2000) * 100) as cpu_percent,
    (memory_usage_mb::float / memory_mb * 100) as memory_percent,
    (storage_committed_gb::float / 
        (storage_committed_gb + storage_uncommitted_gb) * 100
    ) as disk_percent,
    NULL as uptime_seconds,
    timestamp,
    'vmware' as environment
FROM vcenter_vms
WHERE power_state = 'poweredOn'

UNION ALL

-- NetApp Nodes
SELECT 
    name as hostname,
    'netapp' as platform_type,
    cpu_busy_percent as cpu_percent,
    NULL as memory_percent,
    NULL as disk_percent,
    uptime_seconds,
    timestamp,
    'on-premise' as environment
FROM netapp_nodes;
```

---

## 📊 Enhanced Dashboard Design

### Platform Selector

```javascript
// Dashboard enhancement - platform filter
const PlatformFilter = () => {
    const [selectedPlatforms, setSelectedPlatforms] = useState([
        'linux', 'windows', 'vmware', 'netapp'
    ]);
    
    const platformCounts = {
        linux: 133,
        windows: 0,  // To be added
        vmware: 0,   // To be added
        netapp: 0    // To be added
    };
    
    return (
        <div className="platform-filter">
            {Object.entries(platformCounts).map(([platform, count]) => (
                <PlatformChip 
                    key={platform}
                    platform={platform}
                    count={count}
                    selected={selectedPlatforms.includes(platform)}
                    onToggle={() => togglePlatform(platform)}
                />
            ))}
        </div>
    );
};
```

### Platform-Specific Views

```javascript
// VMware-specific dashboard view
const VMwareView = () => {
    return (
        <div className="vmware-dashboard">
            <MetricCard title="vCenter Clusters" value={clusters.length} />
            <MetricCard title="ESXi Hosts" value={hosts.length} />
            <MetricCard title="Total VMs" value={vms.length} />
            <MetricCard title="VMs with Snapshots" value={snapshotCount} />
            
            <ClusterList clusters={clusters} />
            <ResourcePools pools={pools} />
            <DatastoreUtilization datastores={datastores} />
        </div>
    );
};

// NetApp-specific dashboard view
const NetAppView = () => {
    return (
        <div className="netapp-dashboard">
            <MetricCard title="Total Capacity" value={`${totalTB} TB`} />
            <MetricCard title="Used" value={`${usedPercent}%`} />
            <MetricCard title="IOPS" value={totalIOPS} />
            <MetricCard title="Latency" value={`${avgLatency} ms`} />
            
            <AggregateList aggregates={aggregates} />
            <VolumeList volumes={volumes} />
            <PerformanceCharts />
        </div>
    );
};
```

---

## 🚀 Implementation Phases

### Phase 1: Foundation (2 weeks)
**Goal:** Prepare architecture for multi-platform support

**Tasks:**
1. ✅ Create `monitored_platforms` table
2. ✅ Create `v_unified_metrics` view
3. ✅ Add platform_type field to all existing tables
4. ✅ Update API to support platform filtering
5. ✅ Add platform selector to dashboard

**Deliverables:**
- Multi-platform database schema
- Platform-agnostic API endpoints
- Dashboard platform filter

---

### Phase 2: Windows Support (3 weeks)
**Goal:** Add Windows monitoring capability

**Tasks:**
1. ✅ Implement WinRM collector
2. ✅ Create Windows metrics tables
3. ✅ Deploy to pilot Windows servers (5-10 servers)
4. ✅ Test and refine
5. ✅ Roll out to all Windows servers
6. ✅ Add Windows-specific dashboard views

**Technical Decisions:**
- **Collection:** WinRM for on-premise, Telegraf agent for cloud
- **Metrics:** CPU, Memory, Disk, Services, Event Logs
- **Frequency:** Every 5 minutes (match Linux)

---

### Phase 3: Cloud Linux (3 weeks)
**Goal:** Extend to AWS/Azure/GCP Linux instances

**Tasks:**
1. ✅ Implement cloud metadata collection
2. ✅ Deploy Telegraf agents to cloud VMs
3. ✅ Or: Set up cloud API integration (CloudWatch, Azure Monitor)
4. ✅ Create cloud-specific metrics tables
5. ✅ Add cloud provider tags and metadata
6. ✅ Test cross-cloud search and filtering

**Cloud-Specific Features:**
- Cost allocation tags
- Instance type tracking
- Region/AZ distribution
- Auto-scaling group membership

---

### Phase 4: VMware vCenter (4 weeks)
**Goal:** Monitor VMware infrastructure

**Tasks:**
1. ✅ Implement vCenter API collector
2. ✅ Create vCenter database schema
3. ✅ Collect VM, Host, and Cluster metrics
4. ✅ Track snapshots and storage
5. ✅ Build vCenter-specific dashboard
6. ✅ Add capacity planning views

**vCenter-Specific Features:**
- Cluster resource pools
- vMotion history
- Snapshot management
- Datastore capacity trends
- Host maintenance scheduling

---

### Phase 5: NetApp Storage (3 weeks)
**Goal:** Monitor NetApp storage systems

**Tasks:**
1. ✅ Implement NetApp ONTAP API collector
2. ✅ Create NetApp database schema
3. ✅ Collect cluster, aggregate, volume metrics
4. ✅ Track IOPS and latency
5. ✅ Build storage-specific dashboard
6. ✅ Add capacity forecasting

**NetApp-Specific Features:**
- Volume growth trends
- Snapshot reserve tracking
- Deduplication/compression ratios
- Thin provisioning monitoring
- Tier migration suggestions

---

## 💻 Development Effort Estimate

| Phase | Duration | Effort (Hours) | Priority |
|-------|----------|----------------|----------|
| **Phase 1: Foundation** | 2 weeks | 40 hours | Critical |
| **Phase 2: Windows** | 3 weeks | 80 hours | High |
| **Phase 3: Cloud Linux** | 3 weeks | 60 hours | High |
| **Phase 4: vCenter** | 4 weeks | 100 hours | Medium |
| **Phase 5: NetApp** | 3 weeks | 60 hours | Medium |
| **Total** | **15 weeks** | **340 hours** | - |

**Team Size Recommendation:** 2 developers  
**Timeline:** 15 weeks (3.75 months) with 2 developers  
**Or:** 7.5 weeks with 4 developers

---

## 🔐 Security Considerations

### Credentials Management

```python
# Use secrets management system
from azure.keyvault.secrets import SecretClient

class CredentialManager:
    def get_windows_creds(self, hostname):
        return self.vault.get_secret(f"windows-{hostname}")
    
    def get_vcenter_creds(self, vcenter_name):
        return self.vault.get_secret(f"vcenter-{vcenter_name}")
    
    def get_netapp_creds(self, cluster_name):
        return self.vault.get_secret(f"netapp-{cluster_name}")
```

### Best Practices
1. **Never store passwords in code or database**
2. **Use service accounts with minimal permissions**
3. **Rotate credentials regularly (every 90 days)**
4. **Audit all access attempts**
5. **Encrypt credentials at rest and in transit**
6. **Use certificate-based auth where possible**

---

## 📋 Prerequisites & Dependencies

### Required Access
- [ ] Windows servers: WinRM enabled, service account created
- [ ] vCenter: Read-only API user account
- [ ] NetApp: Read-only cluster admin account
- [ ] Cloud: IAM roles with CloudWatch/Monitor read access
- [ ] Network: Firewall rules for WinRM (5985/5986), vCenter API (443), NetApp API (443)

### Software Requirements
- [ ] Python packages: `pywinrm`, `pyvmomi`, `netapp-ontap`, `boto3`, `azure-mgmt-monitor`, `google-cloud-monitoring`
- [ ] Telegraf agents: Build/package for Windows
- [ ] PostgreSQL: Additional 50GB storage for multi-platform data
- [ ] Dashboard: React components for new platform views

---

## 🎯 Success Criteria

Multi-platform expansion will be successful when:

- [ ] All 4 platform types integrated (Linux, Windows, vCenter, NetApp)
- [ ] >80% of each platform type monitored
- [ ] Unified dashboard shows all platforms
- [ ] Search works across all platforms
- [ ] Platform-specific views functional
- [ ] Performance metrics < 30s refresh
- [ ] No credential exposure
- [ ] Documentation complete
- [ ] Team trained on new platforms

---

## 📈 Expected Outcomes

### Metrics Growth
| Metric | Current | After Expansion | Growth |
|--------|---------|-----------------|--------|
| **Monitored Systems** | 133 | ~500-1000 | 4-8x |
| **Platforms** | 1 | 4 | 4x |
| **Data Points/Min** | ~800 | ~4000 | 5x |
| **Dashboard Users** | Limited | All IT staff | 10x |

### Business Value
- **Complete visibility** - No infrastructure blind spots
- **Hybrid cloud ready** - Monitor on-prem + cloud seamlessly
- **Storage optimization** - NetApp capacity planning
- **Cost allocation** - Cloud tagging and tracking
- **Faster troubleshooting** - Single pane of glass

---

## 📞 Next Steps

### Immediate (This Week)
1. **Review this plan** with infrastructure team
2. **Get approval** for multi-platform expansion
3. **Secure credentials** for pilot systems
4. **Set up test environment** (1 Windows VM, 1 vCenter, 1 NetApp)

### Short Term (Next 2 Weeks)
1. **Start Phase 1** - Foundation work
2. **Pilot Windows collection** on 5 servers
3. **Document findings** and refine approach

### Long Term (Next Quarter)
1. **Execute all 5 phases** (15 weeks)
2. **Roll out to production** incrementally
3. **Train team** on multi-platform monitoring

---

**Ready to begin multi-platform expansion!**

Would you like to:
1. Start with Phase 1 (Foundation) implementation?
2. Set up a pilot for one specific platform (Windows/vCenter/NetApp)?
3. Review and refine the technical approach?
