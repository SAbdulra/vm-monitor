#!/bin/bash
# Bootstrap Central SSH Key to Zero-Metric VMs
# Uses default id_rsa to add id_rsa_central for metrics collection

DEFAULT_KEY="/root/.ssh/id_rsa"
CENTRAL_KEY_PUB="/root/.ssh/id_rsa_central.pub"

if [ ! -f "$CENTRAL_KEY_PUB" ]; then
    echo "ERROR: Central public key not found"
    exit 1
fi

PUBLIC_KEY=$(cat "$CENTRAL_KEY_PUB")

# VMs with zero metrics that need the key
VMS="mxhdacddb01l mxhdcsrmdb01l mxhdlcddb01l mxhdld1db01l mxhdlimgen01l mxhdmysqldb01l mxhdrd1db01l mxhdscddb01l mxhdsd1db01l mxhdslddb01l mxhdsmddb01l mxhdwebapp100l mxhdwebapp200l mxhpcsrmdb01l mxhqacqdb01l mxhqcsrmdb01l mxhqdocapp50l mxhqlcqdb01l mxhqlq1db01l mxhqrq1db01l mxhqslqdb01l mxhqwebapp100l mxhqwebapp200l mxhtctsdb01l mxhtlcsdb01l mxhtrheltestvm01l mxhtrheltestvm02l mxhtrhelts02l mxhttxsap01l sjcp-metrics01l sjcp-util01l"

FIXED=0
FAILED=0
SKIPPED=0

get_fqdn() {
    local vm=$1
    local fqdn=""

    fqdn=$(grep -w "${vm}" /etc/hosts 2>/dev/null | awk '{print $2}' | head -1)

    if [ -z "$fqdn" ]; then
        if [[ $vm =~ ^mx ]]; then
            if ping -c 1 -W 2 "${vm}.erp.maxim-ic.com" &>/dev/null; then
                fqdn="${vm}.erp.maxim-ic.com"
            elif ping -c 1 -W 2 "${vm}.maxim-ic.com" &>/dev/null; then
                fqdn="${vm}.maxim-ic.com"
            fi
        else
            if ping -c 1 -W 2 "${vm}.ad.analog.com" &>/dev/null; then
                fqdn="${vm}.ad.analog.com"
            fi
        fi
    fi

    echo "$fqdn"
}

echo "=========================================="
echo "Bootstrap Central SSH Key"
echo "=========================================="
echo ""

for vm in $VMS; do
    echo -n "Processing $vm... "

    FQDN=$(get_fqdn "$vm")

    if [ -z "$FQDN" ]; then
        echo "SKIP (unreachable)"
        ((SKIPPED++))
        continue
    fi

    # Use default key to add central key
    RESULT=$(ssh -i "$DEFAULT_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes "$FQDN" "
        mkdir -p ~/.ssh
        chmod 700 ~/.ssh
        touch ~/.ssh/authorized_keys
        chmod 600 ~/.ssh/authorized_keys

        # Check if key already exists
        if grep -qF '$PUBLIC_KEY' ~/.ssh/authorized_keys 2>/dev/null; then
            echo 'already_present'
        else
            echo '$PUBLIC_KEY' >> ~/.ssh/authorized_keys
            echo 'added'
        fi
    " 2>&1)

    if [[ "$RESULT" == "added" ]]; then
        echo "OK (key added)"
        ((FIXED++))
    elif [[ "$RESULT" == "already_present" ]]; then
        echo "OK (already had key)"
        ((FIXED++))
    else
        echo "FAIL"
        ((FAILED++))
    fi
done

echo ""
echo "=========================================="
echo "Summary:"
echo "  Fixed: $FIXED"
echo "  Failed: $FAILED"
echo "  Skipped: $SKIPPED"
echo "=========================================="
echo ""
echo "Wait 5 minutes for metrics collector to gather data"
echo "from newly accessible VMs."
