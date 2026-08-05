#!/bin/bash
# Simple script to add central SSH key to VMs

CENTRAL_KEY="/root/.ssh/id_rsa_central.pub"
DEFAULT_KEY="/root/.ssh/id_rsa"

# VMs needing the key
VMS="mxhdcsrmdb01l mxhdlcddb01l mxhdld1db01l mxhdlimgen01l mxhdmysqldb01l mxhdrd1db01l mxhdscddb01l mxhdsd1db01l mxhdsmddb01l mxhdwebapp100l mxhdwebapp200l mxhpcsrmdb01l mxhqacqdb01l mxhqcsrmdb01l mxhqdocapp50l mxhqlcqdb01l mxhqlq1db01l mxhqrq1db01l mxhqwebapp200l mxhtctsdb01l mxhtlcsdb01l mxhtrheltestvm01l mxhtrheltestvm02l mxhtrhelts02l mxhttxsap01l sjcp-metrics01l sjcp-util01l"

FIXED=0
FAILED=0

get_fqdn() {
    local vm=$1
    grep -w "${vm}" /etc/hosts 2>/dev/null | awk '{print $2}' | head -1 || {
        if [[ $vm =~ ^mx ]]; then
            ping -c 1 -W 2 "${vm}.erp.maxim-ic.com" &>/dev/null && echo "${vm}.erp.maxim-ic.com" ||
            ping -c 1 -W 2 "${vm}.maxim-ic.com" &>/dev/null && echo "${vm}.maxim-ic.com"
        else
            ping -c 1 -W 2 "${vm}.ad.analog.com" &>/dev/null && echo "${vm}.ad.analog.com"
        fi
    }
}

echo "Adding central SSH key to VMs..."
echo ""

for vm in $VMS; do
    echo -n "$vm... "

    FQDN=$(get_fqdn "$vm")

    if [ -z "$FQDN" ]; then
        echo "SKIP"
        continue
    fi

    # Pipe the key directly
    if cat "$CENTRAL_KEY" | ssh -i "$DEFAULT_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes "$FQDN" 'cat >> ~/.ssh/authorized_keys' 2>/dev/null; then
        echo "OK"
        ((FIXED++))
    else
        echo "FAIL"
        ((FAILED++))
    fi
done

echo ""
echo "Fixed: $FIXED, Failed: $FAILED"
