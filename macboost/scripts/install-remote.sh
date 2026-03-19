#!/bin/bash
# ============================================================================
# MacBoost — Instalador Remoto
# Uso: curl -fsSL https://raw.githubusercontent.com/WerrySs/optimize-perfect-macbook/main/macboost/scripts/install-remote.sh | bash
# ============================================================================
set -e

BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

REPO="https://github.com/WerrySs/optimize-perfect-macbook.git"

echo ""
echo -e "${CYAN}${BOLD}  ⚡ MacBoost — Instalador${NC}"
echo -e "${DIM}  Optimización total para macOS en Apple Silicon${NC}"
echo ""

# ── Verificar macOS ──
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}  ✗ MacBoost solo funciona en macOS${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} macOS detectado ($(sw_vers -productVersion))"

# ── Verificar arquitectura ──
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    echo -e "  ${GREEN}✓${NC} Apple Silicon (arm64)"
else
    echo -e "  ${YELLOW}⚠${NC} Arquitectura: $ARCH (optimizado para Apple Silicon)"
fi

# ── Verificar Python ──
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version 2>&1)
    echo -e "  ${GREEN}✓${NC} $PY_VERSION"
else
    echo -e "${RED}  ✗ Python 3 no encontrado${NC}"
    echo ""
    echo -e "  Instálalo con:"
    echo -e "    ${CYAN}brew install python@3.12${NC}"
    exit 1
fi

# ── Verificar pip/pipx ──
USE_PIPX=false
if command -v pipx &> /dev/null; then
    echo -e "  ${GREEN}✓${NC} pipx disponible"
    USE_PIPX=true
elif command -v pip3 &> /dev/null; then
    echo -e "  ${GREEN}✓${NC} pip3 disponible"
else
    echo -e "${RED}  ✗ No se encontró pip3 ni pipx${NC}"
    echo ""
    echo -e "  Instala pipx con:"
    echo -e "    ${CYAN}brew install pipx && pipx ensurepath${NC}"
    exit 1
fi

# ── Verificar git ──
if ! command -v git &> /dev/null; then
    echo -e "${RED}  ✗ git no encontrado${NC}"
    exit 1
fi

echo ""
echo -e "${BOLD}  Instalando MacBoost...${NC}"
echo ""

# ── Clonar en temporal ──
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

echo -e "  ${DIM}[1/4]${NC} Descargando desde GitHub..."
if ! git clone --quiet --depth 1 "$REPO" "$TMPDIR/macboost-repo"; then
    echo -e "${RED}  ✗ Error descargando el repositorio${NC}"
    exit 1
fi

# ── Instalar ──
echo -e "  ${DIM}[2/4]${NC} Instalando paquete..."
cd "$TMPDIR/macboost-repo/macboost"

if $USE_PIPX; then
    if ! pipx install . --force; then
        echo -e "${RED}  ✗ Error instalando con pipx${NC}"
        exit 1
    fi
else
    if ! pip3 install --user --break-system-packages . 2>/dev/null && ! pip3 install --user . 2>/dev/null && ! pip3 install .; then
        echo -e "${RED}  ✗ Error instalando con pip${NC}"
        exit 1
    fi
fi

# ── Crear config ──
echo -e "  ${DIM}[3/4]${NC} Configurando..."
mkdir -p ~/.macboost/snapshots ~/.macboost/reports

# ── Verificar ──
echo -e "  ${DIM}[4/4]${NC} Verificando..."

# Buscar el binario
MACBOOST_BIN=""
if command -v macboost &> /dev/null; then
    MACBOOST_BIN="macboost"
elif [[ -f "$HOME/.local/bin/macboost" ]]; then
    MACBOOST_BIN="$HOME/.local/bin/macboost"
    export PATH="$HOME/.local/bin:$PATH"
fi

echo ""
if [[ -n "$MACBOOST_BIN" ]]; then
    echo -e "${GREEN}${BOLD}  ✓ MacBoost instalado correctamente${NC}"
    echo ""
    echo -e "  ${BOLD}Comandos:${NC}"
    echo -e "    ${CYAN}macboost scan --all${NC}       Escaneo completo del sistema"
    echo -e "    ${CYAN}macboost quick${NC}            Optimización rápida (RAM + DNS + tmp)"
    echo -e "    ${CYAN}macboost status${NC}           Ver Health Score"
    echo -e "    ${CYAN}macboost fix --all${NC}        Aplicar todas las optimizaciones"
    echo -e "    ${CYAN}macboost fix --all -p${NC}     Preview (ver qué se haría)"
    echo -e "    ${CYAN}macboost dashboard${NC}        Dashboard web en localhost:7777"
    echo -e "    ${CYAN}macboost top${NC}              Top procesos por RAM"
    echo -e "    ${CYAN}macboost agents${NC}           Listar Launch Agents"
    echo -e "    ${CYAN}macboost power -p performance${NC}  Cambiar perfil de energía"
    echo -e "    ${CYAN}macboost menubar start${NC}    Iniciar app en barra de menú"
    echo ""
    echo -e "  ${DIM}Config: ~/.macboost/config.toml${NC}"
    echo -e "  ${DIM}Desinstalar: curl -fsSL https://raw.githubusercontent.com/WerrySs/optimize-perfect-macbook/main/macboost/scripts/uninstall.sh | bash${NC}"
else
    echo -e "${GREEN}${BOLD}  ✓ MacBoost instalado${NC}"
    echo -e "${YELLOW}  ⚠ 'macboost' no encontrado en PATH${NC}"
    echo ""
    echo -e "  Añade esto a tu ~/.zshrc:"
    echo -e "    ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
    echo ""
    echo -e "  Luego ejecuta:"
    echo -e "    ${CYAN}source ~/.zshrc${NC}"
fi
echo ""
