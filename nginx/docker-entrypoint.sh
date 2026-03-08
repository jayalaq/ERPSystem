#!/bin/sh
set -e

# Substitute only our custom env vars, preserving nginx variables like $host, $remote_addr, etc.
mkdir -p /etc/nginx/conf.d
envsubst '${ERP_PRODUCTION_HOST} ${ERP_TESTING_HOST} ${DOMAIN}' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

echo "=== Generated nginx config ==="
grep server_name /etc/nginx/conf.d/default.conf
echo "=== Starting nginx ==="

exec nginx -g 'daemon off;'
