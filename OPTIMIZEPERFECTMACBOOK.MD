# MacBoost — Plan de Desarrollo

> Herramienta de optimización total para macOS en Apple Silicon.  
> Cada byte cuenta, cada proceso importa.

---

## 1. Visión General

**MacBoost** es una herramienta nativa de macOS que vive en la **barra de menú** (menu bar) como un icono persistente — al estilo de DisplayLink Manager, iStat Menus o Bartender. Desde ahí, el usuario puede:

- Ver el estado de salud del sistema de un vistazo (CPU, RAM, SSD, batería, temperatura).
- Ejecutar optimizaciones con un solo clic.
- Acceder al dashboard web completo.
- Recibir alertas cuando algo requiere atención.

La herramienta también incluye una **CLI** completa para usuarios avanzados y automatización.

---

## 2. Interfaz: Menu Bar App

### 2.1 Icono en la Barra de Menú

El icono principal de MacBoost aparece en la zona superior derecha de macOS junto al resto de iconos del sistema (Wi-Fi, batería, reloj, etc.).

**Estados del icono:**

| Estado | Icono | Descripción |
|--------|-------|-------------|
| Todo OK | ⚡ (verde) | Sistema optimizado, sin problemas |
| Atención | ⚡ (amarillo) | Hay optimizaciones recomendadas |
| Crítico | ⚡ (rojo) | RAM alta, disco lleno, o throttling térmico |
| Escaneando | ⚡ (animado) | Escaneo en progreso |

### 2.2 Popover / Dropdown Principal

Al hacer clic en el icono se despliega un panel (popover nativo de macOS) con la siguiente estructura:

```
┌──────────────────────────────────────┐
│  ⚡ MacBoost              Score: 87  │
├──────────────────────────────────────┤
│                                      │
│  CPU   ████████░░░░  38%    42°C     │
│  RAM   ██████████░░  78%    12.4 GB  │
│  SSD   ████░░░░░░░░  34%    342 GB   │
│  BAT   ████████████  96%    127 cyc  │
│                                      │
├──────────────────────────────────────┤
│  ▶ Optimización Rápida               │
│  ▶ Escanear Sistema                  │
│  ▶ Limpiar Almacenamiento            │
│  ▶ Gestionar Launch Agents           │
├──────────────────────────────────────┤
│  ⚙ Preferencias   📊 Dashboard Web  │
│  ↺ Último undo disponible            │
│                                      │
│  MacBoost v1.0.0         ■ Salir     │
└──────────────────────────────────────┘
```

**Secciones del popover:**

1. **Header** — Nombre + Health Score global (0–100).
2. **Métricas rápidas** — Barras de progreso en tiempo real para CPU, RAM, SSD y batería con valores numéricos y temperatura/ciclos.
3. **Acciones rápidas** — Botones para las operaciones más comunes. Cada acción muestra un loading inline y resultado (ej: "Liberados 2.3 GB").
4. **Footer** — Acceso a preferencias, dashboard web (abre navegador en `localhost:7777`), undo del último cambio, y botón de salir.

### 2.3 Submenús Contextuales

Cada acción rápida puede expandirse con un hover o clic en la flecha:

- **Optimización Rápida** → Purge RAM + Flush DNS + Limpiar /tmp (todo en <10s)
- **Escanear Sistema** → Escaneo completo de los 7 módulos con reporte
- **Limpiar Almacenamiento** → Muestra preview del espacio recuperable antes de ejecutar
- **Gestionar Launch Agents** → Lista de agents activos con toggle on/off

### 2.4 Notificaciones del Sistema

MacBoost envía notificaciones nativas de macOS (NSUserNotification / UNUserNotificationCenter) cuando:

- El uso de RAM supera el 90% sostenido por más de 5 minutos.
- El SSD tiene menos del 10% de espacio libre.
- Se detecta throttling térmico en el SoC.
- Se completa una limpieza automática programada.
- Hay actualizaciones disponibles de MacBoost.

