#!/bin/bash

# Quick script to update Cloudflare Tunnel config file with ingress rules

set -e

CONFIG_FILE="cloudflare/config.yml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Config file not found: $CONFIG_FILE"
    echo "Run ./scripts/setup_cloudflare_tunnel_cli.sh first"
    exit 1
fi

# Get tunnel ID from config
TUNNEL_ID=$(grep "^tunnel:" "$CONFIG_FILE" | awk '{print $2}')

if [ -z "$TUNNEL_ID" ]; then
    echo "Could not find tunnel ID in config file"
    exit 1
fi

echo "Current tunnel ID: $TUNNEL_ID"
echo ""

# Get domain info
read -p "Enter your domain (e.g., example.com): " DOMAIN
read -p "Enter UI subdomain (default: ui): " UI_SUBDOMAIN
UI_SUBDOMAIN=${UI_SUBDOMAIN:-ui}
read -p "Enter API subdomain (default: api): " API_SUBDOMAIN
API_SUBDOMAIN=${API_SUBDOMAIN:-api}

UI_DOMAIN="${UI_SUBDOMAIN}.${DOMAIN}"
API_DOMAIN="${API_SUBDOMAIN}.${DOMAIN}"

# Create backup
cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"
echo "Created backup: ${CONFIG_FILE}.backup"

# Update config file
cat > "$CONFIG_FILE" <<EOF
tunnel: $TUNNEL_ID
credentials-file: /etc/cloudflared/credentials.json

ingress:
  # UI - Main frontend
  - hostname: $UI_DOMAIN
    service: http://ui:3000
  
  # API - Backend API
  - hostname: $API_DOMAIN
    service: http://api:8000
  
  # Catch-all rule (must be last)
  - service: http_status:404
EOF

echo "✓ Updated $CONFIG_FILE"
echo ""
echo "Configuration:"
echo "  UI Domain: $UI_DOMAIN"
echo "  API Domain: $API_DOMAIN"
echo ""
echo "Next steps:"
echo "1. Restart cloudflared: docker compose restart cloudflared"
echo "2. Check logs: docker compose logs cloudflared"
echo ""

