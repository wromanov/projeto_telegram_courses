from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import threading
import time
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

from telegram_courses.auth import AuthState
from telegram_courses.channel_discovery import (
    ChannelKind,
    ChannelSummary,
    DiscoveryResult,
    DiscoveryStats,
)
from telegram_courses.config import TelegramCredentials
from telegram_courses.message_scanner import GatewayMedia, GatewayMessage
from telegram_courses.s9_operational_ledger import (
    F_CAP,
    GIB,
    S9OperationalLedger,
    _create_private_directory,
    media_m_cap,
)
from telegram_courses.s9_real_gate_producers import canonical_bytes, sha256_bytes
from telegram_courses.s9_supervisor import STAGE_TIMEOUTS_SECONDS, SupervisorResult
from telegram_courses.s9_supervisor_cli import (
    OfflineRunnerError,
    start_supervised_run,
)

pytestmark = pytest.mark.skipif(os.name != "nt", reason="S9 process control is Windows-specific")

CHANNEL_ID = -1001234567890
F_MESSAGE_ID = 10
M_MESSAGE_ID = 20
INDEX_MESSAGE_ID = 30
RECOVERY_MESSAGE_ID = 40
G8_TARGET_MESSAGE_ID = 35
F_SIZE = 400_001
G8_SIZE = 600_001
M_SIZE = GIB
CHUNK_BYTES = 256 * 1024


class _TTYOutput(io.StringIO):
    def isatty(self) -> bool:
        return True


