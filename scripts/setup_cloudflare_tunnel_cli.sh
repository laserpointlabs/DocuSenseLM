#!/bin/bash

# Cloudflare Tunnel CLI Setup Script
# This script sets up Cloudflare Tunnel using config file (full CLI control)

set -e

echo "=== Cloudflare Tunnel CLI Setup ==="
echo ""

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "cloudflared is not installed. Installing..."
    
    if command -v snap &> /dev/null; then
        echo "Installing via snap (recommended)..."
        sudo snap install cloudflared
    elif command -v apt-get &> /dev/null; then
        echo "Installing via binary..."
        BINARY_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        sudo wget -O /usr/local/bin/cloudflared "${BINARY_URL}"
        sudo chmod +x /usr/local/bin/cloudflared
    else
        echo "Please install cloudflared manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
        exit 1
    fi
    
    if command -v cloudflared &> /dev/null; then
        echo "✓ cloudflared installed successfully"
        cloudflared --version
    else
        echo "✗ Installation failed. Please install manually."
        exit 1
    fi
fi

echo "✓ cloudflared is installed"
echo ""

# Check if user is logged in
if ! cloudflared tunnel list &> /dev/null; then
    echo "Please log in to Cloudflare:"
    cloudflared tunnel login
fi

echo "✓ Logged in to Cloudflare"
echo ""

# Create tunnel
TUNNEL_NAME="nda-tool"
echo "Creating tunnel: $TUNNEL_NAME"
if cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
    echo "Tunnel '$TUNNEL_NAME' already exists"
    TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
    echo "Using existing tunnel ID: $TUNNEL_ID"
else
    TUNNEL_OUTPUT=$(cloudflared tunnel create "$TUNNEL_NAME" 2>&1)
    TUNNEL_ID=$(echo "$TUNNEL_OUTPUT" | grep -oP 'Created tunnel \K[^\s]+' || echo "")
    if [ -z "$TUNNEL_ID" ]; then
        # Try alternative parsing
        TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
    fi
    if [ -z "$TUNNEL_ID" ]; then
        echo "Failed to create tunnel. Please create it manually."
        exit 1
    fi
    echo "Created tunnel ID: $TUNNEL_ID"
fi

echo "✓ Tunnel ID: $TUNNEL_ID"
echo ""

# Get domain from user
read -p "Enter your domain (e.g., example.com): " DOMAIN
read -p "Enter UI subdomain (default: ui): " UI_SUBDOMAIN
UI_SUBDOMAIN=${UI_SUBDOMAIN:-ui}
read -p "Enter API subdomain (default: api): " API_SUBDOMAIN
API_SUBDOMAIN=${API_SUBDOMAIN:-api}

UI_DOMAIN="${UI_SUBDOMAIN}.${DOMAIN}"
API_DOMAIN="${API_SUBDOMAIN}.${DOMAIN}"

echo ""
echo "Creating DNS records..."

# Create DNS records
cloudflared tunnel route dns "$TUNNEL_NAME" "$UI_DOMAIN" 2>/dev/null || echo "DNS record for $UI_DOMAIN may already exist"
cloudflared tunnel route dns "$TUNNEL_NAME" "$API_DOMAIN" 2>/dev/null || echo "DNS record for $API_DOMAIN may already exist"

echo "✓ DNS records created"
echo ""

# Create cloudflare directory if it doesn't exist
mkdir -p cloudflare

# Find credentials file location
CREDENTIALS_FILE=""
if [ -f "$HOME/.cloudflared/$TUNNEL_ID.json" ]; then
    CREDENTIALS_FILE="$HOME/.cloudflared/$TUNNEL_ID.json"
elif [ -f "$HOME/.cloudflared/$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}').json" ]; then
    CREDENTIALS_FILE="$HOME/.cloudflared/$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}').json"
else
    echo "Warning: Could not find credentials file automatically."
    echo "Credentials are usually stored in: ~/.cloudflared/$TUNNEL_ID.json"
    read -p "Enter path to credentials file (or press Enter to skip): " CREDENTIALS_FILE
    if [ -z "$CREDENTIALS_FILE" ] || [ ! -f "$CREDENTIALS_FILE" ]; then
        echo "Please copy the credentials file to cloudflare/credentials.json manually"
        CREDENTIALS_FILE="cloudflare/credentials.json"
    fi
