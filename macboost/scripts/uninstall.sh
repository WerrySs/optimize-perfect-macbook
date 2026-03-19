#!/bin/bash
# MacBoost — Script de desinstalación
set -e

BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}⚡ MacBoost — Desinstalador${NC}"
echo ""

# Detener menu bar app si está corriendo
echo -e "${BOLD}1/3${NC} Deteniendo procesos de MacBoost..."
pkill -f "macboost.menubar" 2>/dev/null || true
pkill -f "macboost.dashboard" 2>/dev/null || true

# Desinstalar paquete
echo -e "${BOLD}2/3${NC} Desinstalando paquete..."
if command -v pipx &> /dev/null; then
    pipx uninstall macboost 2>/dev/null || true
else
    pip3 uninstall macboost -y 2>/dev/null || true
fi

# Preguntar sobre datos de usuario
echo ""
read -p "¿Eliminar configuración y datos (~/.macboost)? [s/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    echo -e "${BOLD}3/3${NC} Eliminando datos de usuario..."
    rm -rf ~/.macboost
    echo -e "${GREEN}✓ Datos eliminados${NC}"
else
    echo -e "${BOLD}3/3${NC} Datos conservados en ~/.macboost"
fi

echo ""
echo -e "${GREEN}${BOLD}✓ MacBoost desinstalado${NC}"
