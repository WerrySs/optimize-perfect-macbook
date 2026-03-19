#!/bin/bash
# MacBoost — Script de instalación
set -e

BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}⚡ MacBoost — Instalador${NC}"
echo ""

# Verificar macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}Error: MacBoost solo funciona en macOS${NC}"
    exit 1
fi

# Verificar Apple Silicon
ARCH=$(uname -m)
if [[ "$ARCH" != "arm64" ]]; then
    echo -e "${YELLOW}Aviso: MacBoost está optimizado para Apple Silicon (arm64). Arquitectura detectada: $ARCH${NC}"
fi

# Verificar Python 3.12+
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 no encontrado. Instálalo con: brew install python@3.12${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED="3.12"
if [[ "$(printf '%s\n' "$REQUIRED" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED" ]]; then
    echo -e "${YELLOW}Aviso: Se recomienda Python >= 3.12. Versión actual: $PYTHON_VERSION${NC}"
fi

echo -e "${BOLD}1/4${NC} Verificando dependencias..."

# Instalar con pipx si está disponible, sino pip
if command -v pipx &> /dev/null; then
    echo -e "${BOLD}2/4${NC} Instalando con pipx..."
    pipx install .
elif command -v pip3 &> /dev/null; then
    echo -e "${BOLD}2/4${NC} Instalando con pip..."
    pip3 install --user .
else
    echo -e "${RED}Error: No se encontró pip3 ni pipx${NC}"
    exit 1
fi

echo -e "${BOLD}3/4${NC} Creando configuración por defecto..."
mkdir -p ~/.macboost/snapshots ~/.macboost/reports

# Generar config por defecto si no existe
if [[ ! -f ~/.macboost/config.toml ]]; then
    python3 -c "from macboost.core.config import ConfigManager; ConfigManager()" 2>/dev/null || true
fi

echo -e "${BOLD}4/4${NC} Verificando instalación..."
if command -v macboost &> /dev/null; then
    echo ""
    echo -e "${GREEN}${BOLD}✓ MacBoost instalado correctamente${NC}"
    echo ""
    echo -e "  Comandos disponibles:"
    echo -e "    ${CYAN}macboost scan --all${NC}     Escanear sistema completo"
    echo -e "    ${CYAN}macboost quick${NC}          Optimización rápida"
    echo -e "    ${CYAN}macboost status${NC}         Ver estado de salud"
    echo -e "    ${CYAN}macboost dashboard${NC}      Abrir dashboard web"
    echo -e "    ${CYAN}macboost menubar start${NC}  Iniciar menu bar app"
    echo ""
    echo -e "  Configuración: ${YELLOW}~/.macboost/config.toml${NC}"
else
    echo -e "${YELLOW}MacBoost instalado pero no encontrado en PATH.${NC}"
    echo -e "Asegúrate de que ~/.local/bin esté en tu PATH."
fi
