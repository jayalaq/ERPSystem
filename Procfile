web: gunicorn erp_system.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --threads 2 --timeout 120
worker: celery -A erp_system worker -l info --concurrency=2
beat: celery -A erp_system beat -l info --schedule=/tmp/celerybeat-schedule
