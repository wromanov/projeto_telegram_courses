from __future__ import annotations

import asyncio
import hashlib
import io
import os
import re
from pathlib import Path

import pytest

from telegram_courses.s9_g0_confirmation import (
    G0ConfirmationError,
    request_g0_confirmation,
)
from telegram_courses.s9_operational_ledger import S9OperationalLedger
from telegram_courses.s9_real_gate_producers import (
    canonical_bytes,
    collect_g1_evidence,
    g1_worker_main,
    load_approved_manifest,
    read_validated_gate_receipt,
    sha256_bytes,
)
from telegram_courses.s9_supervisor_cli import start_supervised_run

pytestmark = pytest.mark.skipif(os.name != "nt", reason="S9 private-run validation is Windows-specific")

CHANNEL_ID = -1000000000123


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def _manifest() -> dict[str, object]:
    scope = {"target_alias": "SYNTHETIC_RASMOO"}
    return {
        "schema_version": 1,
        "channel_id": CHANNEL_ID,
        "channel_alias": "SYNTHETIC_CHANNEL",
        "scope": scope,
        "hierarchy": {"TRACK": 1, "COURSE": 2, "MODULE": 2},
        "unresolved_count": 0,
        "scope_approval": {
            "decision": "APPROVED",
            "confirmation_source": "G0_HUMAN_CONFIRMATION",
            "scope_sha256": sha256_bytes(canonical_bytes(scope)),
        },
    }


