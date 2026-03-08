#!/bin/bash
set -e

echo "Waiting for database..."
MAX_RETRIES=30
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.environ.get('DJANGO_SETTINGS_MODULE', 'erp_system.settings'))
django.setup()
from django.db import connection
connection.ensure_connection()
print('Database connected successfully')
" 2>&1; then
        break
    fi
    RETRY=$((RETRY + 1))
    echo "Database not ready (attempt $RETRY/$MAX_RETRIES), waiting 2 seconds..."
    sleep 2
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    echo "ERROR: Could not connect to database after $MAX_RETRIES attempts"
    exit 1
fi

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput 2>/dev/null || true

exec "$@"
