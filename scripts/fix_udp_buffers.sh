#!/bin/bash

# Script to fix UDP buffer sizes for Cloudflare Tunnel
# This addresses the warning: "failed to sufficiently increase receive buffer size"

set -e

echo "=== Fixing UDP Buffer Sizes for Cloudflare Tunnel ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "This script needs to be run with sudo to modify system settings"
    echo "Please run: sudo $0"
    exit 1
fi

# Set UDP buffer sizes
echo "Setting UDP buffer sizes..."
sysctl -w net.core.rmem_max=8388608
sysctl -w net.core.rmem_default=8388608
sysctl -w net.core.rmem_min=8388608

# Make it persistent by adding to /etc/sysctl.conf
echo ""
echo "Making changes persistent..."

# Remove old entries if they exist
sed -i '/^net\.core\.rmem_max=/d' /etc/sysctl.conf
sed -i '/^net\.core\.rmem_default=/d' /etc/sysctl.conf
sed -i '/^net\.core\.rmem_min=/d' /etc/sysctl.conf

# Add new entries
cat >> /etc/sysctl.conf <<EOF

# Cloudflare Tunnel UDP buffer settings
net.core.rmem_max=8388608
net.core.rmem_default=8388608
net.core.rmem_min=8388608
EOF

echo "✓ UDP buffer sizes set to 8MB"
echo "✓ Changes made persistent in /etc/sysctl.conf"
echo ""
echo "Current values:"
sysctl net.core.rmem_max net.core.rmem_default net.core.rmem_min
echo ""
echo "You may want to restart the cloudflared container:"
echo "  cd /home/jdehart/Working/ndaTool && docker compose restart cloudflared"

