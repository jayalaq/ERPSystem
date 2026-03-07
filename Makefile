.PHONY: help dev prod test migrate seed backup logs clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================
# DEVELOPMENT
# ============================================
dev: ## Start testing environment
	docker compose up -d db-testing redis app-testing nginx
	@echo "\n  Testing:    http://localhost:8001"
	@echo "  Nginx:      http://localhost:80"

dev-logs: ## Tail testing logs
	docker compose logs -f app-testing

# ============================================
# PRODUCTION
# ============================================
prod: ## Start full production stack
	docker compose up -d
	@echo "\n  Production: http://localhost:8000"
	@echo "  Testing:    http://localhost:8001"

prod-logs: ## Tail production logs
	docker compose logs -f app-production celery-worker

# ============================================
# DATABASE
# ============================================
migrate-test: ## Run migrations on testing DB
	docker compose exec app-testing python manage.py migrate

migrate-prod: ## Run migrations on production DB
	docker compose exec app-production python manage.py migrate

seed-test: ## Seed initial data on testing DB
	docker compose exec app-testing python manage.py seed_initial_data

seed-prod: ## Seed initial data on production DB
	docker compose exec app-production python manage.py seed_initial_data

superuser-test: ## Create superuser on testing
	docker compose exec app-testing python manage.py createsuperuser

superuser-prod: ## Create superuser on production
	docker compose exec app-production python manage.py createsuperuser

# ============================================
# BACKUP
# ============================================
backup: ## Backup production database
	docker compose --profile backup run --rm db-backup
	@echo "Backup saved to ./backups/"

backup-list: ## List available backups
	@ls -lah backups/*.sql.gz 2>/dev/null || echo "No backups found"

restore: ## Restore production DB from backup (usage: make restore FILE=backups/file.sql.gz)
	@test -n "$(FILE)" || (echo "Usage: make restore FILE=backups/erp_production_XXXXXXXX.sql.gz" && exit 1)
	gunzip -c $(FILE) | docker compose exec -T db-production psql -U erp_user erp_production

# ============================================
# CLOUDFLARE
# ============================================
cf-setup: ## Run Cloudflare setup (usage: make cf-setup DOMAIN=example.com)
	@test -n "$(DOMAIN)" || (echo "Usage: make cf-setup DOMAIN=example.com" && exit 1)
	./scripts/setup-cloudflare.sh $(DOMAIN)

cf-tunnel-status: ## Check Cloudflare tunnel status
	docker compose logs cloudflared --tail=20

# ============================================
# MAINTENANCE
# ============================================
test: ## Run Django tests
	docker compose exec app-testing python manage.py test --verbosity=2

shell-test: ## Django shell on testing
	docker compose exec app-testing python manage.py shell

shell-prod: ## Django shell on production
	docker compose exec app-production python manage.py shell

collectstatic: ## Collect static files
	docker compose exec app-production python manage.py collectstatic --noinput

clean: ## Stop all containers and remove volumes
	docker compose down -v
	@echo "All containers and volumes removed"

restart: ## Restart all services
	docker compose restart

status: ## Show status of all services
	docker compose ps
