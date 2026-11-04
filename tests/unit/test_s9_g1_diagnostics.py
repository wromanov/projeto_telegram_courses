from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from telegram_courses import operational_logging, s9_operational_ledger
from telegram_courses import s9_real_gate_producers as producer
from telegram_courses.config import TelegramCredentials
from telegram_courses.s9_supervisor_cli import _TRUSTED_G1_BOOTSTRAP


def test_ledger_identity_failure_precedes_secondary_t24_finalization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _setup_worker(monkeypatch, tmp_path)

    def fail(_path: object) -> None:
        raise s9_operational_ledger.LedgerError("LEDGER_CHILD_IDENTITY_INVALID")

    monkeypatch.setattr(s9_operational_ledger, "S9OperationalLedger", fail)
    monkeypatch.setattr(logging.getLogger("telegram_courses"), "handlers", [])
    monkeypatch.setattr(operational_logging, "_LOGGING_FAILURE_SEEN", False)
    expected = str(Path(producer.__file__).resolve())
    monkeypatch.setattr(sys, "argv", ["-c", expected, str(tmp_path), "run", "hash"])
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda _name: SimpleNamespace(origin=expected)
    )
    monkeypatch.setattr(
        runpy,
        "run_module",
        lambda *_args, **_kwargs: {"g1_worker_main": producer.g1_worker_main},
    )
    with pytest.raises(SystemExit) as result:
        exec(_TRUSTED_G1_BOOTSTRAP, {})
    assert result.value.code == 125
    events = _events(capsys.readouterr().err)
    primary = next(
        i
        for i, event in enumerate(events)
        if event["failure_class"] == "LEDGER_CHILD_IDENTITY_INVALID"
    )
    secondary = next(
        i
        for i, event in enumerate(events)
        if event["failure_class"] == "FINALIZATION_FAILED"
    )
    assert primary < secondary


def test_isolated_bootstrap_rejects_unsupervised_environment_without_rpc() -> None:
    environment = os.environ.copy()
    for key in (
        "TELEGRAM_COURSES_S9_SUPERVISED_CHILD",
        "TELEGRAM_COURSES_S9_LEDGER_PATH",
        "TELEGRAM_COURSES_S9_STAGE",
    ):
        environment.pop(key, None)
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            _TRUSTED_G1_BOOTSTRAP,
            str(Path(producer.__file__).resolve()),
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 125
    assert any(
        item["failure_class"] == "INVALID_ENVIRONMENT"
        for item in _events(result.stderr)
    )


