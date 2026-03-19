# ⚡ MacBoost

**Herramienta de optimización total para macOS en Apple Silicon.**

Cada byte cuenta, cada proceso importa.

## Instalación rápida

```bash
curl -fsSL https://raw.githubusercontent.com/WerrySs/optimize-perfect-macbook/main/macboost/scripts/install-remote.sh | bash
```

O con pipx:

```bash
pipx install git+https://github.com/WerrySs/optimize-perfect-macbook.git#subdirectory=macboost
```

## Uso

```bash
macboost scan --all          # Escaneo completo del sistema
macboost quick               # Optimización rápida (RAM + DNS + tmp)
macboost status              # Ver Health Score
macboost fix --all           # Aplicar todas las optimizaciones
macboost fix --all --preview # Ver qué se haría sin ejecutar
macboost dashboard           # Dashboard web en localhost:7777
macboost top                 # Top procesos por consumo de RAM
macboost agents              # Listar Launch Agents
macboost health              # Health Score detallado
macboost power --profile performance  # Cambiar perfil de energía
macboost menubar start       # Iniciar app en barra de menú
macboost undo                # Revertir última operación
macboost undo --list         # Ver historial de cambios
```

## Módulos

| Módulo | Descripción | Prioridad |
|--------|-------------|-----------|
| RAM & Procesos | Kill zombies, purge, detección memory leaks | Crítico |
| Almacenamiento | Cachés, Xcode, Homebrew, npm, Docker, logs | Crítico |
| Launch Agents | Auditoría y toggle de servicios de inicio | Alto |
| Red & DNS | DNS optimizados, flush, MTU, IPv6 | Alto |
| UI & Animaciones | Tweaks Dock, transparencias, motion | Medio |
| Energía & Thermal | Perfiles Low Power / Balanced / Performance | Medio |
| Health Monitor | Métricas, Health Score (0-100), reportes | Automático |

## Dashboard Web

```bash
macboost dashboard
```

Abre un dashboard en `localhost:7777` con:
- Métricas en tiempo real (CPU, RAM, SSD, batería)
- Gráficas con Chart.js
- Acciones rápidas (scan, fix, optimize)
- WebSocket para actualizaciones en vivo

## Configuración

Edita `~/.macboost/config.toml` para personalizar comportamiento, umbrales, DNS, whitelists y más.

## Seguridad

- Nunca se desactiva SIP
- Todo cambio tiene undo
- Nunca se ejecuta sin confirmación
- Whitelist por defecto para procesos del sistema
- Sin telemetría — 100% local

## Desinstalar

```bash
curl -fsSL https://raw.githubusercontent.com/WerrySs/optimize-perfect-macbook/main/macboost/scripts/uninstall.sh | bash
```

## License

MIT