---

## 3. Módulos de Optimización

MacBoost se divide en **7 módulos independientes** que pueden ejecutarse individualmente o en conjunto. Cada módulo tiene modo **preview** (muestra qué hará) y **undo** (revierte cambios).

### 3.1 🧠 RAM & Procesos — `CRÍTICO`

Monitoreo en tiempo real de memoria. Detecta y mata procesos zombie, apps con memory leaks, y agentes de fondo innecesarios.

**Acciones:**

- Listar procesos por consumo de RAM (top 20).
- Detectar procesos zombie y matarlos.
- Purge de RAM comprimida del sistema.
- Identificar apps con memory leaks (crecimiento sostenido > umbral).
- Matar agentes de fondo no esenciales (con whitelist configurable).

**Herramientas del sistema:** `ps aux`, `purge`, `kill`, `vm_stat`, `memory_pressure`

### 3.2 💾 Limpieza de Almacenamiento — `CRÍTICO`

Eliminación segura de cachés, logs, temporales y datos huérfanos.

**Targets de limpieza:**

| Categoría | Ruta / Comando | Impacto típico |
|-----------|----------------|----------------|
| Cachés de usuario | `~/Library/Caches/*` | 2–15 GB |
| Xcode DerivedData | `~/Library/Developer/Xcode/DerivedData` | 5–50 GB |
| Homebrew | `brew cleanup --prune=all` | 1–5 GB |
| npm/yarn cache | `npm cache clean --force` | 0.5–3 GB |
| pip cache | `pip cache purge` | 0.2–2 GB |
| Docker | `docker system prune -af` | 5–50 GB |
| Logs del sistema | `/var/log/*`, `~/Library/Logs/*` | 0.5–3 GB |
| APFS snapshots | `tmutil deletelocalsnapshots` | 10–100 GB |
| Apps huérfanas | Detecta datos de apps desinstaladas | Variable |
| Archivos .DS_Store | `find / -name ".DS_Store" -delete` | Mínimo |

**Seguridad:** Antes de eliminar, se muestra un desglose exacto de qué se va a borrar y cuánto espacio se recupera. Nunca se borra sin confirmación.

### 3.3 🚀 Arranque & Launch Agents — `ALTO`

Auditoría completa de servicios que se cargan al inicio del sistema.

**Acciones:**

- Listar todos los Launch Agents (usuario y sistema).
- Listar todos los Launch Daemons activos.
- Clasificar cada uno como: esencial del sistema / app conocida / sospechoso / innecesario.
- Toggle para habilitar/deshabilitar cada agent sin eliminarlo.
- Whitelist/blacklist persistente en configuración.
- Listar y gestionar Login Items de aplicaciones.

**Rutas escaneadas:**

```
~/Library/LaunchAgents/
/Library/LaunchAgents/
/Library/LaunchDaemons/
/System/Library/LaunchAgents/    (solo lectura, informativo)
/System/Library/LaunchDaemons/   (solo lectura, informativo)
```

**Herramientas del sistema:** `launchctl`, `osascript`

### 3.4 🌐 Red & DNS — `ALTO`

Optimización de configuración de red para máxima velocidad y mínima latencia.

**Acciones:**

- Configurar DNS optimizados (Cloudflare `1.1.1.1` / Quad9 `9.9.9.9` / Google `8.8.8.8`).
- Flush de caché DNS (`dscacheutil -flushcache` + `killall -HUP mDNSResponder`).
- Optimización de MTU (testeo automático del valor óptimo).
- Desactivar IPv6 si no se usa (reduce latencia en algunas redes).
- Limpiar perfiles de red Wi-Fi obsoletos.
- Resetear stack de red completo si hay problemas.

**Herramientas del sistema:** `networksetup`, `dscacheutil`, `sysctl`, `ifconfig`, `ping`

### 3.5 🎨 UI & Animaciones — `MEDIO`