def test_unhandled_worker_error_preserves_exception_and_logs_phase(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _setup_worker(monkeypatch, tmp_path)

    def fail(_path: object) -> object:
        raise TypeError("SECRET_PRIVATE_PAYLOAD")

    monkeypatch.setattr(producer, "load_approved_manifest", fail)
    with pytest.raises(TypeError):
        producer.g1_worker_main([str(tmp_path), "run", "hash"])
    stderr = capsys.readouterr().err
    assert "SECRET_PRIVATE_PAYLOAD" not in stderr
    assert any(
        item["phase"] == "context_manifest" and item["failure_class"] == "OTHER_ERROR"
        for item in _events(stderr)
    )


def _events(stderr: str) -> list[dict[str, str]]:
    return [json.loads(line) for line in stderr.splitlines() if line.startswith("{")]


def _setup_worker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TELEGRAM_COURSES_S9_SUPERVISED_CHILD", "1")
    monkeypatch.setenv("TELEGRAM_COURSES_S9_STAGE", "discovery")
    monkeypatch.setenv("TELEGRAM_COURSES_S9_LEDGER_PATH", str(tmp_path / "ledger"))
    events = [
        {"event_type": name, "details_json": '{"stage":"discovery"}'}
        for name in (
            "RUN_INITIALIZED",
            "PREFLIGHT_CONFIRMED",
            "GATE_STARTED",
            "CHILD_PROCESS_CONFIRMED",
        )
    ]
    snapshot = {
        "run": {
            "run_id": "run",
            "gate": "G1",
            "status": "RUNNING",
            "result": "UNKNOWN",
        },
        "critical_audit": {"events": events, "quarantined": False},
    }
    monkeypatch.setattr(
        s9_operational_ledger,
        "S9OperationalLedger",
        lambda _path: SimpleNamespace(snapshot=lambda: snapshot),
    )
    monkeypatch.setattr(
        operational_logging, "configure_operational_logging", lambda *_args: None
    )
    monkeypatch.setattr(
        operational_logging, "emit_operational_event", lambda *_args, **_kwargs: None
    )
    manifest = {"channel_id": -1, "scope": {}}
    monkeypatch.setattr(
        producer, "load_approved_manifest", lambda _path: (manifest, "hash", "scope")
    )
    monkeypatch.setattr(
        producer,
        "read_validated_gate_receipt",
        lambda *_args, **_kwargs: {
            "status": "PASS",
            "evidence_origin": "HUMAN_INTERACTIVE",
            "channel_id": -1,
            "authorized_scope": {},
        },
    )


@pytest.mark.parametrize(
    ("failure_point", "phase", "error_type"),
    [
        ("ledger", "context_manifest", RuntimeError),
        ("logging", "t24_initialization", RuntimeError),
        ("manifest", "context_manifest", ValueError),
        ("gateway", "gateway_open", RuntimeError),
        ("persistence", "evidence_persistence", OSError),
    ],
)
def test_worker_failure_is_sanitized_and_preserves_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    failure_point: str,
    phase: str,
    error_type: type[Exception],
) -> None:
    _setup_worker(monkeypatch, tmp_path)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise error_type("SECRET_PRIVATE_PAYLOAD")

    async def collect(*_args: object, **_kwargs: object) -> dict[str, object]:
        if failure_point == "gateway":
            fail()
        return {"status": "BLOCKED", "reason": "TEST"}

    if failure_point == "ledger":
        monkeypatch.setattr(s9_operational_ledger, "S9OperationalLedger", fail)
    elif failure_point == "logging":
        monkeypatch.setattr(operational_logging, "configure_operational_logging", fail)
    elif failure_point == "manifest":
        monkeypatch.setattr(producer, "load_approved_manifest", fail)
    monkeypatch.setattr(producer, "collect_g1_evidence", collect)
    if failure_point == "persistence":
        monkeypatch.setattr(producer, "_run_root", fail)

    assert producer.g1_worker_main([str(tmp_path), "run", "hash"]) == 4
    stderr = capsys.readouterr().err
    assert "SECRET_PRIVATE_PAYLOAD" not in stderr
    assert any(
        item["phase"] == phase and item["state"] == "FAILURE"
        for item in _events(stderr)
    )


def test_worker_rejects_before_gateway_with_sanitized_diagnostic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert producer.g1_worker_main([]) == 2
    assert any(
        item["failure_class"] == "INVALID_ARGUMENTS"
        for item in _events(capsys.readouterr().err)
    )


def test_diagnostic_stream_failure_does_not_change_worker_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenStream:
        def write(self, _text: str) -> None:
            raise OSError("SECRET_PRIVATE_PAYLOAD")

        def flush(self) -> None:
            raise OSError("SECRET_PRIVATE_PAYLOAD")

    with monkeypatch.context() as patch:
        patch.setattr(sys, "stderr", BrokenStream())
        assert producer.g1_worker_main([]) == 2


@pytest.mark.parametrize(
    ("point", "reason"),
    [
        ("environment", "INVALID_ENVIRONMENT"),
        ("context", "INVALID_CONTEXT"),
        ("audit", "INVALID_AUDIT"),
        ("manifest", "MANIFEST_MISMATCH"),
        ("g0", "G0_INVALID"),
    ],
)
def test_worker_preconditions_block_before_gateway(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    point: str,
    reason: str,
) -> None:
    _setup_worker(monkeypatch, tmp_path)
    if point == "environment":
        monkeypatch.delenv("TELEGRAM_COURSES_S9_LEDGER_PATH")
    elif point == "context":
        monkeypatch.setattr(
            s9_operational_ledger,
            "S9OperationalLedger",
            lambda _path: SimpleNamespace(
                snapshot=lambda: {
                    "run": {},
                    "critical_audit": {"events": [], "quarantined": False},
                },
            ),
        )
    elif point == "audit":
        monkeypatch.setattr(
            s9_operational_ledger,
            "S9OperationalLedger",
            lambda _path: SimpleNamespace(
                snapshot=lambda: {
                    "run": {
                        "run_id": "run",
                        "gate": "G1",
                        "status": "RUNNING",
                        "result": "UNKNOWN",
                    },
                    "critical_audit": {"events": [], "quarantined": False},
                },
            ),
        )
    elif point == "manifest":
        monkeypatch.setattr(
            producer, "load_approved_manifest", lambda _path: ({}, "different", "scope")
        )
    elif point == "g0":
        monkeypatch.setattr(
            producer, "read_validated_gate_receipt", lambda *_args, **_kwargs: {}
        )

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("gateway must not be opened")

    monkeypatch.setattr(producer, "collect_g1_evidence", forbidden)
    assert producer.g1_worker_main([str(tmp_path), "run", "hash"]) == 4
    assert any(
        item["failure_class"] == reason for item in _events(capsys.readouterr().err)
    )


