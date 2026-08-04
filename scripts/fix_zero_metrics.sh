#!/bin/bash
# Fix Zero-Metric VMs - Telegraf Troubleshooting and Repair Script
# This script diagnoses and fixes VMs reporting 0.0 for all metrics

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get list of VMs with zero metrics from API
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}VM Monitor - Zero Metrics Fix Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Monitoring server
MONITOR_SERVER="ashdaimonapp01l.ad.analog.com"
API_URL="http://${MONITOR_SERVER}:8001/api/vms"

echo -e "${YELLOW}Step 1: Fetching VM list from API...${NC}"
VMS_JSON=$(curl -s "${API_URL}")

# Extract VMs with all zeros
echo -e "${YELLOW}Step 2: Identifying VMs with zero metrics...${NC}"
ZERO_VMS=$(echo "$VMS_JSON" | grep -o '"name":"[^"]*","status":"online","cpu_usage":0.0,"memory_usage":0.0,"disk_usage":0.0' | grep -o '"name":"[^"]*"' | cut -d'"' -f4)

# Count
ZERO_COUNT=$(echo "$ZERO_VMS" | wc -l)
echo -e "${RED}Found ${ZERO_COUNT} VMs with zero metrics${NC}"
echo ""

# Save to file
echo "$ZERO_VMS" > /tmp/zero_metric_vms.txt
echo -e "${GREEN}✓ List saved to /tmp/zero_metric_vms.txt${NC}"
echo ""

# Show first 10
echo -e "${YELLOW}First 10 affected VMs:${NC}"
echo "$ZERO_VMS" | head -10
echo ""