Reducción del overhead visual de macOS para máxima fluidez.

**Tweaks disponibles (todos reversibles):**

```bash
# Dock: autohide instantáneo sin delay
defaults write com.apple.dock autohide-delay -float 0
defaults write com.apple.dock autohide-time-modifier -float 0.3

# Dock: sin animación de bounce al abrir apps
defaults write com.apple.dock launchanim -bool false

# Finder: sin animaciones de ventana
defaults write com.apple.finder DisableAllAnimations -bool true

# Reducir transparencias del sistema
defaults write com.apple.universalaccess reduceTransparency -bool true

# Reducir motion (animaciones del sistema)
defaults write com.apple.universalaccess reduceMotion -bool true

# Abrir/guardar diálogos: expandidos por defecto
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode -bool true

# Mostrar extensiones de archivo siempre
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# Screenshots: formato optimizado (HEIC en vez de PNG)
defaults write com.apple.screencapture type -string "heic"

# Deshabilitar widgets del centro de notificaciones
# (reduce procesos en background)
```

### 3.6 🔋 Energía & Thermal — `MEDIO`

Perfiles de rendimiento y control de servicios que consumen energía innecesariamente.

**Perfiles predefinidos:**

| Perfil | Spotlight | Time Machine | Power Nap | Turbo Boost | Uso ideal |
|--------|-----------|--------------|-----------|-------------|-----------|
| Low Power | OFF | Pausado | OFF | OFF | Batería, viajes |
| Balanced | ON (throttled) | Normal | ON | Auto | Uso diario |
| Performance | ON | Pausado | OFF | Forzado | Gaming, renders, compilación |

**Acciones:**

- Cambiar perfil con un clic desde el menu bar.
- Control de Spotlight indexing (`mdutil -i off /Volumes/...`).
- Pausar/reanudar Time Machine (`tmutil disable/enable`).
- Monitoreo de throttling térmico en tiempo real (`powermetrics`).
- Mostrar watts consumidos por proceso.

**Herramientas del sistema:** `pmset`, `mdutil`, `tmutil`, `powermetrics`, `caffeinate`

### 3.7 📊 Health Monitor — `AUTOMATIZADO`

Dashboard de salud del sistema con métricas persistentes y reportes automáticos.

**Métricas recopiladas:**

- **CPU:** Uso por core (E-cores vs P-cores), frecuencia, procesos top.
- **RAM:** Presión de memoria, RAM comprimida, swap usage, wired/active/inactive.
- **SSD:** Espacio libre, salud SMART, data written (TBW), velocidad R/W.
- **Batería:** Ciclos de carga, capacidad máxima vs diseño, estado de salud, temperatura.
- **Temperatura:** SoC, GPU, SSD, ambient.
- **Red:** Velocidad actual, latencia DNS, paquetes perdidos.

**Health Score (0–100):**

El score se calcula ponderando cada métrica:

```
Score = (RAM_score × 0.25) + (CPU_score × 0.20) + (SSD_score × 0.20)
      + (Boot_score × 0.15) + (Network_score × 0.10) + (Battery_score × 0.10)
```

**Reportes:**

- Reporte semanal automático en HTML (guardado en `~/.macboost/reports/`).
- Historial de métricas para ver tendencias.
- Alertas cuando métricas superan umbrales configurables.

---

## 4. Arquitectura Técnica

### 4.1 Diagrama de Capas

