#!/bin/bash
#
# ERP System - Quick Deploy Script
# Usage: ./scripts/deploy.sh [testing|production|all]
#

set -euo pipefail

ENV="${1:-all}"

echo "============================================"
echo "  ERP System Deploy - ${ENV}"
echo "============================================"

# Check .env file exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and configure it."
    exit 1
fi

source .env

case "${ENV}" in
    testing)
        echo "Deploying TESTING environment..."
        docker compose up -d db-testing redis app-testing nginx
        sleep 5
        docker compose exec -T app-testing python manage.py migrate
        docker compose exec -T app-testing python manage.py collectstatic --noinput
        docker compose exec -T app-testing python manage.py seed_initial_data
        echo ""
        echo "Testing ready at: http://testing.${DOMAIN:-localhost:8001}"
        ;;
    production)
        echo "Deploying PRODUCTION environment..."
        docker compose up -d db-production redis app-production celery-worker celery-beat nginx cloudflared
        sleep 5
        docker compose exec -T app-production python manage.py migrate
        docker compose exec -T app-production python manage.py collectstatic --noinput
        docker compose exec -T app-production python manage.py seed_initial_data
        echo ""
        echo "Production ready at: https://${DOMAIN:-localhost:8000}"
        ;;
    all)
        echo "Deploying ALL environments..."
        docker compose up -d
        sleep 8
        echo ""
        echo "Running testing migrations..."
        docker compose exec -T app-testing python manage.py migrate
        docker compose exec -T app-testing python manage.py collectstatic --noinput 2>/dev/null || true
        docker compose exec -T app-testing python manage.py seed_initial_data
        echo ""
        echo "Running production migrations..."
        docker compose exec -T app-production python manage.py migrate
        docker compose exec -T app-production python manage.py collectstatic --noinput 2>/dev/null || true
        docker compose exec -T app-production python manage.py seed_initial_data
        echo ""
        echo "============================================"
        echo "  ALL SYSTEMS READY"
        echo "============================================"
        echo "  Testing:    http://testing.${DOMAIN:-localhost:8001}"
        echo "  Production: https://${DOMAIN:-localhost:8000}"
        echo "  Admin:      https://${DOMAIN:-localhost:8000}/admin/"
        echo ""
        echo "  Create admin user:"
        echo "    make superuser-prod"
        echo "    make superuser-test"
        echo "============================================"
        ;;
    *)
        echo "Usage: $0 [testing|production|all]"
        exit 1
        ;;
esac
