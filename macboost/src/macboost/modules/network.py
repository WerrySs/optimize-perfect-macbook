"""Módulo Red & DNS — Optimización de red para máxima velocidad."""

from __future__ import annotations

import subprocess

from macboost.core.undo import UndoEntry
from macboost.modules.base import BaseModule, FixResult, ScanResult

DNS_PROVIDERS = {
    "cloudflare": ["1.1.1.1", "1.0.0.1"],
    "quad9": ["9.9.9.9", "149.112.112.112"],
    "google": ["8.8.8.8", "8.8.4.4"],
}


class NetworkModule(BaseModule):
    name = "network"
    description = "Red & DNS"
    priority = "alto"

    def scan(self) -> ScanResult:
        issues = []

        # Verificar DNS actual
        current_dns = self._get_current_dns()
        provider = self.config.get("dns_provider", "cloudflare")
        optimal_dns = self.config.get("custom_dns") or DNS_PROVIDERS.get(provider, DNS_PROVIDERS["cloudflare"])

        if current_dns != optimal_dns:
            issues.append({
                "type": "suboptimal_dns",
                "description": f"DNS actual: {current_dns or 'automático'} → recomendado: {optimal_dns}",
                "fixable": True,
                "severity": "medium",
            })

        # Probar latencia DNS
        latency = self._test_dns_latency()
        if latency and latency > 50:
            issues.append({
                "type": "high_dns_latency",
                "description": f"Latencia DNS alta: {latency:.0f}ms",
                "fixable": True,
                "severity": "medium" if latency < 100 else "high",
            })

        # IPv6 si está configurado para desactivar
        if self.config.get("disable_ipv6", False):
            ipv6_active = self._is_ipv6_active()
            if ipv6_active:
                issues.append({
                    "type": "ipv6_active",
                    "description": "IPv6 activo (configurado para desactivar)",
                    "fixable": True,
                    "severity": "low",
                })

        return ScanResult(
            module=self.name,
            issues=issues,
            status="warning" if issues else "ok",
            summary=f"Red: {len(issues)} optimizaciones disponibles",
        )

    def fix(self, preview: bool = False) -> FixResult:
        actions = []
        undo_commands = []

        # Configurar DNS optimizado
        provider = self.config.get("dns_provider", "cloudflare")
        target_dns = self.config.get("custom_dns") or DNS_PROVIDERS.get(provider, DNS_PROVIDERS["cloudflare"])
        current_dns = self._get_current_dns()
        service = self._get_active_service()

        if service and current_dns != target_dns:
            if not preview:
                try:
                    # Guardar DNS actual para undo
                    if current_dns:
                        undo_cmd = f"networksetup -setdnsservers '{service}' {' '.join(current_dns)}"
                    else:
                        undo_cmd = f"networksetup -setdnsservers '{service}' Empty"
                    undo_commands.append({"type": "shell", "command": undo_cmd})

                    dns_args = ["networksetup", "-setdnsservers", service] + target_dns
                    subprocess.run(dns_args, capture_output=True, check=True, timeout=10)
                    actions.append({"action": "set_dns", "detail": f"DNS configurado: {', '.join(target_dns)} ({provider})"})
                except subprocess.CalledProcessError as e:
                    actions.append({"action": "set_dns", "detail": f"Error configurando DNS: {e}", "skipped": True})
            else:
                actions.append({"action": "set_dns", "detail": f"Se configuraría DNS: {', '.join(target_dns)}", "preview": True})

        # Flush DNS cache
        if not preview:
            self._flush_dns()
            actions.append({"action": "flush_dns", "detail": "Caché DNS limpiada"})
        else:
            actions.append({"action": "flush_dns", "detail": "Se limpiaría caché DNS", "preview": True})

        # Desactivar IPv6 si configurado
        if self.config.get("disable_ipv6", False) and service:
            if not preview:
                try:
                    subprocess.run(
                        ["networksetup", "-setv6off", service],
                        capture_output=True, check=True, timeout=10,
                    )
                    undo_commands.append({"type": "shell", "command": f"networksetup -setv6automatic '{service}'"})
                    actions.append({"action": "disable_ipv6", "detail": "IPv6 desactivado"})
                except subprocess.CalledProcessError:
                    actions.append({"action": "disable_ipv6", "detail": "No se pudo desactivar IPv6", "skipped": True})
            else:
                actions.append({"action": "disable_ipv6", "detail": "Se desactivaría IPv6", "preview": True})

        if actions and not preview and undo_commands:
            self.undo.save(UndoEntry(
                module=self.name,
                action="optimize_network",
                description="Optimización de red y DNS",
                undo_commands=undo_commands,
            ))

        return FixResult(
            module=self.name,
            actions=actions,
            status="ok",
            summary=f"{len(actions)} optimizaciones de red {'previstas' if preview else 'aplicadas'}",
            preview_only=preview,
        )

    def quick_fix(self) -> FixResult:
        """Solo flush DNS."""
        self._flush_dns()
        return FixResult(
            module=self.name,
            actions=[{"action": "flush_dns", "detail": "Caché DNS limpiada"}],
            status="ok",
            summary="DNS flush completado",
        )

    def _get_active_service(self) -> str | None:
        try:
            result = subprocess.run(
                ["networksetup", "-listallnetworkservices"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.splitlines()[1:]:  # Skip header
                line = line.strip()
                if line.startswith("*"):
                    continue
                if "Wi-Fi" in line or "Ethernet" in line:
                    return line
            return None
        except Exception:
            return None

    def _get_current_dns(self) -> list[str] | None:
        service = self._get_active_service()
        if not service:
            return None
        try:
            result = subprocess.run(
                ["networksetup", "-getdnsservers", service],
                capture_output=True, text=True, timeout=10,
            )
            if "There aren't any DNS Servers" in result.stdout:
                return None
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except Exception:
            return None

    def _flush_dns(self):
        try:
            subprocess.run(["dscacheutil", "-flushcache"], capture_output=True, timeout=10)
            subprocess.run(["sudo", "-n", "killall", "-HUP", "mDNSResponder"], capture_output=True, timeout=10)
        except Exception:
            pass

    def _test_dns_latency(self) -> float | None:
        try:
            result = subprocess.run(
                ["ping", "-c", "3", "-t", "5", "1.1.1.1"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.splitlines():
                if "avg" in line:
                    parts = line.split("=")[-1].strip().split("/")
                    return float(parts[1])  # avg
            return None
        except Exception:
            return None

    def _is_ipv6_active(self) -> bool:
        service = self._get_active_service()
        if not service:
            return False
        try:
            result = subprocess.run(
                ["networksetup", "-getinfo", service],
                capture_output=True, text=True, timeout=10,
            )
            return "IPv6:" in result.stdout and "off" not in result.stdout.lower()
        except Exception:
            return False