```
╔════════════════════════════════════════════════════════════════╗
║                    CAPA DE INTERFAZ                            ║
║                                                                ║
║   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐  ║
║   │  Menu Bar    │   │   CLI        │   │  Web Dashboard   │  ║
║   │  (rumps/     │   │  (Typer +    │   │  (localhost:7777) │  ║
║   │   PyObjC)    │   │   Rich)      │   │  FastAPI + HTML  │  ║
║   └──────┬───────┘   └──────┬───────┘   └────────┬─────────┘  ║
╠══════════╪══════════════════╪════════════════════╪═════════════╣
║          └──────────────────┼────────────────────┘             ║
║                    CORE ENGINE                                 ║
║                                                                ║
║   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐  ║
║   │ Orchestrator │◄──│Module Loader  │──►│  Config Manager  │  ║
║   └──────┬───────┘   └──────────────┘   │  (~/.macboost/)   │  ║
║          │           ┌──────────────┐   └──────────────────┘  ║
║          ├──────────►│ Undo Engine  │                          ║
║          │           │ (snapshots)  │                          ║
║          │           └──────────────┘                          ║
╠══════════╪═════════════════════════════════════════════════════╣
║          │       MÓDULOS DE OPTIMIZACIÓN                       ║
║          │                                                     ║
║   ┌──────┴──────────────────────────────────────────────────┐  ║
║   │  RAM  │ Storage │ Boot │ Network │ UI │ Power │ Health  │  ║
║   └──────┬──────────────────────────────────────────────────┘  ║
╠══════════╪═════════════════════════════════════════════════════╣
║          │          CAPA DEL SISTEMA                           ║
║          ▼                                                     ║
║   ┌─────────────────────────────────────────────────────────┐  ║
║   │  Shell (subprocess)  │  defaults write  │  launchctl    │  ║
║   │  sysctl  │  pmset  │  mdutil  │  networksetup  │ ioreg  │  ║
║   └─────────────────────────────────────────────────────────┘  ║
╚════════════════════════════════════════════════════════════════╝
```

### 4.2 Estructura del Proyecto

```
macboost/
├── pyproject.toml              # Metadata, dependencias, entry points
├── README.md
├── LICENSE
│
├── src/
│   └── macboost/
│       ├── __init__.py
│       ├── main.py             # Entry point principal
│       │
│       ├── core/
│       │   ├── orchestrator.py # Coordina ejecución de módulos
│       │   ├── config.py       # Lee/escribe ~/.macboost/config.toml
│       │   ├── undo.py         # Undo Engine con snapshots JSON
│       │   ├── scanner.py      # Runner genérico de escaneos
│       │   └── health.py       # Cálculo del Health Score
│       │
│       ├── modules/
│       │   ├── base.py         # Clase base abstracta para módulos
│       │   ├── ram.py          # Módulo RAM & Procesos
│       │   ├── storage.py      # Módulo Limpieza de Almacenamiento
│       │   ├── boot.py         # Módulo Arranque & Launch Agents
│       │   ├── network.py      # Módulo Red & DNS
│       │   ├── ui.py           # Módulo UI & Animaciones
│       │   ├── power.py        # Módulo Energía & Thermal
│       │   └── monitor.py      # Módulo Health Monitor
│       │
│       ├── cli/
│       │   ├── app.py          # CLI con Typer
│       │   └── formatters.py   # Output con Rich (tablas, barras, colores)
│       │
│       ├── menubar/
│       │   ├── app.py          # Menu bar app (rumps + PyObjC)
│       │   ├── popover.py      # Contenido del popover
│       │   └── icons/          # Iconos SVG/PNG para cada estado
│       │
│       └── dashboard/
│           ├── server.py       # FastAPI backend
│           ├── api.py          # REST endpoints
│           ├── websocket.py    # WebSocket para métricas real-time
│           └── static/
│               └── index.html  # Dashboard single-page (Alpine.js + Chart.js)
│
├── tests/
│   ├── test_modules/
│   ├── test_core/
│   └── test_cli/
│
└── scripts/
    ├── install.sh              # Instalador para Homebrew
    └── uninstall.sh            # Desinstalador limpio
```

### 4.3 Configuración del Usuario

Archivo: `~/.macboost/config.toml`

