#!/bin/bash
# ============================================
# TAILORINGCONSULT S.A.C.S - ERP Setup
# Hostinger VPS + n8n existente + Cloudflare
#
# Ejecutar en tu VPS Hostinger:
#   curl -sL <raw-github-url>/scripts/setup-tailoringconsult.sh | bash
#   o: ./scripts/setup-tailoringconsult.sh
# ============================================

set -euo pipefail

DOMAIN="app.tailoringconsult.com"
TEST_DOMAIN="test-app.tailoringconsult.com"
PROJECT_DIR="/opt/erp"
COMPOSE_FILE="docker-compose.hostinger.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "============================================"
echo "  TAILORINGCONSULT S.A.C.S"
echo "  ERP System - Setup Automático"
echo "  RUC: 20610248633"
echo "============================================"
echo -e "${NC}"

# ==========================================
# PASO 1: Verificar requisitos
# ==========================================
echo -e "${YELLOW}[PASO 1/8] Verificando requisitos...${NC}"

# Docker
if ! command -v docker &>/dev/null; then
    echo "  Instalando Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    echo -e "  ${GREEN}✓ Docker instalado${NC}"
fi

# Docker Compose
if ! docker compose version &>/dev/null; then
    echo "  Instalando Docker Compose plugin..."
    apt-get update && apt-get install -y docker-compose-plugin
else
    echo -e "  ${GREEN}✓ Docker Compose disponible${NC}"
fi

# Git
if ! command -v git &>/dev/null; then
    apt-get install -y git
fi
echo -e "  ${GREEN}✓ Git disponible${NC}"

# ==========================================
# PASO 2: Detectar red de n8n
# ==========================================
echo ""
echo -e "${YELLOW}[PASO 2/8] Detectando tu instancia de n8n...${NC}"

N8N_NETWORK=""
N8N_CONTAINER=""

# Buscar contenedor n8n
N8N_CONTAINER=$(docker ps --format '{{.Names}}' | grep -i n8n | head -1 || echo "")
if [ -n "${N8N_CONTAINER}" ]; then
    echo -e "  ${GREEN}✓ n8n encontrado: ${N8N_CONTAINER}${NC}"
    # Obtener la red del contenedor n8n
    N8N_NETWORK=$(docker inspect "${N8N_CONTAINER}" --format '{{range $key, $value := .NetworkSettings.Networks}}{{$key}}{{end}}' | head -1 || echo "")
    echo -e "  ${GREEN}✓ Red de n8n: ${N8N_NETWORK}${NC}"
else
    echo -e "  ${YELLOW}⚠ No se encontró contenedor n8n activo${NC}"
    # Buscar red existente
    N8N_NETWORK=$(docker network ls --format '{{.Name}}' | grep -iE 'n8n|hostinger' | head -1 || echo "")
    if [ -z "${N8N_NETWORK}" ]; then
        echo "  Creando red 'hostinger_default'..."
        docker network create hostinger_default 2>/dev/null || true
        N8N_NETWORK="hostinger_default"
    fi
    echo -e "  ${GREEN}✓ Usando red: ${N8N_NETWORK}${NC}"
fi

# ==========================================
# PASO 3: Clonar/actualizar repositorio
# ==========================================
echo ""
echo -e "${YELLOW}[PASO 3/8] Preparando código fuente...${NC}"

if [ -d "${PROJECT_DIR}/.git" ]; then
    echo "  Actualizando repositorio existente..."
    cd "${PROJECT_DIR}"
    git pull origin main 2>/dev/null || git pull 2>/dev/null || true
else
    echo "  NOTA: Clona tu repositorio manualmente:"
    echo "    git clone <tu-repo-url> ${PROJECT_DIR}"
    echo "    cd ${PROJECT_DIR}"

    if [ ! -d "${PROJECT_DIR}" ]; then
        mkdir -p "${PROJECT_DIR}"
    fi
fi

