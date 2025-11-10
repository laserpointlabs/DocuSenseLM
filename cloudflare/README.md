# Cloudflare Tunnel Setup

This guide will help you set up Cloudflare Tunnel to expose your NDA Dashboard from home.

## Prerequisites

1. A Cloudflare account (free tier works)
2. A domain name added to Cloudflare (or use Cloudflare's free subdomain)
3. Docker and Docker Compose installed

## Quick Setup (Recommended - No Host Installation Needed)

Since the `docker-compose.yml` includes a cloudflared service, you don't need to install cloudflared on your host machine. Just:

1. **Create a tunnel in Cloudflare Dashboard**:
   - Go to [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)
   - Navigate to Networks → Tunnels
   - Click "Create a tunnel"
   - Choose "Cloudflared" and give it a name (e.g., "nda-tool")
   - Copy the tunnel token

2. **Add to your `.env` file**:
   ```bash
   CLOUDFLARE_TUNNEL_TOKEN=<paste-token-here>
   CLOUDFLARE_DOMAIN_UI=ui.yourdomain.com
   CLOUDFLARE_DOMAIN_API=api.yourdomain.com
   ```

3. **Configure Ingress Rules** (IMPORTANT - in Cloudflare Dashboard):
   - In the tunnel configuration page, click "Configure" next to your tunnel
   - Go to the "Public Hostnames" tab
   - Add two public hostnames:
     - **Hostname**: `ui.yourdomain.com`
       - **Service**: `http://ui:3000`
     - **Hostname**: `api.yourdomain.com`
       - **Service**: `http://api:8000`
   - Save the configuration

4. **Configure DNS** (in Cloudflare Dashboard):
   - Go to DNS → Records
   - Create CNAME records:
     - `ui` → `<tunnel-id>.cfargotunnel.com`
     - `api` → `<tunnel-id>.cfargotunnel.com`

5. **Start services**:
   ```bash
   docker compose up -d
   ```

That's it! The cloudflared container will handle the tunnel connection.

---

## CLI Setup (Full Control via Config File)

For full CLI control with ingress rules defined in a config file:

```bash
./scripts/setup_cloudflare_tunnel_cli.sh
```

This script will:
1. Install cloudflared if needed
2. Create a tunnel via CLI
3. Create DNS records
4. Generate `cloudflare/config.yml` with ingress rules
5. Copy credentials file to `cloudflare/credentials.json`
6. Update `docker-compose.yml` to use the config file

The config file approach gives you full control over ingress rules from the CLI/config file, without needing the Cloudflare Dashboard.

**After running the script:**
- Review the generated `cloudflare/config.yml`
- Ensure `cloudflare/credentials.json` exists
- Start services: `docker compose up -d`

---

## Alternative: Using the Token-Based Setup Script

If you prefer token-based authentication (simpler, but requires Dashboard for ingress rules):

## Step 1: Install Cloudflare CLI (if not already installed)

```bash
# On Linux
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Or using snap
sudo snap install cloudflared
```

## Step 2: Authenticate with Cloudflare

```bash
cloudflared tunnel login
```

This will open a browser window for you to authenticate. Select the domain you want to use.

## Step 3: Create a Tunnel

```bash
cloudflared tunnel create nda-tool
```

This will create a tunnel and save credentials. Note the tunnel ID that's displayed.

## Step 4: Create DNS Records

Create DNS records pointing to your tunnel:

```bash
# For UI (main frontend)
cloudflared tunnel route dns nda-tool ui.yourdomain.com

# For API (backend)
cloudflared tunnel route dns nda-tool api.yourdomain.com
```

Or manually create CNAME records in Cloudflare dashboard:
- `ui.yourdomain.com` → `<tunnel-id>.cfargotunnel.com`
- `api.yourdomain.com` → `<tunnel-id>.cfargotunnel.com`

## Step 5: Configure Environment Variables

Add these to your `.env` file:

```bash
# Cloudflare Tunnel Configuration
CLOUDFLARE_TUNNEL_ID=<your-tunnel-id>
CLOUDFLARE_TUNNEL_TOKEN=<your-tunnel-token>
CLOUDFLARE_DOMAIN_UI=ui.yourdomain.com
CLOUDFLARE_DOMAIN_API=api.yourdomain.com
```

### Getting the Tunnel Token

If you created the tunnel via CLI, you can get the token:

```bash
cloudflared tunnel token nda-tool
```

Or create a token in Cloudflare Dashboard:
1. Go to Zero Trust → Networks → Tunnels
2. Click on your tunnel
3. Click "Create token" and copy it

## Step 6: Update docker-compose.yml

The cloudflared service is already added to docker-compose.yml. Make sure your `.env` file has the tunnel token.

## Step 7: Start the Services

```bash
docker-compose up -d
```

## Step 8: Verify

1. Check tunnel logs: `docker-compose logs cloudflared`
2. Visit `https://ui.yourdomain.com` in your browser
3. The API should be accessible at `https://api.yourdomain.com`

## Troubleshooting

### Tunnel won't start
- Check that `CLOUDFLARE_TUNNEL_TOKEN` is set correctly
- Verify the token hasn't expired
- Check logs: `docker-compose logs cloudflared`

### DNS not resolving
- Wait a few minutes for DNS propagation
- Verify CNAME records in Cloudflare dashboard
- Check tunnel status: `cloudflared tunnel info nda-tool`

### Services not accessible
- Ensure UI and API containers are running: `docker-compose ps`
- Check that services are healthy: `docker-compose logs ui api`
- Verify the tunnel is connected: `cloudflared tunnel info nda-tool`

## Alternative: Quick Tunnel (for testing)

For quick testing without setting up DNS:

```bash
cloudflared tunnel --url http://localhost:3000
```

This will give you a temporary URL like `https://random-name.trycloudflare.com`

## Security Notes

- Cloudflare Tunnel automatically provides HTTPS
- Consider adding Cloudflare Access rules for additional security
- The tunnel token should be kept secret - don't commit it to git
- Use environment variables or secrets management for production

