#!/bin/bash
#
# ERP System - Deploy on Hostinger VPS (alongside existing n8n)
# Usage: ./scripts/deploy-hostinger.sh [testing|production|all]
#
set -euo pipefail

ENV="${1:-all}"
PROJECT_DIR="/opt/erp"
COMPOSE_FILE="docker-compose.hostinger.yml"

echo "============================================"
echo "  ERP System - Hostinger Deploy"
echo "  Environment: ${ENV}"
echo "============================================"

# Check .env exists
if [ ! -f "${PROJECT_DIR}/.env" ]; then
    echo "ERROR: .env not found at ${PROJECT_DIR}/.env"
    echo "Run: cp .env.example .env && nano .env"
    exit 1
fi

source "${PROJECT_DIR}/.env"

# Detect n8n network
echo ""
echo "[1/6] Detecting n8n Docker network..."
N8N_NETWORK=$(docker network ls --format '{{.Name}}' | grep -i 'n8n\|hostinger' | head -1 || echo "")
if [ -z "${N8N_NETWORK}" ]; then
    echo "  No n8n network found. Creating 'hostinger_default'..."
    docker network create hostinger_default 2>/dev/null || true
    N8N_NETWORK="hostinger_default"
fi
echo "  Using network: ${N8N_NETWORK}"
export HOSTINGER_NETWORK="${N8N_NETWORK}"

# Build
echo ""
echo "[2/6] Building Docker images..."
cd "${PROJECT_DIR}"
docker compose -f ${COMPOSE_FILE} build

# Deploy based on environment
case "${ENV}" in
    testing)
        echo ""
        echo "[3/6] Starting TESTING environment..."
        docker compose -f ${COMPOSE_FILE} up -d erp-db-testing erp-redis erp-app-testing erp-nginx
        sleep 8
        echo "[4/6] Running migrations..."
        docker compose -f ${COMPOSE_FILE} exec -T erp-app-testing python manage.py migrate
        docker compose -f ${COMPOSE_FILE} exec -T erp-app-testing python manage.py collectstatic --noinput 2>/dev/null || true
        echo "[5/6] Loading initial data..."
        docker compose -f ${COMPOSE_FILE} exec -T erp-app-testing python manage.py seed_initial_data
        echo "[6/6] Done!"
        echo ""
        echo "  Testing: https://testing.${DOMAIN}"
        ;;

    production)
        echo ""
        echo "[3/6] Starting PRODUCTION environment..."
        docker compose -f ${COMPOSE_FILE} up -d erp-db-production erp-redis erp-app-production erp-celery-worker erp-celery-beat erp-nginx
        sleep 8
        echo "[4/6] Running migrations..."
        docker compose -f ${COMPOSE_FILE} exec -T erp-app-production python manage.py migrate
        docker compose -f ${COMPOSE_FILE} exec -T erp-app-production python manage.py collectstatic --noinput
        echo "[5/6] Loading initial data..."
        docker compose -f ${COMPOSE_FILE} exec -T erp-app-production python manage.py seed_initial_data
        echo "[6/6] Done!"
        echo ""
        echo "  Production: https://${DOMAIN}"
        ;;

    all)
        echo ""
        echo "[3/6] Starting ALL services..."
        docker compose -f ${COMPOSE_FILE} up -d
        sleep 10

        echo "[4/6] Running migrations..."
        docker compose -f ${COMPOSE_FILE} exec -T erp-app-testing python manage.py migrate
        docker compose -f ${COMPOSE_FILE} exec -T erp-app-production python manage.py migrate

        echo "[5/6] Collecting static + loading data..."
        docker compose -f ${COMPOSE_FILE} exec -T erp-app-testing python manage.py collectstatic --noinput 2>/dev/null || true
        docker compose -f ${COMPOSE_FILE} exec -T erp-app-production python manage.py collectstatic --noinput
        docker compose -f ${COMPOSE_FILE} exec -T erp-app-testing python manage.py seed_initial_data
        docker compose -f ${COMPOSE_FILE} exec -T erp-app-production python manage.py seed_initial_data

        echo "[6/6] Done!"
        echo ""
        echo "============================================"
        echo "  ALL SYSTEMS RUNNING"
        echo "============================================"
        echo "  Testing:    https://testing.${DOMAIN}"
        echo "  Production: https://${DOMAIN}"
        echo "  n8n:        https://n8n.${DOMAIN} (existing)"
        echo ""
        echo "  n8n API Endpoints:"
        echo "    GET  https://${DOMAIN}/api/n8n/dashboard/"
        echo "    GET  https://${DOMAIN}/api/n8n/customers/"
        echo "    GET  https://${DOMAIN}/api/n8n/products/"
        echo "    GET  https://${DOMAIN}/api/n8n/sales/"
        echo "    GET  https://${DOMAIN}/api/n8n/invoices/"
        echo "    GET  https://${DOMAIN}/api/n8n/stock/"
        echo "    POST https://${DOMAIN}/api/n8n/action/"
        echo ""
        echo "  Create admin users:"
        echo "    docker compose -f ${COMPOSE_FILE} exec erp-app-production python manage.py createsuperuser"
        echo "    docker compose -f ${COMPOSE_FILE} exec erp-app-testing python manage.py createsuperuser"
        echo ""
        echo "  Connect n8n to ERP:"
        echo "    In n8n, use HTTP Request node with:"
        echo "    Header: X-N8N-API-Key = \${N8N_API_KEY}"
        echo "    URL: http://erp-nginx/api/n8n/..."
        echo "============================================"
        ;;

    *)
        echo "Usage: $0 [testing|production|all]"
        exit 1
        ;;
esac

echo ""
echo "Service status:"
docker compose -f ${COMPOSE_FILE} ps