```toml
[general]
auto_scan_interval = "6h"       # Intervalo de escaneo automático
notifications = true             # Notificaciones del sistema
health_report = "weekly"         # Frecuencia del reporte (daily/weekly/off)
theme = "auto"                   # Menu bar theme (auto/light/dark)

[modules.ram]
enabled = true
kill_threshold_mb = 500          # Matar procesos con leak > 500 MB
whitelist = ["Finder", "Dock", "WindowServer"]

[modules.storage]
enabled = true
auto_clean_caches = false        # No limpiar cachés sin pedir
xcode_derived = true
homebrew = true
npm = true
docker = true

[modules.boot]
enabled = true
blacklist = [
    "com.adobe.AdobeCreativeCloud",
    "com.spotify.client.startuphelper",
]

[modules.network]
enabled = true
dns_provider = "cloudflare"      # cloudflare / quad9 / google / custom
custom_dns = []
disable_ipv6 = false

[modules.ui]
enabled = true
instant_dock = true
reduce_transparency = false
reduce_motion = false

[modules.power]
default_profile = "balanced"     # lowpower / balanced / performance

[modules.health]
enabled = true
alert_ram_percent = 90
alert_ssd_percent = 90
alert_temp_celsius = 95
```

---

## 5. CLI — Referencia de Comandos

### 5.1 Comandos Principales

```bash
# Escanear todo el sistema
macboost scan --all

# Escanear un módulo específico
macboost scan --module ram
macboost scan --module storage
macboost scan --module boot
macboost scan --module network

# Aplicar todas las optimizaciones recomendadas
macboost fix --all

# Preview: ver qué se haría sin ejecutar nada
macboost fix --all --preview

# Optimización rápida (RAM + Cache temporal + DNS flush)
macboost quick

# Ver estado de salud del sistema
macboost status

# Abrir dashboard web en el navegador
macboost dashboard

# Iniciar/detener la menu bar app
macboost menubar start
macboost menubar stop
```

### 5.2 Undo y Historial

```bash
# Revertir la última optimización
macboost undo

# Ver historial de cambios
macboost undo --list

# Revertir un cambio específico por ID
macboost undo --id abc123
```

### 5.3 Perfiles de Energía

```bash
# Cambiar perfil
macboost power --profile performance
macboost power --profile balanced
macboost power --profile lowpower

# Ver perfil actual
macboost power --status
```

### 5.4 Automatización

```bash
# Ejecutar optimización rápida cada 6 horas
macboost auto --interval 6h

# Detener automatización
macboost auto --stop

# Ver siguiente ejecución programada
macboost auto --status
```

---

## 6. Tech Stack

| Componente | Tecnología | Justificación |
|------------|-----------|---------------|
| Core / Backend | Python 3.12+ | Acceso directo a subprocess, psutil, shutil. Rápido de desarrollar y mantener. |
| CLI | Typer + Rich | Autocompletado, validación, output bonito con tablas y colores. |
| Menu Bar App | rumps + PyObjC | Framework ligero para menu bar apps nativas en macOS. Usa el NSStatusBar real del sistema. |
| Dashboard Backend | FastAPI + Uvicorn | API REST ultra rápida, async, WebSocket nativo para métricas en tiempo real. |
| Dashboard Frontend | Alpine.js + Chart.js | Ligero, sin build step, reactivo. Todo en un solo HTML. |
| Configuración | TOML | Legible, editable a mano, estándar en Python. |
| Undo Engine | JSON snapshots | Un archivo JSON por operación con el estado anterior para restauración. |
| Distribución | Homebrew + pipx | `brew install macboost` o `pipx install macboost`. Sin dependencias externas pesadas. |
| Testing | pytest + pytest-mock | Tests unitarios para cada módulo con mocks de subprocess. |

### Lo que NO usamos y por qué

- **Electron** — Usa más RAM de la que estamos intentando liberar.
- **Swift/SwiftUI** — Overkill para system tuning; Python es más rápido de iterar.
- **Docker** — No tiene sentido containerizar algo que necesita acceso directo al host.
- **Tauri** — Buena opción, pero añade complejidad innecesaria para una herramienta que no necesita un webview completo.

---

