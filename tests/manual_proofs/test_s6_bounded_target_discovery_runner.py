from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from telethon import utils
from telethon.tl.types import PeerChannel
from tools.manual_proofs import s6_bounded_target_discovery as proof

from telegram_courses.auth import AuthState
from telegram_courses.message_scanner import ScanGatewayError
from telegram_courses.telethon_gateway import S6_PEER_RECOVERY_REASONS


@pytest.fixture(autouse=True)
def _use_synthetic_proof_identity(monkeypatch):
    monkeypatch.setattr(
        proof, "CHANNEL_ID", utils.get_peer_id(PeerChannel(424242))
    )
    monkeypatch.setattr(
        proof, "EXECUTE_CONFIRMATION", "synthetic-confirmation"
    )


def test_copy_peer_recovery_reason_is_allowlisted():
    report = {}
    gateway = SimpleNamespace(_metadata_peer_recovery_reason="PEER_RESOLVED")
    proof._copy_peer_recovery_reason(report, gateway, S6_PEER_RECOVERY_REASONS)
    assert report["peer_resolution_reason"] == "PEER_RESOLVED"
    gateway._metadata_peer_recovery_reason = "synthetic-sensitive-sentinel"
    proof._copy_peer_recovery_reason(report, gateway, S6_PEER_RECOVERY_REASONS)
    assert report["peer_resolution_reason"] is None


def test_execute_runner_stops_on_session_failure_without_login_or_rpc(
    monkeypatch, capsys
):
    class Vault:
        def _existing_blob(self):
            return True

    class Gateway:
        def __init__(self, *_args, **_kwargs):
            self.restore_calls = 0
            self.close_calls = 0

        async def restore(self):
            self.restore_calls += 1
            raise ScanGatewayError("SESSION_INVALID")

        async def close(self):
            self.close_calls += 1

        async def begin(self, _phone):
            raise AssertionError("login must never be attempted")

        async def recover_selected_channel_peer(self, *_args, **_kwargs):
            raise AssertionError("RPC must not run after restore failure")

    instance = None

    def gateway_factory(*args, **kwargs):
        nonlocal instance
        instance = Gateway(*args, **kwargs)
        return instance

    monkeypatch.setenv("S6_BOUNDED_TARGET_CONFIRMATION", proof.EXECUTE_CONFIRMATION)
    import telegram_courses.config as config
    import telegram_courses.telethon_gateway as gateway_module

    monkeypatch.setattr(config, "load_telegram_credentials", lambda **_kwargs: object())
    monkeypatch.setattr(gateway_module, "_ProtectedSessionVault", Vault)
    monkeypatch.setattr(gateway_module, "TelethonGateway", gateway_factory)

    code = asyncio.run(proof._execute())
    output = json.loads(capsys.readouterr().out)
    assert code == 2
    assert output["status"] == "SESSION_INVALID"
    assert instance.restore_calls == 1
    assert instance.close_calls == 1


def test_execute_runner_reports_final_metadata_history_counters(monkeypatch, capsys):
    class Vault:
        def _existing_blob(self):
            return True

    class Gateway:
        def __init__(self, *_args, **_kwargs):
            self._metadata_dialog_rpcs = 0
            self._metadata_dialogs_inspected = 0
            self._metadata_message_rpcs = 0
            self._metadata_messages_inspected = 0
            self._metadata_peer_recovery_reason = None

        async def restore(self):
            return AuthState.AUTHENTICATED

        async def recover_selected_channel_peer(self, *_args, **_kwargs):
            self._metadata_dialog_rpcs = 1
            self._metadata_dialogs_inspected = 100
            self._metadata_peer_recovery_reason = "PEER_RESOLVED"
            return True

        async def iter_channel_metadata(self, *_args, **_kwargs):
            self._metadata_message_rpcs = 2
            self._metadata_messages_inspected = 7
            yield SimpleNamespace(media=[])

        async def close(self):
            return None

    monkeypatch.setenv("S6_BOUNDED_TARGET_CONFIRMATION", proof.EXECUTE_CONFIRMATION)
    import telegram_courses.config as config
    import telegram_courses.telethon_gateway as gateway_module

    monkeypatch.setattr(config, "load_telegram_credentials", lambda **_kwargs: object())
    monkeypatch.setattr(gateway_module, "_ProtectedSessionVault", Vault)
    monkeypatch.setattr(gateway_module, "TelethonGateway", Gateway)

    assert asyncio.run(proof._execute()) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "METADATA_COMPLETE"
    assert output["dialog_rpcs"] == 1
    assert output["dialogs_inspected"] == 100
    assert output["metadata_rpcs"] == 2
    assert output["messages_inspected"] == 7
    assert output["peer_resolution_reason"] == "PEER_RESOLVED"


def test_execute_runner_without_confirmation_does_not_load_gateway(monkeypatch, capsys):
    monkeypatch.delenv("S6_BOUNDED_TARGET_CONFIRMATION", raising=False)
    assert asyncio.run(proof._execute()) == 2
    assert "no session restore or RPC" in capsys.readouterr().out