@pytest.mark.parametrize("point", ["gateway", "discovery"])
def test_fake_gateway_diagnostic_distinguishes_failure_phase(point: str) -> None:
    diagnostics: list[tuple[str, str, str]] = []

    class Gateway:
        async def restore(self) -> object:
            raise RuntimeError("SECRET_PRIVATE_PAYLOAD")

        async def close(self) -> None:
            pass

    def factory(_credentials: TelegramCredentials) -> Gateway:
        if point == "gateway":
            raise RuntimeError("SECRET_PRIVATE_PAYLOAD")
        return Gateway()

    result = asyncio.run(
        producer.collect_g1_evidence(
            run_id="synthetic",
            manifest={"channel_id": -1, "channel_alias": "RASMOO"},
            manifest_sha256="x",
            gateway_factory=factory,
            credentials_loader=lambda: TelegramCredentials(12345, "a" * 32),
            diagnostic=lambda *args: diagnostics.append(args),
        )
    )
    assert result["status"] == "BLOCKED"
    assert any(
        event[0] == ("gateway_open" if point == "gateway" else "discovery")
        and event[1] == "FAILURE"
        for event in diagnostics
    )
    assert "SECRET_PRIVATE_PAYLOAD" not in str(diagnostics)


@pytest.mark.parametrize(
    "mode",
    [
        "origin",
        "environment",
        "lookup",
        "module",
        "worker",
        "finalization",
        "finalization_exception",
        "normal",
    ],
)
def test_bootstrap_and_finalization_identify_failures_without_leaking(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode: str,
) -> None:
    monkeypatch.setattr(sys, "argv", ["-c", str(Path("producer.py").absolute())])
    monkeypatch.setenv("TELEGRAM_COURSES_S9_SUPERVISED_CHILD", "1")
    monkeypatch.setenv("TELEGRAM_COURSES_S9_LEDGER_PATH", "ledger")
    monkeypatch.setenv("TELEGRAM_COURSES_S9_STAGE", "discovery")

    def find_spec(_name: str) -> SimpleNamespace:
        if mode == "lookup":
            raise ValueError("SECRET_PRIVATE_PAYLOAD")
        return SimpleNamespace(
            origin=str(
                Path("other.py" if mode == "origin" else "producer.py").absolute()
            )
        )

    monkeypatch.setattr(importlib.util, "find_spec", find_spec)
    if mode == "environment":
        monkeypatch.delenv("TELEGRAM_COURSES_S9_LEDGER_PATH")

    def worker(_args: object) -> int:
        if mode == "worker":
            raise RuntimeError("SECRET_PRIVATE_PAYLOAD")
        return 4

    def load_module(*_args: object, **_kwargs: object) -> dict[str, object]:
        if mode == "module":
            raise RuntimeError("SECRET_PRIVATE_PAYLOAD")
        return {"g1_worker_main": worker}

    def finalize(code: int) -> int:
        if mode == "finalization_exception":
            raise RuntimeError("SECRET_PRIVATE_PAYLOAD")
        return 125 if mode in {"worker", "finalization"} else code

    monkeypatch.setattr(runpy, "run_module", load_module)
    monkeypatch.setattr(operational_logging, "finalize_s9_child_exit_code", finalize)
    with pytest.raises(SystemExit) as result:
        exec(_TRUSTED_G1_BOOTSTRAP, {})
    assert result.value.code == (
        1 if mode in {"worker", "module", "lookup"} else 4 if mode == "normal" else 125
    )
    stderr = capsys.readouterr().err
    assert "SECRET_PRIVATE_PAYLOAD" not in stderr
    events = _events(stderr)
    expected = {
        "origin": "MODULE_ORIGIN_MISMATCH",
        "environment": "INVALID_ENVIRONMENT",
        "lookup": "MODULE_LOOKUP_ERROR",
        "module": "MODULE_LOAD_ERROR",
        "worker": "UNHANDLED_WORKER_ERROR",
        "finalization": "FINALIZATION_FAILED",
        "finalization_exception": "FINALIZATION_EXCEPTION",
        "normal": None,
    }[mode]
    if expected is None:
        assert not any(item["phase"] == "t24_finalization" for item in events)
    else:
        assert any(item["failure_class"] == expected for item in events)
    if mode == "worker":
        assert any(item["phase"] == "t24_finalization" for item in events)
