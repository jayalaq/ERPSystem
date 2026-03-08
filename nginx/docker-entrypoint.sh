#!/bin/sh
# Substitute only our custom env vars, preserving nginx variables like $host, $remote_addr, etc.
envsubst '${ERP_PRODUCTION_HOST} ${ERP_TESTING_HOST} ${DOMAIN}' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