fi

# Copy credentials file to project directory
if [ -f "$CREDENTIALS_FILE" ]; then
    cp "$CREDENTIALS_FILE" cloudflare/credentials.json
    echo "✓ Copied credentials file to cloudflare/credentials.json"
else
    echo "⚠ Credentials file not found. You'll need to copy it manually to cloudflare/credentials.json"
fi

# Create config file
CONFIG_FILE="cloudflare/config.yml"
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

echo "✓ Created config file: $CONFIG_FILE"
echo ""

# Update docker-compose.yml to use config file
echo "Updating docker-compose.yml to use config file..."
# Check if already using config file
if grep -q "tunnel --config" docker-compose.yml; then
    echo "docker-compose.yml already configured for config file"
else
    # Create backup
    cp docker-compose.yml docker-compose.yml.backup
    echo "Created backup: docker-compose.yml.backup"
    
    # Update cloudflared service to use config file
    sed -i 's|command: tunnel run|command: tunnel --config /etc/cloudflared/config.yml run|' docker-compose.yml
    
    # Uncomment volumes section
    sed -i 's|# volumes:|volumes:|' docker-compose.yml
    sed -i 's|#   - ./cloudflare/config.yml:/etc/cloudflared/config.yml:ro|  - ./cloudflare/config.yml:/etc/cloudflared/config.yml:ro|' docker-compose.yml
    sed -i 's|#   - ./cloudflare/credentials.json:/etc/cloudflared/credentials.json:ro|  - ./cloudflare/credentials.json:/etc/cloudflared/credentials.json:ro|' docker-compose.yml
    
    # Remove TUNNEL_TOKEN environment variable (not needed with config file)
    sed -i '/TUNNEL_TOKEN=/d' docker-compose.yml
    
    echo "✓ Updated docker-compose.yml to use config file"
fi

# Update .env file
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    echo "Creating .env file..."
    touch "$ENV_FILE"
fi

# Add or update Cloudflare config in .env
if grep -q "CLOUDFLARE_TUNNEL_ID" "$ENV_FILE"; then
    sed -i "s|CLOUDFLARE_TUNNEL_ID=.*|CLOUDFLARE_TUNNEL_ID=$TUNNEL_ID|" "$ENV_FILE"
else
    echo "" >> "$ENV_FILE"
    echo "# Cloudflare Tunnel Configuration (CLI setup)" >> "$ENV_FILE"
    echo "CLOUDFLARE_TUNNEL_ID=$TUNNEL_ID" >> "$ENV_FILE"
fi

if grep -q "CLOUDFLARE_DOMAIN_UI" "$ENV_FILE"; then
    sed -i "s|CLOUDFLARE_DOMAIN_UI=.*|CLOUDFLARE_DOMAIN_UI=$UI_DOMAIN|" "$ENV_FILE"
else
    echo "CLOUDFLARE_DOMAIN_UI=$UI_DOMAIN" >> "$ENV_FILE"
fi

if grep -q "CLOUDFLARE_DOMAIN_API" "$ENV_FILE"; then
    sed -i "s|CLOUDFLARE_DOMAIN_API=.*|CLOUDFLARE_DOMAIN_API=$API_DOMAIN|" "$ENV_FILE"
else
    echo "CLOUDFLARE_DOMAIN_API=$API_DOMAIN" >> "$ENV_FILE"
fi

echo "✓ Updated .env file"
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Configuration:"
echo "  Tunnel ID: $TUNNEL_ID"
echo "  UI Domain: https://$UI_DOMAIN"
echo "  API Domain: https://$API_DOMAIN"
echo "  Config File: $CONFIG_FILE"
echo "  Credentials: cloudflare/credentials.json"
echo ""
echo "Next steps:"
echo "1. Verify credentials file exists: ls -la cloudflare/credentials.json"
echo "2. Review config file: cat $CONFIG_FILE"
echo "3. Start services: docker compose up -d"
echo "4. Check tunnel logs: docker compose logs cloudflared"
echo "5. Visit: https://$UI_DOMAIN"
echo ""

