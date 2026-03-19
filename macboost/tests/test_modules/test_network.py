"""Tests para el módulo Network."""

from unittest.mock import MagicMock, patch

import pytest

from macboost.core.undo import UndoEngine


@pytest.fixture
def network_module(tmp_path):
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    with patch("macboost.core.undo.SNAPSHOTS_DIR", snapshots):
        from macboost.modules.network import NetworkModule
        undo = UndoEngine()
        config = {
            "enabled": True,
            "dns_provider": "cloudflare",
            "custom_dns": [],
            "disable_ipv6": False,
        }
        return NetworkModule(config=config, undo_engine=undo)


def test_scan_returns_result(network_module):
    result = network_module.scan()
    assert result.module == "network"
    assert isinstance(result.issues, list)


def test_fix_preview_mode(network_module):
    result = network_module.fix(preview=True)
    assert result.preview_only is True
    for action in result.actions:
        assert action.get("preview") is True


def test_quick_fix_flushes_dns(network_module):
    with patch("macboost.modules.network.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0)
        result = network_module.quick_fix()
    assert result.module == "network"
    assert any("DNS" in a["detail"] for a in result.actions)


def test_dns_providers():
    from macboost.modules.network import DNS_PROVIDERS
    assert "cloudflare" in DNS_PROVIDERS
    assert "google" in DNS_PROVIDERS
    assert "quad9" in DNS_PROVIDERS
    assert DNS_PROVIDERS["cloudflare"] == ["1.1.1.1", "1.0.0.1"]
