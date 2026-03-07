FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput 2>/dev/null || true
RUN chmod +x scripts/docker-entrypoint.sh

# --- Development ---
FROM base AS development
ENV DJANGO_SETTINGS_MODULE=erp_system.settings
EXPOSE 8000
ENTRYPOINT ["scripts/docker-entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# --- Production ---
FROM base AS production
ENV DJANGO_SETTINGS_MODULE=erp_system.settings_production

RUN addgroup --system django && adduser --system --group django
USER django

EXPOSE 8000
ENTRYPOINT ["scripts/docker-entrypoint.sh"]
CMD ["gunicorn", "erp_system.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "gthread", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