cd "${PROJECT_DIR}"

# ==========================================
# PASO 4: Generar .env
# ==========================================
echo ""
echo -e "${YELLOW}[PASO 4/8] Generando configuración .env...${NC}"

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || openssl rand -base64 50 | tr -dc 'a-zA-Z0-9' | head -c 50)
DB_PROD_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
DB_TEST_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
N8N_API_KEY=$(openssl rand -hex 32)

if [ -f .env ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "  Backup de .env existente creado"
fi

cat > .env << ENVEOF
# ============================================
# TAILORINGCONSULT S.A.C.S - ERP System
# Generado automáticamente: $(date)
# ============================================

# --- General ---
SECRET_KEY=${SECRET_KEY}
DEBUG=False
DOMAIN=${DOMAIN}

# --- Database ---
DB_TESTING_PASSWORD=${DB_TEST_PASS}
DB_PRODUCTION_PASSWORD=${DB_PROD_PASS}

# --- Company ---
COMPANY_NAME=TAILORINGCONSULT S.A.C.S
COMPANY_RUC=20610248633
COMPANY_ADDRESS=JR. CAMANA NRO. 421 INT. 123 CERCADO DE LIMA LIMA - LIMA - LIMA
COMPANY_PHONE=
COMPANY_EMAIL=servicios@tailoringconsult.com
COMPANY_WEBSITE=https://tailoringconsult.com

# --- SUNAT (modo beta inicialmente) ---
SUNAT_RUC=20610248633
SUNAT_USER=MODDATOS
SUNAT_PASSWORD=moddatos
SUNAT_PRODUCTION=False

# --- Cloudflare Tunnel ---
CLOUDFLARE_TUNNEL_TOKEN=PENDIENTE_VER_PASO_6

# --- Cloudflare R2 ---
CLOUDFLARE_R2_BUCKET=
CLOUDFLARE_R2_ACCESS_KEY=
CLOUDFLARE_R2_SECRET_KEY=
CLOUDFLARE_R2_ENDPOINT=
CLOUDFLARE_R2_PUBLIC_URL=

# --- Email ---
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=servicios@tailoringconsult.com
EMAIL_HOST_PASSWORD=CAMBIAR_AQUI
DEFAULT_FROM_EMAIL=TAILORINGCONSULT <servicios@tailoringconsult.com>

# --- Redis ---
REDIS_URL=redis://erp-redis:6379/0

# --- n8n ---
N8N_API_KEY=${N8N_API_KEY}
N8N_WEBHOOK_URL=http://n8n:5678
HOSTINGER_NETWORK=${N8N_NETWORK}
ENVEOF

echo -e "  ${GREEN}✓ .env generado${NC}"
echo -e "  ${GREEN}✓ SECRET_KEY: generada${NC}"
echo -e "  ${GREEN}✓ DB passwords: generados${NC}"
echo -e "  ${GREEN}✓ N8N_API_KEY: ${N8N_API_KEY}${NC}"
echo ""
echo -e "  ${RED}IMPORTANTE: Guarda esta API key para configurar en n8n:${NC}"
echo -e "  ${BLUE}N8N_API_KEY=${N8N_API_KEY}${NC}"

# ==========================================
# PASO 5: Build e iniciar servicios
# ==========================================
echo ""
echo -e "${YELLOW}[PASO 5/8] Construyendo e iniciando servicios...${NC}"

docker compose -f ${COMPOSE_FILE} build --no-cache
docker compose -f ${COMPOSE_FILE} up -d

echo "  Esperando que las bases de datos estén listas..."
sleep 15

# ==========================================
# PASO 6: Migraciones y datos iniciales
# ==========================================
echo ""
echo -e "${YELLOW}[PASO 6/8] Configurando bases de datos...${NC}"

echo "  Migrando BD testing..."
docker compose -f ${COMPOSE_FILE} exec -T erp-app-testing python manage.py migrate

echo "  Migrando BD producción..."
docker compose -f ${COMPOSE_FILE} exec -T erp-app-production python manage.py migrate

echo "  Cargando datos iniciales (monedas, unidades SUNAT, series)..."
docker compose -f ${COMPOSE_FILE} exec -T erp-app-testing python manage.py seed_initial_data
docker compose -f ${COMPOSE_FILE} exec -T erp-app-production python manage.py seed_initial_data

echo "  Recolectando archivos estáticos..."
docker compose -f ${COMPOSE_FILE} exec -T erp-app-production python manage.py collectstatic --noinput 2>/dev/null || true
docker compose -f ${COMPOSE_FILE} exec -T erp-app-testing python manage.py collectstatic --noinput 2>/dev/null || true

echo -e "  ${GREEN}✓ Bases de datos configuradas${NC}"

# ==========================================
# PASO 7: Verificar servicios
# ==========================================
echo ""
echo -e "${YELLOW}[PASO 7/8] Verificando servicios...${NC}"

docker compose -f ${COMPOSE_FILE} ps

# Health check
sleep 5
HEALTH=$(docker compose -f ${COMPOSE_FILE} exec -T erp-app-production curl -s http://localhost:8000/health/ 2>/dev/null || echo '{"status":"checking"}')
echo ""
echo "  Health check: ${HEALTH}"

# ==========================================
# PASO 8: Instrucciones finales
# ==========================================
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  SETUP COMPLETADO!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${BLUE}PRÓXIMOS PASOS MANUALES:${NC}"
echo ""
echo -e "  ${YELLOW}1. Crear usuario administrador:${NC}"
echo "     docker compose -f ${COMPOSE_FILE} exec erp-app-production python manage.py createsuperuser"
echo ""
echo -e "  ${YELLOW}2. Configurar Cloudflare DNS (en dash.cloudflare.com):${NC}"
echo "     Agregar registros CNAME:"
echo "     - app      → IP-de-tu-VPS  (Proxy: ON)"
echo "     - test-app → IP-de-tu-VPS  (Proxy: ON)"
echo ""
echo -e "  ${YELLOW}3. (Opcional) Crear Cloudflare Tunnel:${NC}"
echo "     cloudflared tunnel login"
echo "     cloudflared tunnel create erp-tunnel"
echo "     cloudflared tunnel route dns erp-tunnel ${DOMAIN}"
echo "     cloudflared tunnel route dns erp-tunnel ${TEST_DOMAIN}"
echo "     # Copiar token al .env: CLOUDFLARE_TUNNEL_TOKEN=..."
echo ""
echo -e "  ${YELLOW}4. Configurar n8n para conectar al ERP:${NC}"
echo "     En tus workflows de n8n, usa HTTP Request con:"
echo "     - Header: X-N8N-API-Key = ${N8N_API_KEY}"
echo "     - URL: http://erp-nginx/api/n8n/dashboard/"
echo ""
echo -e "${BLUE}URLs del sistema:${NC}"
echo "  Producción:  https://${DOMAIN}"
echo "  Testing:     https://${TEST_DOMAIN}"
echo "  Admin:       https://${DOMAIN}/admin/"
echo "  POS:         https://${DOMAIN}/pos/"
echo "  n8n API:     https://${DOMAIN}/api/n8n/"
echo "  n8n (tuyo):  https://n8n.tailoringconsult.com"
echo ""
echo -e "${BLUE}Comandos útiles:${NC}"
echo "  Ver logs:    docker compose -f ${COMPOSE_FILE} logs -f erp-app-production"
echo "  Reiniciar:   docker compose -f ${COMPOSE_FILE} restart"
echo "  Estado:      docker compose -f ${COMPOSE_FILE} ps"
echo "  Backup BD:   docker compose -f ${COMPOSE_FILE} exec erp-db-production pg_dump -U erp_user erp_production > backup.sql"
echo ""
