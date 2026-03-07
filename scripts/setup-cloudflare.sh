#!/bin/bash
#
# Cloudflare Setup Script for ERP System
# Prerequisites: cloudflared CLI, wrangler CLI
#
# Usage: ./scripts/setup-cloudflare.sh <your-domain.com>
#

set -euo pipefail

DOMAIN="${1:?Usage: $0 <domain>}"
TUNNEL_NAME="erp-tunnel"

echo "============================================"
echo "  ERP System - Cloudflare Setup"
echo "  Domain: ${DOMAIN}"
echo "============================================"

# -------------------------------------------
# 1. Authenticate with Cloudflare
# -------------------------------------------
echo ""
echo "[1/6] Authenticating with Cloudflare..."
if ! cloudflared tunnel list &>/dev/null; then
    cloudflared tunnel login
fi

# -------------------------------------------
# 2. Create Cloudflare Tunnel
# -------------------------------------------
echo ""
echo "[2/6] Creating Cloudflare Tunnel..."
if cloudflared tunnel list | grep -q "${TUNNEL_NAME}"; then
    echo "  Tunnel '${TUNNEL_NAME}' already exists"
    TUNNEL_ID=$(cloudflared tunnel list | grep "${TUNNEL_NAME}" | awk '{print $1}')
else
    cloudflared tunnel create "${TUNNEL_NAME}"
    TUNNEL_ID=$(cloudflared tunnel list | grep "${TUNNEL_NAME}" | awk '{print $1}')
fi
echo "  Tunnel ID: ${TUNNEL_ID}"

# -------------------------------------------
# 3. Configure DNS records
# -------------------------------------------
echo ""
echo "[3/6] Configuring DNS records..."
cloudflared tunnel route dns "${TUNNEL_NAME}" "${DOMAIN}" 2>/dev/null || echo "  DNS record for ${DOMAIN} may already exist"
cloudflared tunnel route dns "${TUNNEL_NAME}" "testing.${DOMAIN}" 2>/dev/null || echo "  DNS record for testing.${DOMAIN} may already exist"
cloudflared tunnel route dns "${TUNNEL_NAME}" "www.${DOMAIN}" 2>/dev/null || echo "  DNS record for www.${DOMAIN} may already exist"

# -------------------------------------------
# 4. Create Tunnel config
# -------------------------------------------
echo ""
echo "[4/6] Creating tunnel configuration..."
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml <<EOF
tunnel: ${TUNNEL_ID}
credentials-file: /root/.cloudflared/${TUNNEL_ID}.json

ingress:
  # Production ERP
  - hostname: ${DOMAIN}
    service: http://nginx:80
  - hostname: www.${DOMAIN}
    service: http://nginx:80

  # Testing ERP
  - hostname: testing.${DOMAIN}
    service: http://nginx:80

  # Catch-all
  - service: http_status:404
EOF
echo "  Config written to ~/.cloudflared/config.yml"

# -------------------------------------------
# 5. Create R2 bucket
# -------------------------------------------
echo ""
echo "[5/6] Creating R2 storage bucket..."
if command -v wrangler &>/dev/null; then
    wrangler r2 bucket create erp-media 2>/dev/null || echo "  Bucket 'erp-media' may already exist"
    wrangler r2 bucket create erp-backups 2>/dev/null || echo "  Bucket 'erp-backups' may already exist"
    echo "  R2 buckets created. Get API tokens from Cloudflare Dashboard > R2 > Manage R2 API tokens"
else
    echo "  wrangler not installed. Install with: npm install -g wrangler"
    echo "  Then create buckets manually or re-run this script"
fi

# -------------------------------------------
# 6. Get Tunnel Token for Docker
# -------------------------------------------
echo ""
echo "[6/6] Getting tunnel token..."
TUNNEL_TOKEN=$(cloudflared tunnel token "${TUNNEL_NAME}" 2>/dev/null || echo "")
if [ -n "${TUNNEL_TOKEN}" ]; then
    echo ""
    echo "============================================"
    echo "  SETUP COMPLETE!"
    echo "============================================"
    echo ""
    echo "Add this to your .env file:"
    echo ""
    echo "  DOMAIN=${DOMAIN}"
    echo "  CLOUDFLARE_TUNNEL_TOKEN=${TUNNEL_TOKEN}"
    echo ""
    echo "Then configure R2 credentials in .env:"
    echo "  CLOUDFLARE_R2_ACCESS_KEY=<from dashboard>"
    echo "  CLOUDFLARE_R2_SECRET_KEY=<from dashboard>"
    echo "  CLOUDFLARE_R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com"
    echo "  CLOUDFLARE_R2_PUBLIC_URL=https://media.${DOMAIN}"
    echo ""
else
    echo "  Could not retrieve token. Run: cloudflared tunnel token ${TUNNEL_NAME}"
fi

echo ""
echo "Next steps:"
echo "  1. Copy .env.example to .env and fill in values"
echo "  2. Run: docker compose up -d"
echo "  3. Run: docker compose exec app-production python manage.py migrate"
echo "  4. Run: docker compose exec app-production python manage.py createsuperuser"
echo "  5. Run: docker compose exec app-production python manage.py seed_initial_data"
echo ""
echo "Cloudflare Dashboard settings to verify:"
echo "  - SSL/TLS: Full (strict)"
echo "  - Always Use HTTPS: ON"
echo "  - Auto Minify: CSS, JS, HTML"
echo "  - Brotli: ON"
echo "  - Browser Cache TTL: 4 hours"
echo "  - Security Level: Medium"
echo "  - Bot Fight Mode: ON"
echo ""