class _TTYInput(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.answers: deque[str] = deque()

    def isatty(self) -> bool:
        return True

    def queue(self, *answers: str) -> None:
        self.answers.extend(answers)

    def readline(self, size: int = -1) -> str:
        if self.answers:
            return self.answers.popleft() + "\n"
        return "s\n"


@contextmanager
def _exclusive_tty() -> Iterator[_TTYInput]:
    saved = (sys.stdin, sys.stdout, sys.stderr)
    stdin, stdout, stderr = _TTYInput(), _TTYOutput(), _TTYOutput()
    sys.stdin, sys.stdout, sys.stderr = stdin, stdout, stderr
    try:
        yield stdin
    finally:
        sys.stdin, sys.stdout, sys.stderr = saved


def _message(message_id: int, text: str, media: GatewayMedia | None = None) -> GatewayMessage:
    return GatewayMessage(
        telegram_chat_id=CHANNEL_ID,
        telegram_message_id=message_id,
        date_utc="2026-10-30T12:00:00+00:00",
        edit_date_utc=None,
        text=text,
        grouped_id=None,
        media=() if media is None else (media,),
    )


def _initial_messages(*, include_m: bool) -> list[GatewayMessage]:
    index_lines = [
        "=1 F track",
        "==1 F course",
        "===1 F module",
        "#F1",
    ]
    if include_m:
        index_lines.extend((
            "=2 M track",
            "==2 M course",
            "===2 M module",
            "#F2",
        ))
    index_lines.extend((
        "=3 G8 track",
        "==3 G8 course",
        "===3 G8 module",
        "#F3",
    ))
    records = [
        _message(
            F_MESSAGE_ID,
            "#F1 1 F lesson\n1 F track\n=1 F course\n==1 F module",
            GatewayMedia(0, "DOCUMENT", "fake-f-media", "f.bin", "application/octet-stream", F_SIZE),
        ),
        _message(
            INDEX_MESSAGE_ID,
            "\n".join(index_lines),
        ),
    ]
    if include_m:
        records.append(_message(
            M_MESSAGE_ID,
            "#F2 1 M lesson\n2 M track\n=2 M course\n==2 M module",
            GatewayMedia(0, "DOCUMENT", "fake-m-media", "m.bin", "application/octet-stream", M_SIZE),
        ))
    records.append(_g8_target_message())
    return records


def _g8_target_message() -> GatewayMessage:
    return _message(
        G8_TARGET_MESSAGE_ID,
        "#F3 1 G8 lesson\n3 G8 track\n=3 G8 course\n==3 G8 module",
        GatewayMedia(0, "DOCUMENT", "fake-g8-media", "g8.bin", "application/octet-stream", G8_SIZE),
    )


def _recovery_message() -> GatewayMessage:
    return _message(
        RECOVERY_MESSAGE_ID,
        "G7 incremental marker",
    )


class _DiscoveryGateway:
    async def restore(self) -> AuthState:
        return AuthState.AUTHENTICATED

    async def discover_channels(self, request) -> DiscoveryResult:
        channel = ChannelSummary(
            CHANNEL_ID, "Synthetic target", "synthetic_target", ChannelKind.MEGAGROUP,
        )
        return DiscoveryResult(
            (channel,), True, None,
            DiscoveryStats(1, 1, 1, 1, 0.0, request.limits),
        )

    async def close(self) -> None:
        return None


class _ScanGateway:
    messages: list[GatewayMessage] = []

    async def restore(self) -> AuthState:
        return AuthState.AUTHENTICATED

    async def iter_channel_messages(
        self,
        telegram_chat_id: int,
        *,
        through_message_id: int | None,
        before_message_id: int | None,
        limit: int,
        min_message_id: int | None = None,
    ):
        emitted = 0
        for item in sorted(self.messages, key=lambda row: row.telegram_message_id, reverse=True):
            if item.telegram_chat_id != telegram_chat_id:
                continue
            if through_message_id is not None and item.telegram_message_id > through_message_id:
                continue
            if before_message_id is not None and item.telegram_message_id >= before_message_id:
                continue
            if min_message_id is not None and item.telegram_message_id < min_message_id:
                continue
            if emitted >= limit:
                break
            emitted += 1
            yield item

    async def close(self) -> None:
        return None


class _DownloadGateway:
    stage = ""
    interrupted = False
    rpc_calls = 0
    stream_calls = 0

    @staticmethod
    def _block(message_id: int, start: int, size: int) -> bytes:
        if message_id == M_MESSAGE_ID:
            return bytes(size)
        seed = {
            F_MESSAGE_ID: b"F-synthetic-payload-",
            G8_TARGET_MESSAGE_ID: b"G8-synthetic-prefix-",
        }.get(message_id, b"synthetic-payload-")
        shift = start % len(seed)
        pattern = seed[shift:] + seed[:shift]
        return (pattern * ((size + len(pattern) - 1) // len(pattern)))[:size]

    async def restore(self) -> AuthState:
        return AuthState.AUTHENTICATED

    async def close(self) -> None:
        return None

    async def validate_media_identity(self, *_args, **_kwargs) -> bool:
        type(self).rpc_calls += 1
        return True

    async def get_file_hashes(
        self, _channel_id, message_id, _ordinal, *, expected_bytes: int, offset: int = 0,
        **_kwargs,
    ):
        from telegram_courses.downloads import RemoteFileHash

        type(self).rpc_calls += 1
        records = []
        cursor = 0
        while cursor < expected_bytes:
            size = min(CHUNK_BYTES, expected_bytes - cursor)
            payload = self._block(message_id, cursor, size)
            records.append(RemoteFileHash(cursor, size, hashlib.sha256(payload).digest()))
            cursor += size
        return tuple(item for item in records if item.offset >= offset)

    async def stream_media(
        self, _channel_id, message_id, _ordinal, *, expected_bytes: int,
        offset: int = 0, reserve_chunk, **_kwargs,
    ):
        type(self).rpc_calls += 1
        type(self).stream_calls += 1
        if (
            message_id == G8_TARGET_MESSAGE_ID
            and type(self).stage == "g8-interrupt"
            and not type(self).interrupted
        ):
            amount = 64 * 1024
            lease = await reserve_chunk(amount)
            if lease is None:
                return
            lease.received(amount)
            yield self._block(message_id, offset, amount)
            type(self).interrupted = True
            from telegram_courses.downloads import DownloadGatewayError

            raise DownloadGatewayError("NETWORK")
        cursor = offset
        while cursor < expected_bytes:
            size = min(CHUNK_BYTES, expected_bytes - cursor)
            lease = await reserve_chunk(size)
            if lease is None:
                return
            payload = self._block(message_id, cursor, size)
            lease.received(len(payload))
            yield payload
            cursor += len(payload)


class _SyntheticSupervisor:
    _s9_synthetic_test_seam = True
    messages: list[GatewayMessage] = []
    module_selection = 1
    cli_invocations = 0
    supervisor_runs = 0

    def _s9_g1_gateway_factory(_credentials):
        return _DiscoveryGateway()

    def _s9_g1_credentials_loader():
        return TelegramCredentials(7, "synthetic-test-credential")

    def __init__(self, *, receipt_path: Path, require_tty: bool, critical_audit_writer, ledger_run_id: str):
        self.receipt_path = receipt_path
        self.require_tty = require_tty
        self.critical_audit_writer = critical_audit_writer
        self.ledger_run_id = ledger_run_id
        type(self).supervisor_runs += 1
        self.audit_invocation = type(self).supervisor_runs

    def _audit(self, event_type: str, details: dict[str, object], index: int):
        event_id = hashlib.sha256(
            f"{self.ledger_run_id}:{details['stage']}:{self.audit_invocation}:{index}".encode("ascii"),
        ).hexdigest()[:32]
        return self.critical_audit_writer(event_type, details=details, event_id=event_id)

    def _invoke_cli(self, command, environment, stage: str, callbacks) -> int:
        from telegram_courses.cli import main as cli_main

        arguments = list(command[5:])
        saved_environment = dict(os.environ)
        try:
            os.environ.clear()
            os.environ.update(environment or {})
            if stage == "queue_f" and (environment or {}).get(
                "TELEGRAM_COURSES_S9_OPERATIONAL_GATE",
            ) == "G8":
                snapshot = S9OperationalLedger(
                    (environment or {})["TELEGRAM_COURSES_S9_LEDGER_PATH"],
                ).snapshot()
                _DownloadGateway.stage = (
                    "g8-recovery"
                    if snapshot["run"].get("interruptions") == 1
                    else "g8-interrupt"
                )
            else:
                _DownloadGateway.stage = stage
            _ScanGateway.messages = list(type(self).messages)
            if stage == "scan" and "--incremental" in arguments:
                _ScanGateway.messages.append(_recovery_message())
            type(self).cli_invocations += 1
            exit_code = cli_main(
                arguments,
                discovery_gateway_factory=lambda _credentials: _DiscoveryGateway(),
                scan_gateway_factory=lambda _credentials: _ScanGateway(),
                download_gateway_factory=lambda _credentials: _DownloadGateway(),
                gateway_factory=lambda _credentials: _DownloadGateway(),
                credentials_loader=lambda: TelegramCredentials(7, "synthetic-test-credential"),
            )
            if exit_code != 0:
                diagnostic = getattr(sys.stderr, "getvalue", lambda: "")()
                sys.__stderr__.write(
                    f"S9 E2E synthetic CLI stage={stage} exit_code={exit_code} "
                    f"stderr={diagnostic!r}\n",
                )
                sys.__stderr__.flush()
            return exit_code
        finally:
            os.environ.clear()
            os.environ.update(saved_environment)

    def run(self, command, *, stage: str, baseline_prompt_ready=None,
            release_confirmation=None, environment=None, allow_message_limit_exit=False,
            **_kwargs) -> SupervisorResult:
        if self.require_tty and not all(
            getattr(stream, "isatty", lambda: False)()
            for stream in (sys.stdin, sys.stdout, sys.stderr)
        ):
            raise AssertionError("the synthetic supervisor requires its exclusive fake TTY")
        acknowledgements = []
        next_id = 0

        def record(event_type: str, details: dict[str, object]) -> None:
            nonlocal next_id
            next_id += 1
            acknowledgements.append(self._audit(event_type, details, next_id))

        for event_type in ("RUN_INITIALIZED", "PREFLIGHT_CONFIRMED", "GATE_STARTED"):
            record(event_type, {"stage": stage})
        process_creation_time = time.time_ns()
        synthetic_environment = dict(environment or {})
        synthetic_environment["TELEGRAM_COURSES_S9_SYNTHETIC_PROCESS_CREATION_TIME"] = str(
            process_creation_time,
        )
        record("CHILD_PROCESS_CONFIRMED", {
            "stage": stage,
            "pid": os.getpid(),
            "process_creation_time": process_creation_time,
        })
        tty_available = all(
            getattr(stream, "isatty", lambda: False)()
            for stream in (sys.stdin, sys.stdout, sys.stderr)
        )

        def invoke() -> tuple[int | None, BaseException | None]:
            try:
                return self._invoke_cli(
                    command, synthetic_environment, stage,
                    (baseline_prompt_ready, release_confirmation),
                ), None
            except BaseException as error:
                return None, error

        exit_code: int | None = 0
        raised: BaseException | None = None
        if stage in {"queue_f", "queue_m"} and baseline_prompt_ready is not None:
            result_box: list[tuple[int | None, BaseException | None]] = []
            child = threading.Thread(target=lambda: result_box.append(invoke()), daemon=True)
            child.start()
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and not baseline_prompt_ready():
                if not child.is_alive():
                    break
                time.sleep(0.01)
            if baseline_prompt_ready():
                release_confirmation()
            stage_timeout = _kwargs.get("timeout_seconds")
            if stage_timeout is None:
                stage_timeout = STAGE_TIMEOUTS_SECONDS[stage]
            if type(stage_timeout) is not int or stage_timeout <= 0:
                raise AssertionError("fake supervisor received invalid stage timeout")
            join_deadline = time.monotonic() + stage_timeout
            global_deadline = _kwargs.get("global_deadline_monotonic")
            if type(global_deadline) in {int, float}:
                join_deadline = min(join_deadline, float(global_deadline))
            stage_started = time.monotonic()
            last_status_report = stage_started
            while child.is_alive():
                remaining = join_deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError(
                        "fake CLI exceeded the operation/global deadline; "
                        f"stage={stage}"
                    )
                child.join(timeout=min(30, remaining))
                if stage == "queue_m" and child.is_alive():
                    now = time.monotonic()
                    if now - last_status_report >= 60:
                        elapsed = int(now - stage_started)
                        sys.__stderr__.write(
                            f"S9 E2E progress stage={stage} child_alive=True "
                            f"elapsed_seconds={elapsed}\n"
                        )
                        sys.__stderr__.flush()
                        last_status_report = now
            if result_box:
                exit_code, raised = result_box[0]
            else:
                exit_code, raised = None, AssertionError("fake CLI did not return")
        elif stage in {"scan", "catalog", "inspection"}:
            exit_code, raised = invoke()

        if raised is not None:
            raise raised
        is_interruption = bool(
            stage == "queue_f" and exit_code == 4
            and _DownloadGateway.stage == "g8-interrupt"
            and _DownloadGateway.interrupted
        )
        if is_interruption:
            result = "FAILED"
            supervisor_gate = "BLOCKED"
            external_exit = 4
        else:
            result = "COMPLETED" if exit_code == 0 else "FAILED"
            supervisor_gate = "PASS" if exit_code == 0 else "BLOCKED"
            external_exit = exit_code
        record("SUPERVISOR_RUN_FINISHED", {
            "stage": stage,
            "result": result,
            "exit_code": external_exit,
            "tree_confirmed": True,
        })
        prepared_id = hashlib.sha256(
            f"{self.ledger_run_id}:{stage}:{self.audit_invocation}:prepared".encode("ascii"),
        ).hexdigest()[:32]
        persisted_id = hashlib.sha256(
            f"{self.ledger_run_id}:{stage}:{self.audit_invocation}:persisted".encode("ascii"),
        ).hexdigest()[:32]
        receipt: dict[str, object] = {
            "schema": "telegram-courses-s9-supervisor-receipt-v1",
            "run_id": self.ledger_run_id,
            "ledger_run_id": self.ledger_run_id,
            "stage": stage,
            "result": result,
            "reason": "PROCESS_EXITED",
            "external_exit_code": external_exit,
            "message_limit_exit_allowed": bool(allow_message_limit_exit),
            "process_tree_termination_confirmed": True,
            "critical_audit_gate": "PASS",
            "supervisor_offline_gate": supervisor_gate,
            "process_control_offline_gate": "PASS",
            "memory_monitoring_offline_gate": "PASS",
            "tty_required": self.require_tty,
            "tty_available": tty_available,
            "preconfirmation_prompt_signal_available": baseline_prompt_ready is not None,
            "preconfirmation_release_callback_available": release_confirmation is not None,
            "preconfirmation_confirmation_released": baseline_prompt_ready is not None,
            "limit_check_result": (
                "PASS" if stage in {"queue_f", "queue_m"} and exit_code == 0
                else "UNKNOWN"
            ),
            "memory": {
                "samples": [{"working_set_bytes": 128, "private_bytes": 96}],
                "peak_working_set_bytes": 128,
            },
            "critical_audit_acknowledgements": acknowledgements,
            "receipt_prepared_event_id": prepared_id,
            "receipt_attestation_event_id": persisted_id,
        }
        raw = canonical_bytes(receipt) + b"\n"
        digest = hashlib.sha256(raw).hexdigest()
        self.critical_audit_writer(
            "RECEIPT_PREPARED", details={"receipt_sha256": digest}, event_id=prepared_id,
        )
        self.receipt_path.write_bytes(raw)
        self.critical_audit_writer(
            "RECEIPT_PERSISTED", details={"receipt_sha256": digest}, event_id=persisted_id,
        )
        return SupervisorResult(
            run_id=self.ledger_run_id,
            result=result,
            reason="PROCESS_EXITED",
            exit_code=external_exit,
            receipt_path=self.receipt_path,
            receipt_persisted=True,
            supervisor_gate=supervisor_gate,
            process_control_gate="PASS",
            memory_monitoring_gate="PASS",
            limit_check_result=(
                "PASS" if stage in {"queue_f", "queue_m"} and exit_code == 0
                else "UNKNOWN"
            ),
            critical_audit_gate="PASS",
            receipt_attested=True,
        )


class _UnmarkedSupervisor(_SyntheticSupervisor):
    _s9_synthetic_test_seam = False


def _write_manifest(run_directory: Path, *, hierarchy_count: int) -> None:
    scope = {"target_alias": "SYNTHETIC_TARGET"}
    manifest = {
        "schema_version": 1,
        "channel_id": CHANNEL_ID,
        "channel_alias": "SYNTHETIC_TARGET",
        "scope": scope,
        "hierarchy": {
            "TRACK": hierarchy_count,
            "COURSE": hierarchy_count,
            "MODULE": hierarchy_count,
        },
        "unresolved_count": 0,
        "scope_approval": {
            "decision": "APPROVED",
            "confirmation_source": "G0_HUMAN_CONFIRMATION",
            "scope_sha256": sha256_bytes(canonical_bytes(scope)),
        },
    }
    (run_directory / "approved-manifest.json").write_bytes(canonical_bytes(manifest) + b"\n")


def _arguments(run_directory: Path, *, module_index: int, profile: str, max_bytes: int) -> list[str]:
    return [
        "download", "queue", "--channel-id", str(CHANNEL_ID),
        "--database", str(run_directory / "catalog.sqlite3"),
        "--download-dir", str(run_directory / "downloads"),
        "--scope", "module", "--workers", "1", "--attempts-per-media", "1",
        "--max-media-items", "1", "--max-transfer-bytes", str(max_bytes),
        "--integrity-mode", "REMOTE_HASH_REQUIRED",
    ]


def _approve_fake_g0(prompt: str, **_kwargs) -> str:
    match = re.search(r"digite: (APROVAR S9 G0 [0-9a-f]+)", prompt)
    assert match is not None
    return match.group(1)


def _set_supervisor_messages(include_m: bool) -> None:
    _SyntheticSupervisor.messages = _initial_messages(include_m=include_m)
    _SyntheticSupervisor.cli_invocations = 0
    _SyntheticSupervisor.supervisor_runs = 0
    _DownloadGateway.interrupted = False
    _DownloadGateway.rpc_calls = 0
    _DownloadGateway.stream_calls = 0


def _run_g0_g1(context, tty_input: _TTYInput, monkeypatch) -> None:
    from telegram_courses import s9_g0_confirmation, s9_supervisor
    from telegram_courses.s9_supervisor_cli import run_supervised_g1

    monkeypatch.setattr(s9_g0_confirmation, "_read_tty_line", _approve_fake_g0)
    monkeypatch.setattr(
        s9_supervisor,
        "_creation_time",
        lambda *_args: int(os.environ["TELEGRAM_COURSES_S9_SYNTHETIC_PROCESS_CREATION_TIME"]),
    )
    localappdata_guard = _create_private_directory(
        context.run_directory / "synthetic-local-app-data",
    )
    localappdata = localappdata_guard.path
    localappdata_guard.close()
    monkeypatch.setenv("LOCALAPPDATA", str(localappdata))
    outcome = run_supervised_g1(
        context,
        context.run_directory / "g1-output",
        require_tty=True,
        supervisor_type=_SyntheticSupervisor,
    )
    assert outcome.stage_gate_result == "OFFLINE_SYNTHETIC_PASS", (
        f"synthetic stage failed: gate={outcome.stage_gate_result} "
        f"supervisor={outcome.supervisor!r} "
        f"ledger_status={outcome.ledger_status} ledger_result={outcome.ledger_result}"
    )
    assert S9OperationalLedger(context.ledger_path).snapshot()["run"]["result"] == "OFFLINE_SYNTHETIC_PASS"


def _run_scan(context, *, incremental: bool) -> None:
    from telegram_courses.s9_supervisor_cli import run_supervised_cli_stage

    args = [
        "scan", "--channel-id", str(CHANNEL_ID),
        "--database", str(context.run_directory / "catalog.sqlite3"),
        "--max-messages", "200", "--timeout-seconds", "120",
    ]
    if incremental:
        args.extend(["--incremental", "--reconcile-window", "50"])
    outcome = run_supervised_cli_stage(
        context, context.run_directory / ("g7-scan" if incremental else "g2-scan"),
        args, require_tty=True, supervisor_type=_SyntheticSupervisor,
    )
    assert outcome.stage_gate_result == "OFFLINE_SYNTHETIC_PASS", (
        f"synthetic stage failed: gate={outcome.stage_gate_result} "
        f"supervisor={outcome.supervisor!r} "
        f"ledger_status={outcome.ledger_status} ledger_result={outcome.ledger_result}"
    )


def _run_catalog(context) -> None:
    from telegram_courses.s9_supervisor_cli import run_supervised_cli_stage

    outcome = run_supervised_cli_stage(
        context,
        context.run_directory / "g3-catalog",
        [
            "catalog", "build", "--channel-id", str(CHANNEL_ID),
            "--parser-key", "rasmoo",
            "--database", str(context.run_directory / "catalog.sqlite3"),
        ],
        require_tty=True,
        supervisor_type=_SyntheticSupervisor,
    )
    assert outcome.stage_gate_result == "OFFLINE_SYNTHETIC_PASS"


def _run_queue(
    context, tty_input: _TTYInput, *, profile: str, pass_index: int,
    module_index: int, max_bytes: int, supervisor_type=_SyntheticSupervisor,
):
    from telegram_courses.s9_supervisor_cli import run_supervised_queue

    tty_input.queue(
        str(module_index),
        *( () if pass_index == 2 else ("s",) ),
    )
    return run_supervised_queue(
        context.run_directory / f"queue-{profile.lower()}-{pass_index}",
        context.ledger_path,
        _arguments(context.run_directory, module_index=module_index, profile=profile, max_bytes=max_bytes),
        profile=profile,
        require_tty=True,
        supervisor_type=supervisor_type,
    )


def test_synthetic_g0_through_g9_cli_path_and_recovery(tmp_path: Path, monkeypatch) -> None:
    from telegram_courses.s9_operational_reconciliation import (
        OperationalReconciliationError,
        reconcile_g9_operational,
    )
    from telegram_courses.s9_supervisor_cli import (
        run_supervised_g8,
        run_supervised_queue,
    )
    _set_supervisor_messages(include_m=True)
    context = start_supervised_run(tmp_path / "synthetic-full-run")
    _write_manifest(context.run_directory, hierarchy_count=3)
    with _exclusive_tty() as tty_input:
        _run_g0_g1(context, tty_input, monkeypatch)
        _run_scan(context, incremental=False)
        _run_catalog(context)

        f_first = _run_queue(
            context, tty_input, profile="F", pass_index=1,
            module_index=1, max_bytes=F_CAP,
        )
        assert f_first.queue_gate_result == "OFFLINE_SYNTHETIC_PASS"

        # The default/unmarked supervisor cannot convert the synthetic G0
        # receipt into authorization to launch a queue or touch the gateway.
        launches: list[int] = []

        class NoLaunch(_UnmarkedSupervisor):
            def __init__(self, **kwargs):
                launches.append(1)
                super().__init__(**kwargs)

        before_rpc = _DownloadGateway.rpc_calls
        with pytest.raises(OfflineRunnerError, match="G0_CONFIRMATION_REQUIRED"):
            run_supervised_queue(
                context.run_directory / "synthetic-g0-must-not-launch",
                context.ledger_path,
                _arguments(context.run_directory, module_index=1, profile="F", max_bytes=F_CAP),
                profile="F", require_tty=True, supervisor_type=NoLaunch,
            )
        assert launches == []
        assert _DownloadGateway.rpc_calls == before_rpc

        f_second = _run_queue(
            context, tty_input, profile="F", pass_index=2,
            module_index=1, max_bytes=1,
        )
        assert f_second.queue_gate_result == "OFFLINE_SYNTHETIC_PASS"

        m_first = _run_queue(
            context, tty_input, profile="M", pass_index=1,
            module_index=2, max_bytes=media_m_cap(M_SIZE),
        )
        assert m_first.queue_gate_result == "OFFLINE_SYNTHETIC_PASS"
        m_second = _run_queue(
            context, tty_input, profile="M", pass_index=2,
            module_index=2, max_bytes=1,
        )
        assert m_second.queue_gate_result == "OFFLINE_SYNTHETIC_PASS"

        g6 = json.loads((context.run_directory / "g6-gate-receipt.json").read_text("utf-8"))
        assert g6["status"] == "OFFLINE_SYNTHETIC_PASS"
        _run_scan(context, incremental=True)

        g8_args = _arguments(
            context.run_directory, module_index=3, profile="F", max_bytes=F_CAP,
        )
        _DownloadGateway.interrupted = False
        _DownloadGateway.stage = "g8-interrupt"
        tty_input.queue("3")
        interrupted = run_supervised_g8(
            context,
            context.run_directory / "g8-interrupt-output",
            g8_args,
            phase="interrupt",
            require_tty=True,
            supervisor_type=_SyntheticSupervisor,
        )
        assert interrupted.gate_result == "INTERRUPTED"
        assert interrupted.ledger_status == "RUNNING"
        assert interrupted.ledger_result == "PARTIAL"

        _DownloadGateway.stage = "g8-recover"
        tty_input.queue("3")
        recovered = run_supervised_g8(
            context,
            context.run_directory / "g8-recover-output",
            g8_args,
            phase="recover",
            require_tty=True,
            supervisor_type=_SyntheticSupervisor,
        )
        assert recovered.gate_result == "OFFLINE_SYNTHETIC_PASS"
        proof = json.loads((context.run_directory / "g8-s6-prefix-proof.json").read_text("utf-8"))
        assert proof["evidence_origin"] == "SYNTHETIC"
        assert proof["physical_prefix_bytes"] == 64 * 1024
        assert proof["verification_payload_bytes"] > 0

        final = reconcile_g9_operational(
            context.run_directory,
            context.run_directory / "catalog.sqlite3",
            context.run_directory / "downloads",
        )
        assert final.result == "OFFLINE_SYNTHETIC_PASS"
        assert final.real_evidence_status == "REAL_EVIDENCE_PENDING"
        assert all(gate.evidence_origin == "SYNTHETIC" for gate in final.gates)
        report = final.report_path.read_text("utf-8")
        assert "REAL_EVIDENCE_PENDING" in report
        assert str(CHANNEL_ID) not in report
        assert "REAL_CONTRACTUAL_PASS" not in report
        ledger = S9OperationalLedger(context.ledger_path).snapshot()
        assert ledger["run"]["gate"] == "G9"
        assert ledger["run"]["status"] == "COMPLETED"
        assert ledger["run"]["result"] == "OFFLINE_SYNTHETIC_PASS"

        reopened = reconcile_g9_operational(
            context.run_directory,
            context.run_directory / "catalog.sqlite3",
            context.run_directory / "downloads",
        )
        assert reopened.result == "OFFLINE_SYNTHETIC_PASS"

        with sqlite3.connect(context.run_directory / "catalog.sqlite3") as database:
            row = database.execute(
                "SELECT d.final_path FROM downloads d "
                "JOIN media_items m ON m.id=d.media_item_id "
                "WHERE m.telegram_message_id=? AND d.state='DOWNLOADED'",
                (G8_TARGET_MESSAGE_ID,),
            ).fetchone()
        assert row is not None
        Path(str(row[0])).unlink()
        with pytest.raises(
            OperationalReconciliationError,
            match="G9_OPERATIONAL_REOPEN_MISMATCH",
        ):
            reconcile_g9_operational(
                context.run_directory,
                context.run_directory / "catalog.sqlite3",
                context.run_directory / "downloads",
            )


def test_synthetic_no_m_scenario_stays_partial_and_g7_g8_not_tested(
    tmp_path: Path, monkeypatch,
) -> None:
    from telegram_courses.s9_operational_reconciliation import reconcile_g9_operational

    _set_supervisor_messages(include_m=False)
    context = start_supervised_run(tmp_path / "synthetic-no-m-run")
    _write_manifest(context.run_directory, hierarchy_count=2)
    with _exclusive_tty() as tty_input:
        _run_g0_g1(context, tty_input, monkeypatch)
        _run_scan(context, incremental=False)
        _run_catalog(context)
        assert _run_queue(
            context, tty_input, profile="F", pass_index=1,
            module_index=1, max_bytes=F_CAP,
        ).queue_gate_result == "OFFLINE_SYNTHETIC_PASS"
        assert _run_queue(
            context, tty_input, profile="F", pass_index=2,
            module_index=1, max_bytes=1,
        ).queue_gate_result == "OFFLINE_SYNTHETIC_PASS"
        g6 = json.loads((context.run_directory / "g6-gate-receipt.json").read_text("utf-8"))
        assert g6["status"] == "PARTIAL"
        assert g6["g5_m_status"] == "BLOCKED_DATASET"
        assert g6["g6_aggregate_status"] == "PARTIAL"
        assert g6["g7_real_eligible"] is False
        assert g6["nfr02_real"] == "NOT_TESTED"

        final = reconcile_g9_operational(
            context.run_directory,
            context.run_directory / "catalog.sqlite3",
            context.run_directory / "downloads",
        )
        assert final.result == "PARTIAL"
        assert final.real_evidence_status == "REAL_EVIDENCE_PENDING"
        by_gate = {item.gate: item for item in final.gates}
        assert by_gate["G7"].status == "NOT_TESTED"
        assert by_gate["G8"].status == "NOT_TESTED"
        assert S9OperationalLedger(context.ledger_path).snapshot()["run"]["result"] == "PARTIAL"