def _start_run(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    context = start_supervised_run(tmp_path / "run")
    manifest = _manifest()
    (context.run_directory / "approved-manifest.json").write_bytes(
        canonical_bytes(manifest) + b"\n",
    )
    loaded, manifest_sha256, scope_sha256 = load_approved_manifest(
        context.run_directory,
    )
    return context, loaded, manifest_sha256, scope_sha256, S9OperationalLedger(context.ledger_path)


def _confirm_offline(
    context,
    manifest: dict[str, object],
    manifest_sha256: str,
    scope_sha256: str,
    ledger: S9OperationalLedger,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    prompts: list[str] = []

    def accept(prompt: str, **_kwargs) -> str:
        prompts.append(prompt)
        match = re.search(r"APROVAR S9 G0 ([0-9a-f]{32})", prompt)
        assert match is not None
        return f"APROVAR S9 G0 {match.group(1)}"

    monkeypatch.setattr("telegram_courses.s9_g0_confirmation._read_tty_line", accept)
    receipt = request_g0_confirmation(
        context.run_directory,
        ledger,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        scope_sha256=scope_sha256,
        test_mode=True,
        stdin=_Terminal(),
        stdout=_Terminal(),
    )
    assert prompts and "Manifesto SHA-256" in prompts[0]
    assert "3 scans" in prompts[0]
    assert "janela incremental de 50" in prompts[0]
    assert "confirmação própria em G4" in prompts[0]
    ledger.update_execution(
        gate="G0",
        status="RUNNING",
        elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
        deadline_ns=context.deadline_ns,
        process_state="UNKNOWN",
        result="OFFLINE_SYNTHETIC_PASS",
    )
    return receipt


def test_g0_scoped_confirmation_is_single_use_and_explicitly_synthetic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, manifest, manifest_sha256, scope_sha256, ledger = _start_run(tmp_path)
    receipt = _confirm_offline(
        context, manifest, manifest_sha256, scope_sha256, ledger, monkeypatch,
    )
    reopened = read_validated_gate_receipt(
        context.run_directory,
        S9OperationalLedger(context.ledger_path).snapshot(),
        "G0",
        run_id=context.run_id,
        manifest_sha256=manifest_sha256,
    )
    assert reopened == receipt
    assert reopened["status"] == "OFFLINE_SYNTHETIC_PASS"
    assert reopened["evidence_origin"] == "SYNTHETIC"
    assert reopened["confirmation_source"] == "SYNTHETIC_TEST"
    with pytest.raises(G0ConfirmationError, match="ALREADY_(CONSUMED|ATTEMPTED)"):
        request_g0_confirmation(
            context.run_directory,
            ledger,
            run_id=context.run_id,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            scope_sha256=scope_sha256,
            test_mode=True,
            stdin=_Terminal(),
            stdout=_Terminal(),
        )


def test_g0_non_tty_and_decline_never_create_consumable_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, manifest, manifest_sha256, scope_sha256, ledger = _start_run(tmp_path)
    with pytest.raises(G0ConfirmationError, match="TTY_REQUIRED"):
        request_g0_confirmation(
            context.run_directory,
            ledger,
            run_id=context.run_id,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            scope_sha256=scope_sha256,
            test_mode=True,
            stdin=io.StringIO(),
            stdout=io.StringIO(),
        )
    assert not (context.run_directory / "g0-gate-receipt.json").exists()

    second, second_manifest, second_hash, second_scope, second_ledger = _start_run(
        tmp_path / "declined",
    )
    monkeypatch.setattr(
        "telegram_courses.s9_g0_confirmation._read_tty_line",
        lambda *_args, **_kwargs: "N",
    )
    with pytest.raises(G0ConfirmationError, match="DECLINED"):
        request_g0_confirmation(
            second.run_directory,
            second_ledger,
            run_id=second.run_id,
            manifest=second_manifest,
            manifest_sha256=second_hash,
            scope_sha256=second_scope,
            test_mode=True,
            stdin=_Terminal(),
            stdout=_Terminal(),
        )
    assert not (second.run_directory / "g0-gate-receipt.json").exists()
    assert any(
        item["event_type"] == "G0_CONFIRMATION_BLOCKED"
        for item in second_ledger.snapshot()["critical_audit"]["events"]
    )

    third, third_manifest, third_hash, third_scope, third_ledger = _start_run(
        tmp_path / "timed-out",
    )
    monkeypatch.setattr(
        "telegram_courses.s9_g0_confirmation._read_tty_line",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError),
    )
    with pytest.raises(G0ConfirmationError, match="TIMEOUT"):
        request_g0_confirmation(
            third.run_directory,
            third_ledger,
            run_id=third.run_id,
            manifest=third_manifest,
            manifest_sha256=third_hash,
            scope_sha256=third_scope,
            test_mode=True,
            stdin=_Terminal(),
            stdout=_Terminal(),
        )
    assert not (third.run_directory / "g0-gate-receipt.json").exists()


def test_g0_receipt_is_bound_to_its_run_and_manifest_channel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, manifest, manifest_sha256, scope_sha256, ledger = _start_run(tmp_path)
    _confirm_offline(
        context, manifest, manifest_sha256, scope_sha256, ledger, monkeypatch,
    )
    other, other_manifest, other_hash, _other_scope, other_ledger = _start_run(
        tmp_path / "other-run",
    )
    (other.run_directory / "g0-gate-receipt.json").write_bytes(
        (context.run_directory / "g0-gate-receipt.json").read_bytes(),
    )
    with pytest.raises(ValueError):
        read_validated_gate_receipt(
            other.run_directory,
            other_ledger.snapshot(),
            "G0",
            run_id=other.run_id,
            manifest_sha256=other_hash,
        )

    changed_manifest = dict(manifest) | {"channel_id": CHANNEL_ID - 1}
    (context.run_directory / "approved-manifest.json").write_bytes(
        canonical_bytes(changed_manifest) + b"\n",
    )
    with pytest.raises(ValueError, match="G0_CONFIRMATION_RECEIPT_INVALID"):
        read_validated_gate_receipt(
            context.run_directory,
            ledger.snapshot(),
            "G0",
            run_id=context.run_id,
            manifest_sha256=manifest_sha256,
        )


def test_g1_worker_requires_consumed_human_g0_before_gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, _manifest, manifest_sha256, _scope_sha256, ledger = _start_run(tmp_path)
    for index, event_type in enumerate((
        "RUN_INITIALIZED", "PREFLIGHT_CONFIRMED", "GATE_STARTED",
        "CHILD_PROCESS_CONFIRMED",
    ), 1):
        details: dict[str, object] = {"stage": "discovery"}
        if event_type == "CHILD_PROCESS_CONFIRMED":
            details.update({"pid": 12345, "process_creation_time": 67890})
        ledger.record_critical_event(
            event_type,
            details=details,
            event_id=hashlib.sha256(f"test-g1-stage:{index}".encode("ascii")).hexdigest()[:32],
        )
    gateway_called = False

    def forbidden_gateway(*_args, **_kwargs):
        nonlocal gateway_called
        gateway_called = True
        raise AssertionError("gateway constructed before G0")

    monkeypatch.setattr("telegram_courses.s9_real_gate_producers.TelegramGateway", forbidden_gateway)
    monkeypatch.setattr(
        "telegram_courses.operational_logging.configure_operational_logging",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setenv("TELEGRAM_COURSES_S9_LEDGER_PATH", str(context.ledger_path))
    monkeypatch.setenv("TELEGRAM_COURSES_S9_SUPERVISED_CHILD", "1")
    monkeypatch.setenv("TELEGRAM_COURSES_S9_STAGE", "discovery")

    result = g1_worker_main([
        str(context.run_directory), context.run_id, manifest_sha256,
    ])

    assert result == 4
    assert gateway_called is False
    assert not (context.run_directory / "g1-worker-evidence.json").exists()


def test_default_gateway_api_requires_g0_before_loading_credentials(
    tmp_path: Path,
) -> None:
    context, manifest, manifest_sha256, _scope_sha256, _ledger = _start_run(tmp_path)
    credentials_loaded = False

    def forbidden_credentials():
        nonlocal credentials_loaded
        credentials_loaded = True
        raise AssertionError("credentials loaded before G0")

    with pytest.raises(ValueError, match="G0_CONFIRMATION_REQUIRED_BEFORE_G1"):
        asyncio.run(collect_g1_evidence(
            run_id=context.run_id,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            credentials_loader=forbidden_credentials,
        ))
    assert credentials_loaded is False


def test_default_credentials_require_g0_with_custom_gateway_factory(
    tmp_path: Path,
) -> None:
    context, manifest, manifest_sha256, _scope_sha256, _ledger = _start_run(tmp_path)
    gateway_called = False

    def forbidden_gateway(_credentials):
        nonlocal gateway_called
        gateway_called = True
        raise AssertionError("gateway created before G0")

    with pytest.raises(ValueError, match="G0_CONFIRMATION_REQUIRED_BEFORE_G1"):
        asyncio.run(collect_g1_evidence(
            run_id=context.run_id,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            gateway_factory=forbidden_gateway,
        ))
    assert gateway_called is False


def test_live_g0_rejects_injected_tty_streams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, manifest, manifest_sha256, scope_sha256, ledger = _start_run(tmp_path)
    monkeypatch.setattr(
        "telegram_courses.s9_g0_confirmation._read_tty_line",
        lambda *_args, **_kwargs: f"APROVAR S9 G0 {'a' * 32}",
    )
    with pytest.raises(
        G0ConfirmationError,
        match="G0_INTERACTIVE_STREAM_OVERRIDE_FORBIDDEN",
    ):
        request_g0_confirmation(
            context.run_directory,
            ledger,
            run_id=context.run_id,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            scope_sha256=scope_sha256,
            stdin=_Terminal(),
            stdout=_Terminal(),
        )
    assert not (context.run_directory / "g0-gate-receipt.json").exists()
    assert not any(
        item["event_type"] == "G0_CONFIRMATION_CONSUMED"
        for item in ledger.snapshot()["critical_audit"]["events"]
    )
