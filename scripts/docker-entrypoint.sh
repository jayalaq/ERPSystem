#!/bin/bash
set -e

echo "Waiting for database..."
while ! python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.environ.get('DJANGO_SETTINGS_MODULE', 'erp_system.settings'))
django.setup()
from django.db import connection
connection.ensure_connection()
" 2>/dev/null; do
    echo "Database not ready, waiting 2 seconds..."
    sleep 2
done
echo "Database is ready!"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput 2>/dev/null || true

exec "$@"
