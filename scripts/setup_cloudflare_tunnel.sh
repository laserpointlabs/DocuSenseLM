#!/bin/bash

# Cloudflare Tunnel Setup Script
# This script helps set up Cloudflare Tunnel for the NDA Dashboard

set -e

echo "=== Cloudflare Tunnel Setup ==="
echo ""

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "cloudflared is not installed. Installing..."
    
    # Detect OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v snap &> /dev/null; then
            echo "Installing via snap (recommended)..."
            sudo snap install cloudflared
        elif command -v apt-get &> /dev/null; then
            echo "Installing via .deb package..."
            DEB_FILE="cloudflared-linux-amd64.deb"
            # Download with retry and verification
            if ! wget --tries=3 --timeout=30 "https://github.com/cloudflare/cloudflared/releases/latest/download/${DEB_FILE}" -O "${DEB_FILE}"; then
                echo "Download failed. Trying alternative method..."
                # Try direct binary installation instead
                BINARY_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
                sudo wget -O /usr/local/bin/cloudflared "${BINARY_URL}"
                sudo chmod +x /usr/local/bin/cloudflared
            else
                # Verify file integrity before installing
                if file "${DEB_FILE}" | grep -q "Debian binary package"; then
                    sudo dpkg -i "${DEB_FILE}"
                    rm "${DEB_FILE}"
                else
                    echo "Downloaded file appears corrupted. Trying binary installation..."
                    rm "${DEB_FILE}"
                    BINARY_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
                    sudo wget -O /usr/local/bin/cloudflared "${BINARY_URL}"
                    sudo chmod +x /usr/local/bin/cloudflared
                fi
            fi
        else
            echo "Please install cloudflared manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
            exit 1
        fi
    else
        echo "Please install cloudflared manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
        exit 1
    fi
    
    # Verify installation
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
else
    TUNNEL_OUTPUT=$(cloudflared tunnel create "$TUNNEL_NAME" 2>&1)
    TUNNEL_ID=$(echo "$TUNNEL_OUTPUT" | grep -oP 'Created tunnel \K[^\s]+' || echo "")
    if [ -z "$TUNNEL_ID" ]; then
        echo "Failed to create tunnel. Please create it manually."
        exit 1
    fi
fi

echo "✓ Tunnel ID: $TUNNEL_ID"
echo ""

# Get tunnel token
echo "Getting tunnel token..."
TUNNEL_TOKEN=$(cloudflared tunnel token "$TUNNEL_NAME" 2>/dev/null || echo "")

if [ -z "$TUNNEL_TOKEN" ]; then
    echo "Could not get tunnel token automatically."
    echo "Please get it from Cloudflare Dashboard:"
    echo "1. Go to Zero Trust → Networks → Tunnels"
    echo "2. Click on '$TUNNEL_NAME'"
    echo "3. Click 'Create token' and copy it"
    read -p "Enter tunnel token: " TUNNEL_TOKEN
fi

echo "✓ Tunnel token obtained"
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
    echo "# Cloudflare Tunnel Configuration" >> "$ENV_FILE"
    echo "CLOUDFLARE_TUNNEL_ID=$TUNNEL_ID" >> "$ENV_FILE"
fi

if grep -q "CLOUDFLARE_TUNNEL_TOKEN" "$ENV_FILE"; then
    sed -i "s|CLOUDFLARE_TUNNEL_TOKEN=.*|CLOUDFLARE_TUNNEL_TOKEN=$TUNNEL_TOKEN|" "$ENV_FILE"
else
    echo "CLOUDFLARE_TUNNEL_TOKEN=$TUNNEL_TOKEN" >> "$ENV_FILE"
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
echo ""
echo "Next steps:"
echo "1. Wait a few minutes for DNS propagation"
echo "2. Start services: docker-compose up -d"
echo "3. Check tunnel logs: docker-compose logs cloudflared"
echo "4. Visit: https://$UI_DOMAIN"
echo ""