## 7. Seguridad y Principios

### 7.1 Reglas Inquebrantables

1. **Nunca se desactiva SIP** (System Integrity Protection). Todas las optimizaciones se hacen dentro de los permisos normales del sistema.
2. **Nunca se ejecuta nada sin confirmación explícita** en modo interactivo. El modo `--preview` existe para ver antes de actuar.
3. **Todo cambio tiene undo.** El Undo Engine guarda un snapshot JSON antes de cada operación con el estado original para restauración instantánea.
4. **Whitelist por defecto.** Los procesos críticos del sistema nunca se tocan. Solo se actúa sobre lo que está explícitamente identificado como seguro.
5. **Sin telemetría.** MacBoost no envía ningún dato a ningún servidor. Todo es 100% local.

### 7.2 Permisos Requeridos

| Permiso | Cuándo | Para qué |
|---------|--------|----------|
| Acceso completo al disco | Instalación | Leer cachés y logs del sistema |
| Notificaciones | Primera ejecución | Alertas de salud del sistema |
| sudo (puntual) | Operaciones específicas | `purge`, `dscacheutil`, `pmset` |

---

## 8. Roadmap de Desarrollo

### Semana 1 — Fundamentos

- Scaffold del proyecto con `pyproject.toml` y estructura modular.
- Core Engine: Orchestrator, Module Loader, Config Manager, Undo Engine.
- CLI base con Typer: `macboost scan`, `macboost fix`, `macboost status`.
- Clase base abstracta para módulos con interfaz estándar.

### Semana 2 — Módulos Críticos

- Módulo RAM: scanner de procesos, purge inteligente, kill de zombies.
- Módulo Storage: limpieza de cachés con preview de espacio recuperable.
- Módulo Boot: auditor de LaunchAgents/Daemons con whitelist/blacklist.
- Tests unitarios para los tres módulos.

### Semana 3 — Módulos Secundarios

- Módulo Network: DNS optimizer, MTU tuning, flush automático.
- Módulo UI: tweaks de dock, animaciones, transparencias.
- Módulo Power: perfiles de energía, control de Spotlight y Time Machine.
- Modo `--preview` implementado en todos los módulos.

### Semana 4 — Health Monitor + Menu Bar

- Collector de métricas: CPU, RAM, SSD, batería, temperatura.
- Cálculo del Health Score (0–100).
- **Menu bar app** con rumps/PyObjC: icono, popover con métricas, acciones rápidas.
- Notificaciones nativas del sistema.

### Semana 5 — Web Dashboard

- Backend API con FastAPI (`localhost:7777`).
- WebSocket para métricas en tiempo real.
- Frontend con Alpine.js + Chart.js: gráficas, controles, historial.
- Integración bidireccional: CLI ↔ Menu Bar ↔ Dashboard.

### Semana 6 — Polish & Release

- Testing en M1, M2, M3, M4.
- Fórmula de Homebrew para instalación.
- Manpage y `--help` detallado para cada comando.
- README con screenshots y GIFs.
- Auto-updater para futuras versiones.

---

## 9. Instalación Objetivo

```bash
# Opción 1: Homebrew (recomendado)
brew tap macboost/tap
brew install macboost

# Opción 2: pipx
pipx install macboost

# Post-instalación: iniciar menu bar app
macboost menubar start

# Primera ejecución: escaneo completo
macboost scan --all
```

---

## 10. Inspiración y Referencias

- **iStat Menus** — Referencia para el diseño del popover y métricas en menu bar.
- **DisplayLink Manager** — Modelo de menu bar app limpia y funcional (ver screenshot de referencia).
- **OnyX** — Referencia de optimizaciones de macOS disponibles.
- **CleanMyMac** — Referencia de UX para limpieza de almacenamiento (pero sin el bloat).
- **Homebrew** — Modelo de distribución CLI para macOS.

---

*MacBoost v1.0 — Diseñado para Apple Silicon, construido para velocidad.*