# Function to check and fix a single VM
fix_vm() {
    local vm=$1
    local vm_fqdn="${vm}.ad.analog.com"

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Checking: ${vm}${NC}"
    echo -e "${BLUE}========================================${NC}"

    # Test connectivity
    if ! ping -c 1 -W 2 "${vm_fqdn}" &>/dev/null; then
        echo -e "${RED}✗ Cannot ping ${vm_fqdn}${NC}"
        return 1
    fi
    echo -e "${GREEN}✓ VM is reachable${NC}"

    # Check if Telegraf is installed
    if ! ssh -o ConnectTimeout=10 "${vm_fqdn}" "which telegraf" &>/dev/null; then
        echo -e "${RED}✗ Telegraf not installed${NC}"
        echo -e "${YELLOW}Installing Telegraf...${NC}"
        ssh "${vm_fqdn}" "sudo yum install -y telegraf" || {
            echo -e "${RED}✗ Failed to install Telegraf${NC}"
            return 1
        }
    fi
    echo -e "${GREEN}✓ Telegraf is installed${NC}"

    # Check Telegraf status
    local status=$(ssh "${vm_fqdn}" "systemctl is-active telegraf" 2>/dev/null || echo "inactive")
    if [ "$status" != "active" ]; then
        echo -e "${YELLOW}⚠ Telegraf is ${status}${NC}"
        echo -e "${YELLOW}Starting Telegraf...${NC}"
        ssh "${vm_fqdn}" "sudo systemctl start telegraf"
        ssh "${vm_fqdn}" "sudo systemctl enable telegraf"
    else
        echo -e "${GREEN}✓ Telegraf is running${NC}"
    fi

    # Check configuration
    echo -e "${YELLOW}Checking Telegraf configuration...${NC}"
    local has_cpu=$(ssh "${vm_fqdn}" "grep -q '\[\[inputs.cpu\]\]' /etc/telegraf/telegraf.conf && echo yes || echo no")
    local has_mem=$(ssh "${vm_fqdn}" "grep -q '\[\[inputs.mem\]\]' /etc/telegraf/telegraf.conf && echo yes || echo no")
    local has_disk=$(ssh "${vm_fqdn}" "grep -q '\[\[inputs.disk\]\]' /etc/telegraf/telegraf.conf && echo yes || echo no")

    if [ "$has_cpu" != "yes" ] || [ "$has_mem" != "yes" ] || [ "$has_disk" != "yes" ]; then
        echo -e "${RED}✗ Missing input plugins in config${NC}"
        echo -e "  CPU: $has_cpu, Memory: $has_mem, Disk: $has_disk"
        echo -e "${YELLOW}This VM needs configuration update${NC}"
        return 1
    fi
    echo -e "${GREEN}✓ Input plugins configured${NC}"

    # Check if metrics are being collected
    echo -e "${YELLOW}Testing metric collection...${NC}"
    ssh "${vm_fqdn}" "telegraf --test --config /etc/telegraf/telegraf.conf 2>&1 | head -50" > /tmp/${vm}_test.log

    if grep -q "cpu,cpu=cpu-total" /tmp/${vm}_test.log; then
        echo -e "${GREEN}✓ CPU metrics working${NC}"
    else
        echo -e "${RED}✗ CPU metrics not collecting${NC}"
    fi

    if grep -q "mem," /tmp/${vm}_test.log; then
        echo -e "${GREEN}✓ Memory metrics working${NC}"
    else
        echo -e "${RED}✗ Memory metrics not collecting${NC}"
    fi

    # Restart Telegraf
    echo -e "${YELLOW}Restarting Telegraf...${NC}"
    ssh "${vm_fqdn}" "sudo systemctl restart telegraf"
    sleep 2

    # Verify it's running
    status=$(ssh "${vm_fqdn}" "systemctl is-active telegraf" 2>/dev/null || echo "inactive")
    if [ "$status" = "active" ]; then
        echo -e "${GREEN}✓ Telegraf restarted successfully${NC}"
    else
        echo -e "${RED}✗ Telegraf failed to start${NC}"
        ssh "${vm_fqdn}" "sudo journalctl -u telegraf -n 20" | tail -10
        return 1
    fi

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ ${vm} - Fix completed${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""

    return 0
}

# Ask user for action
echo -e "${YELLOW}What would you like to do?${NC}"
echo "1) Check details on one specific VM"
echo "2) Fix all VMs with zero metrics (will take time)"
echo "3) Fix first 10 VMs only (for testing)"
echo "4) Export list and exit"
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        read -p "Enter VM hostname: " test_vm
        fix_vm "$test_vm"
        ;;
    2)
        echo -e "${YELLOW}Fixing all ${ZERO_COUNT} VMs...${NC}"
        echo -e "${RED}This will take approximately $((ZERO_COUNT * 30 / 60)) minutes${NC}"
        read -p "Continue? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            success=0
            failed=0
            for vm in $ZERO_VMS; do
                if fix_vm "$vm"; then
                    ((success++))
                else
                    ((failed++))
                    echo "$vm" >> /tmp/failed_vms.txt
                fi
            done
            echo -e "${GREEN}========================================${NC}"
            echo -e "${GREEN}Summary:${NC}"
            echo -e "${GREEN}  Successful: ${success}${NC}"
            echo -e "${RED}  Failed: ${failed}${NC}"
            if [ $failed -gt 0 ]; then
                echo -e "${RED}  Failed VMs saved to: /tmp/failed_vms.txt${NC}"
            fi
            echo -e "${GREEN}========================================${NC}"
        fi
        ;;
    3)
        echo -e "${YELLOW}Fixing first 10 VMs...${NC}"
        success=0
        failed=0
        for vm in $(echo "$ZERO_VMS" | head -10); do
            if fix_vm "$vm"; then
                ((success++))
            else
                ((failed++))
            fi
        done
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}Test Summary:${NC}"
        echo -e "${GREEN}  Successful: ${success}/10${NC}"
        echo -e "${RED}  Failed: ${failed}/10${NC}"
        echo -e "${GREEN}========================================${NC}"
        ;;
    4)
        echo -e "${GREEN}VM list exported to: /tmp/zero_metric_vms.txt${NC}"
        echo -e "${YELLOW}You can manually fix them later${NC}"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Script completed${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Wait 2-3 minutes for metrics to flow"
echo "2. Check dashboard: http://${MONITOR_SERVER}"
echo "3. Verify VMs no longer show 0.0 metrics"
echo ""
echo -e "${GREEN}Done!${NC}"
