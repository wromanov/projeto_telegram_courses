"""S9 queue accounting integration with synthetic gateway responses only."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from telegram_courses import cli as cli_module
from telegram_courses.auth import RateLimited
from telegram_courses.config import ConfigurationError
from telegram_courses.download_repository import DownloadCandidate
from telegram_courses.downloads import DownloadError, DownloadGatewayError
from telegram_courses.s5_downloads import (
    DownloadPlan,
    DownloadQueue,
    DownloadSelection,
    PlanItem,
)
from telegram_courses.s9_operational_ledger import (
    CHUNK,
    F_CAP,
    GIB,
    M_MAX_CAP,
    S9_MEASUREMENT_SOURCE_ENV,
    LedgerError,
    QueueMediaBinding,
    S9OperationalLedger,
    S9QueueAccounting,
    _create_private_directory,
    media_m_cap,
)
from telegram_courses.s9_supervisor_cli import (
    OfflineRunnerError,
    _record_f_interruption_after_supervised_stop,
    _validate_supervised_queue_arguments,
    run_supervised_queue,
    start_supervised_run,
)
from telegram_courses.s9_supervisor_handshake import (
    HANDSHAKE_DIR_ENV,
    HANDSHAKE_NONCE_ENV,
    S9_LEDGER_PATH_ENV,
    S9_PROFILE_ENV,
    S9_SUPERVISED_CHILD_ENV,
)

IDENTITY = (-1001, 10, 0)
SIZE = 4


def _ledger(tmp_path: Path) -> tuple[S9OperationalLedger, str]:
    guard = _create_private_directory(tmp_path / "private-ledger")
    path = guard.path / "ledger.sqlite3"
    guard.close()
    ledger = S9OperationalLedger.create(path)
    deadline = ledger.start_global_deadline()
    ledger.update_execution(
        gate="G1", status="RUNNING", elapsed_ms=0,
        deadline_ns=deadline, process_state="RUNNING",
    )
    alias = ledger.register_media(
        "synthetic-message-media", profile="F", expected_bytes=SIZE,
    )
    return ledger, alias


def _plan(expected_bytes: int = SIZE) -> DownloadPlan:
    candidate = DownloadCandidate(
        media_item_id=1,
        channel_id=IDENTITY[0],
        telegram_message_id=IDENTITY[1],
        media_ordinal=IDENTITY[2],
        telegram_media_id="synthetic-media",
        expected_bytes=expected_bytes,
        original_filename="fixture.bin",
        lineage=(("course", "Synthetic"), ("lesson", "Fixture")),
    )
    item = PlanItem(IDENTITY, candidate, "PENDING")
    return DownloadPlan(
        "synthetic-plan", DownloadSelection(IDENTITY[0]), "Synthetic",
        True, 1, (item,),
    )


def _two_item_plan() -> DownloadPlan:
    second_identity = (IDENTITY[0], IDENTITY[1] + 1, IDENTITY[2])
    items = []
    for index, identity in enumerate((IDENTITY, second_identity), start=1):
        candidate = DownloadCandidate(
            media_item_id=index,
            channel_id=identity[0],
            telegram_message_id=identity[1],
            media_ordinal=identity[2],
            telegram_media_id=f"synthetic-media-{index}",
            expected_bytes=SIZE,
            original_filename=f"fixture-{index}.bin",
            lineage=(("course", "Synthetic"), ("lesson", f"Fixture {index}")),
        )
        items.append(PlanItem(identity, candidate, "PENDING"))
    return DownloadPlan(
        "synthetic-two-plan", DownloadSelection(IDENTITY[0]), "Synthetic",
        True, 2, tuple(items),
    )


class _SyntheticApplication:
    def __init__(self, tmp_path: Path, action=None) -> None:
        self.download_root = tmp_path / "downloads"
        self.progress_callback = None
        self.chunk_callback = None
        self.chunk_reserver = None
        self.operation_reserver = None
        self.pre_append_check = None
        self.action = action
        self.calls = 0
        self.reservation_seen_before_request = False

    async def download(self, *_identity):
        self.calls += 1
        lease = await self.chunk_reserver(SIZE)
        assert lease is not None
        self.reservation_seen_before_request = True
        if self.action is not None:
            return await self.action(lease)
        # This response length is the synthetic gateway observation. The
        # outcome deliberately disagrees to prove the queue does not use the
        # eventual file-size/result field as byte-accounting evidence.
        lease.received(3)
        return SimpleNamespace(result="DOWNLOADED", transferred_bytes=999)


def _accounting(
    ledger: S9OperationalLedger, alias: str, *, recovery: bool = False,
    expected_bytes: int = SIZE, measurement_source: str = "SYNTHETIC_TEST",
):
    return S9QueueAccounting(
        ledger,
        {IDENTITY: QueueMediaBinding(alias, expected_bytes)},
        measurement_source=measurement_source,
        recovery=recovery,
    )


def _queue(tmp_path: Path, app: _SyntheticApplication, accounting, *, attempts: int = 1):
    return DownloadQueue(
        repository=object(),
        application=app,
        workers=1,
        attempts_per_media=attempts,
        max_media_items=1,
        max_transfer_bytes=F_CAP,
        free_space=lambda _path: 10**12,
        queue_accounting=accounting,
    )


def _set_cli_supervisor_environment(monkeypatch, ledger: S9OperationalLedger) -> None:
    monkeypatch.setenv(HANDSHAKE_DIR_ENV, str(ledger.path.parent))
    monkeypatch.setenv(HANDSHAKE_NONCE_ENV, "a" * 64)
    monkeypatch.setenv(S9_LEDGER_PATH_ENV, str(ledger.path))
    monkeypatch.setenv(S9_MEASUREMENT_SOURCE_ENV, "SYNTHETIC_TEST")
    monkeypatch.setenv(S9_PROFILE_ENV, "F")
    monkeypatch.setenv(S9_SUPERVISED_CHILD_ENV, "1")


def test_s9_run_start_persists_one_g1_deadline_before_queue_stage(tmp_path: Path) -> None:
    context = start_supervised_run(tmp_path / "new-supervised-run")
    snapshot = S9OperationalLedger(context.ledger_path).snapshot()
    starts = [
        event for event in snapshot["critical_audit"]["events"]
        if event["event_type"] == "RUN_DEADLINE_STARTED"
    ]

    assert context.deadline_ns == snapshot["run"]["deadline_ns"]
    assert snapshot["run"]["gate"] == "G1"
    assert snapshot["run"]["status"] == "RUNNING"
    assert len(starts) == 1
    assert '"seconds":3600' in starts[0]["details_json"]


def test_s9_runner_accepts_only_bounded_remote_hash_queue_arguments(
    tmp_path: Path,
) -> None:
    common = [
        "download", "queue", "--channel-id", str(IDENTITY[0]),
        "--database", str(tmp_path / "catalog.sqlite3"),
        "--download-dir", str(tmp_path / "downloads"),
        "--workers", "1", "--attempts-per-media", "1",
        "--max-media-items", "8", "--max-transfer-bytes", str(F_CAP),
        "--integrity-mode", "REMOTE_HASH_REQUIRED",
    ]
    assert _validate_supervised_queue_arguments(common, "F") == common
    with pytest.raises(OfflineRunnerError, match="QUEUE_ARGUMENTS_INVALID"):
        _validate_supervised_queue_arguments([*common, "--confirm"], "F")
    invalid_m = common.copy()
    invalid_m[invalid_m.index("--max-media-items") + 1] = "2"
    invalid_m[invalid_m.index("--max-transfer-bytes") + 1] = str(M_MAX_CAP)
    with pytest.raises(OfflineRunnerError, match="QUEUE_LIMIT_INVALID"):
        _validate_supervised_queue_arguments(invalid_m, "M")


def test_supervised_queue_cannot_start_before_g3_pass(tmp_path: Path) -> None:
    context = start_supervised_run(tmp_path / "run")
    arguments = [
        "download", "queue", "--channel-id", str(IDENTITY[0]),
        "--database", str(context.run_directory / "catalog.sqlite3"),
        "--download-dir", str(context.run_directory / "downloads"),
        "--workers", "1", "--attempts-per-media", "1",
        "--max-media-items", "8", "--max-transfer-bytes", str(F_CAP),
        "--integrity-mode", "REMOTE_HASH_REQUIRED",
    ]

    with pytest.raises(OfflineRunnerError, match="QUEUE_REQUIRES_G3_PASS"):
        run_supervised_queue(
            tmp_path / "queue-output", context.ledger_path, arguments,
            profile="F", require_tty=False,
        )
    assert not (context.run_directory / "downloads").exists()


def test_s9_queue_persists_only_gateway_observed_bytes(tmp_path: Path) -> None:
    ledger, alias = _ledger(tmp_path)
    app = _SyntheticApplication(tmp_path)
    result = asyncio.run(_queue(tmp_path, app, _accounting(ledger, alias)).run(_plan()))

    assert app.reservation_seen_before_request is True
    assert app.calls == 1
    assert result.failed == 0
    assert result.transferred_bytes == 3
    snapshot = ledger.snapshot()
    budget = snapshot["budgets"]["F"]
    assert budget["observed"] == 3
    assert budget["uncertain"] == 0
    assert budget["reserved"] == 0
    reservation = snapshot["reservations"][0]
    assert reservation["amount"] == SIZE
    assert reservation["observed"] == 3
    assert reservation["measurement_source"] == "SYNTHETIC_TEST"
    assert len(snapshot["disk_checks"]) == 1
    assert snapshot["disk_checks"][0]["extra"] == 256 * 1024 * 1024

    _accounting(ledger, alias).record_queue_result(
        status="COMPLETED", result="PASS", cause="NONE", observed_bytes=3,
    )
    snapshot = ledger.snapshot()
    assert snapshot["run"]["gate"] == "G5"
    assert snapshot["run"]["status"] == "RUNNING"
    assert snapshot["run"]["result"] == "PASS"
    queue_event = next(
        event for event in reversed(snapshot["critical_audit"]["events"])
        if event["event_type"] == "GATE_STATE_UPDATED"
        and '"gate":"G5"' in event["details_json"]
    )
    assert '"observed_bytes":3' in queue_event["details_json"]


def test_s9_queue_recovery_keeps_uncertain_bytes_charged(tmp_path: Path) -> None:
    ledger, alias = _ledger(tmp_path)

    async def interrupted(lease):
        lease.charge_uncertain()
        raise DownloadError("NETWORK")

    first_app = _SyntheticApplication(tmp_path, interrupted)
    first = asyncio.run(_queue(
        tmp_path, first_app, _accounting(ledger, alias),
    ).run(_plan()))
    assert first.failed == 1
    assert ledger.snapshot()["budgets"]["F"]["uncertain"] == SIZE

    ledger.record_interruption(alias)
    async def overlapped_resume(first_lease):
        first_lease.received(3)
        next_lease = await second_app.chunk_reserver(SIZE)
        assert next_lease is not None
        next_lease.received(2)
        return SimpleNamespace(result="DOWNLOADED", transferred_bytes=999)

    second_app = _SyntheticApplication(tmp_path, overlapped_resume)
    second = asyncio.run(_queue(
        tmp_path, second_app, _accounting(ledger, alias, recovery=True),
    ).run(_plan()))
    budget = ledger.snapshot()["budgets"]["F"]
    assert second.failed == 0
    assert budget["uncertain"] == SIZE
    assert second.transferred_bytes == 5
    assert budget["observed"] == 5
    assert budget["consumed"] == SIZE + 5
    assert ledger.snapshot()["run"]["recoveries"] == 1


def test_supervised_contained_f_interruption_enables_one_recovery(
    tmp_path: Path,
) -> None:
    ledger, alias = _ledger(tmp_path)
    initial_sequence = ledger.snapshot()["critical_audit"]["head_sequence"]
    ledger.begin_attempt(alias)
    reservation_id = ledger.reserve_bytes(alias, SIZE)
    ledger.settle_bytes(reservation_id)
    stopped = SimpleNamespace(
        process_control_gate="PASS", reason="STAGE_TIMEOUT",
    )

    assert _record_f_interruption_after_supervised_stop(
        ledger, profile="F", supervisor=stopped,
        after_sequence=initial_sequence,
    ) is True
    assert ledger.snapshot()["budgets"]["F"]["uncertain"] == SIZE
    assert ledger.begin_attempt(alias, recovery=True) == 2
    assert ledger.snapshot()["run"]["interruptions"] == 1
    assert ledger.snapshot()["run"]["recoveries"] == 1


def test_supervised_stop_without_contained_f_attempt_cannot_enable_recovery(
    tmp_path: Path,
) -> None:
    ledger, _alias = _ledger(tmp_path)
    initial_sequence = ledger.snapshot()["critical_audit"]["head_sequence"]
    stopped = SimpleNamespace(
        process_control_gate="UNCONTAINED", reason="STAGE_TIMEOUT",
    )

    assert _record_f_interruption_after_supervised_stop(
        ledger, profile="F", supervisor=stopped,
        after_sequence=initial_sequence,
    ) is False
    assert ledger.snapshot()["run"]["interruptions"] == 0


def test_supervised_cleanup_timeout_after_g5_pass_does_not_consume_interruption(
    tmp_path: Path,
) -> None:
    ledger, alias = _ledger(tmp_path)
    initial_sequence = ledger.snapshot()["critical_audit"]["head_sequence"]
    ledger.begin_attempt(alias)
    ledger.update_execution(
        gate="G5", status="RUNNING", elapsed_ms=0,
        deadline_ns=ledger.active_global_deadline(),
        process_state="RUNNING", result="PASS",
    )
    stopped = SimpleNamespace(
        process_control_gate="PASS", reason="STAGE_TIMEOUT",
    )

    assert _record_f_interruption_after_supervised_stop(
        ledger, profile="F", supervisor=stopped,
        after_sequence=initial_sequence,
    ) is False
    assert ledger.snapshot()["run"]["interruptions"] == 0


def test_human_queue_decline_is_durably_classified_as_cancelled(
    tmp_path: Path,
) -> None:
    ledger, alias = _ledger(tmp_path)
    _accounting(ledger, alias).record_queue_result(
        status="CANCELLED", result="CANCELLED", cause="CANCELLED",
        observed_bytes=0,
    )

    snapshot = S9OperationalLedger(ledger.path).snapshot()
    assert snapshot["run"]["gate"] == "G5"
    assert snapshot["run"]["status"] == "RUNNING"
    assert snapshot["run"]["result"] == "CANCELLED"
    assert snapshot["run"]["cause"] == "CANCELLED"


def test_s9_media_profile_m_uses_gateway_observed_bytes_not_expected_size(
    tmp_path: Path,
) -> None:
    guard = _create_private_directory(tmp_path / "private-m-ledger")
    path = guard.path / "ledger.sqlite3"
    guard.close()
    ledger = S9OperationalLedger.create(path)
    deadline = ledger.start_global_deadline()
    ledger.update_execution(
        gate="G1", status="RUNNING", elapsed_ms=0,
        deadline_ns=deadline, process_state="RUNNING",
    )
    alias = ledger.register_media(
        "synthetic-large-media", profile="M", expected_bytes=GIB, fresh=True,
    )
    accounting = _accounting(
        ledger, alias, expected_bytes=GIB,
        measurement_source="GATEWAY_RESPONSE",
    )

    class LargeSyntheticApplication(_SyntheticApplication):
        async def download(self, *_identity):
            self.calls += 1
            lease = await self.chunk_reserver(CHUNK)
            assert lease is not None
            self.reservation_seen_before_request = True
            lease.received(123)
            return SimpleNamespace(result="DOWNLOADED", transferred_bytes=GIB)

    app = LargeSyntheticApplication(tmp_path)
    queue = _queue(tmp_path, app, accounting)
    queue.max_transfer_bytes = media_m_cap(GIB)
    result = asyncio.run(queue.run(_plan(GIB)))

    assert result.transferred_bytes == 123
    assert result.outcomes[0][1] == "COMPLETED"
    reservation = ledger.snapshot()["reservations"][0]
    assert reservation["amount"] == CHUNK
    assert reservation["observed"] == 123
    assert reservation["measurement_source"] == "GATEWAY_RESPONSE"


def test_s9_queue_rejects_nonfrozen_worker_and_attempt_limits_before_download(
    tmp_path: Path,
) -> None:
    ledger, alias = _ledger(tmp_path)
    app = _SyntheticApplication(tmp_path)
    queue = _queue(tmp_path, app, _accounting(ledger, alias), attempts=2)

    with pytest.raises(DownloadError) as error:
        asyncio.run(queue.run(_plan()))
    assert error.value.category == "S9_ACCOUNTING_FAILED"
    assert app.calls == 0
    assert ledger.snapshot()["media"][0]["attempts"] == 0


def test_s9_queue_budget_failure_blocks_before_gateway_request(tmp_path: Path) -> None:
    ledger, alias = _ledger(tmp_path)
    ledger.begin_attempt(alias)
    reservation = ledger.reserve_bytes(alias, F_CAP)
    ledger.settle_bytes(
        reservation, observed=F_CAP, measurement_source="SYNTHETIC_TEST",
    )
    app = _SyntheticApplication(tmp_path)
    result = asyncio.run(_queue(
        tmp_path, app, _accounting(ledger, alias),
    ).run(_plan()))

    assert result.failed == 1
    assert result.outcomes[0][1] == "BLOCKED"
    assert result.outcomes[0][2] == "S9_ACCOUNTING_FAILED"
    assert app.calls == 1
    assert app.reservation_seen_before_request is False
    assert ledger.snapshot()["budgets"]["F"]["remaining"] == 0


def test_s9_disk_reserve_blocks_before_gateway_request(tmp_path: Path) -> None:
    ledger, alias = _ledger(tmp_path)
    app = _SyntheticApplication(tmp_path)
    queue = _queue(tmp_path, app, _accounting(ledger, alias))
    plan = _plan()
    available = plan.additional_disk_bytes + plan.safety_margin + 256 * 1024 * 1024 - 1
    queue.free_space = lambda _path: available

    result = asyncio.run(queue.run(plan))

    assert result.failed == 1
    assert result.outcomes[0][1] == "BLOCKED"
    assert result.outcomes[0][2] == "INSUFFICIENT_DISK_SPACE"
    assert app.calls == 0
    assert ledger.snapshot()["media"][0]["attempts"] == 0
    check = ledger.snapshot()["disk_checks"][0]
    assert check["pending"] == SIZE
    assert check["extra"] == 256 * 1024 * 1024


def test_s9_queue_plan_mismatch_fails_before_attempt_or_transfer(tmp_path: Path) -> None:
    ledger, alias = _ledger(tmp_path)
    app = _SyntheticApplication(tmp_path)
    queue = _queue(tmp_path, app, _accounting(ledger, alias))

    with pytest.raises(DownloadError) as error:
        asyncio.run(queue.run(_plan(expected_bytes=SIZE + 1)))
    assert error.value.category == "S9_ACCOUNTING_FAILED"
    assert app.calls == 0
    assert ledger.snapshot()["media"][0]["attempts"] == 0


def test_s9_queue_accounting_rejects_untrusted_measurement_source(tmp_path: Path) -> None:
    ledger, alias = _ledger(tmp_path)
    with pytest.raises(LedgerError, match="TRUSTED_BYTE_SOURCE_UNAVAILABLE"):
        S9QueueAccounting(
            ledger,
            {IDENTITY: QueueMediaBinding(alias, SIZE)},
            measurement_source="FINAL_FILE_SIZE",
        )


def test_s9_first_floodwait_stops_queue_and_is_recorded_terminally(
    tmp_path: Path,
) -> None:
    ledger, first_alias = _ledger(tmp_path)
    second_identity = (IDENTITY[0], IDENTITY[1] + 1, IDENTITY[2])
    second_alias = ledger.register_media(
        "synthetic-second-media", profile="F", expected_bytes=SIZE,
    )
    accounting = S9QueueAccounting(
        ledger,
        {
            IDENTITY: QueueMediaBinding(first_alias, SIZE),
            second_identity: QueueMediaBinding(second_alias, SIZE),
        },
        measurement_source="SYNTHETIC_TEST",
    )

    class FloodWaitApplication(_SyntheticApplication):
        def __init__(self, tmp_path: Path) -> None:
            super().__init__(tmp_path)
            self.identities = []

        async def download(self, *identity):
            self.identities.append(identity)
            raise DownloadError("RATE_LIMITED", failure_phase="REMOTE_HASH")

    app = FloodWaitApplication(tmp_path)
    queue = _queue(tmp_path, app, accounting, attempts=1)
    queue.max_media_items = 2

    result = asyncio.run(queue.run(_two_item_plan()))
    accounting.record_queue_result(
        status="BLOCKED", result="BLOCKED", cause="FLOODWAIT",
        observed_bytes=0,
    )

    snapshot = ledger.snapshot()
    assert app.identities == [IDENTITY]
    assert result.failed == 2
    assert [status for _, status, _ in result.outcomes] == ["BLOCKED", "BLOCKED"]
    assert result.outcomes[0][2] == "RATE_LIMITED"
    assert snapshot["run"]["status"] == "BLOCKED"
    assert snapshot["run"]["cause"] == "FLOODWAIT"


def test_floodwait_during_gateway_restore_keeps_rate_limit_category() -> None:
    translated = cli_module._download_gateway_initialization_error(RateLimited(90))

    assert isinstance(translated, DownloadGatewayError)
    assert translated.category == "RATE_LIMITED"
    assert translated.retry_after_seconds == 90


def test_cli_s9_path_rejects_confirm_bypass_before_planning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, alias = _ledger(tmp_path)
    _set_cli_supervisor_environment(monkeypatch, ledger)
    accounting = _accounting(ledger, alias)
    args = SimpleNamespace(
        confirm=True,
        credentials_action="queue",
        integrity_mode="REMOTE_HASH_REQUIRED",
        max_media_items=1,
        max_transfer_bytes=F_CAP,
        workers=1,
        attempts_per_media=1,
    )

    with pytest.raises(ConfigurationError):
        cli_module._download_batch(
            args=args,
            selection_prompt=lambda _prompt: "sim",
            gateway_factory=lambda _credentials: None,
            credentials_loader=lambda: None,
            queue_accounting=accounting,
        )


@pytest.mark.parametrize("answer", ["s", "n"])
def test_s9_private_directories_are_prepared_only_after_g4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: str,
) -> None:
    ledger, _alias = _ledger(tmp_path)
    _set_cli_supervisor_environment(monkeypatch, ledger)
    args = cli_module._parse_arguments([
        "download", "queue", "--channel-id", str(IDENTITY[0]),
        "--scope", "channel", "--database", str(tmp_path / "fixture.sqlite3"),
        "--download-dir", str(tmp_path / "downloads"), "--workers", "1",
        "--attempts-per-media", "1", "--max-media-items", "1",
        "--max-transfer-bytes", str(F_CAP),
    ])
    steps: list[str] = []

    class Planner:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def build(self, _selection):
            return _plan()

    class Accounting:
        gate = "G5"

        def validate_queue(self, **_kwargs) -> None:
            pass

        def validate_plan(self, _plan) -> None:
            pass

        def record_preconfirmation_pass(self) -> None:
            steps.append("accounted")

        def record_queue_result(self, **_kwargs) -> None:
            pass

    class Guard:
        def close(self) -> None:
            steps.append("closed")

    class Queue:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def run(self, _plan):
            steps.append("queue")
            return SimpleNamespace(
                outcomes=((IDENTITY, "COMPLETED", ""),), cancelled=False,
                transferred_bytes=SIZE, attempts=1, elapsed_seconds=0.1, failed=False,
            )

    def confirm(*_args, **_kwargs):
        steps.append("confirmation")
        return answer

    def prepare(_root, _candidates):
        steps.append("directories")
        return [Guard()]

    def forbidden(*_args, **_kwargs):
        raise AssertionError("gateway and credentials must not be used in this test")

    monkeypatch.setattr("telegram_courses.s5_downloads.DownloadPlanner", Planner)
    monkeypatch.setattr("telegram_courses.s5_downloads.DownloadQueue", Queue)
    monkeypatch.setattr(cli_module, "supervised_confirmation", confirm)
    monkeypatch.setattr(cli_module, "_prepare_s9_download_directories", prepare)
    assert cli_module._download_batch(
        args=args, selection_prompt=lambda _prompt: "unused", gateway_factory=forbidden,
        credentials_loader=forbidden, queue_accounting=Accounting(),
    ) == 0
    if answer == "s":
        assert steps == ["confirmation", "accounted", "directories", "queue", "closed"]
    else:
        assert steps == ["confirmation"]


def test_product_private_queue_prepares_guarded_paths_after_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from telegram_courses.downloads import destination_paths
    from telegram_courses.s9_operational_ledger import _open_private_directory_guard

    for name in (HANDSHAKE_DIR_ENV, HANDSHAKE_NONCE_ENV, S9_LEDGER_PATH_ENV,
                 S9_MEASUREMENT_SOURCE_ENV, S9_PROFILE_ENV, S9_SUPERVISED_CHILD_ENV,
                 "TELEGRAM_COURSES_S9_OPERATIONAL_GATE"):
        monkeypatch.delenv(name, raising=False)
    root_guard = _create_private_directory(tmp_path / "downloads")
    root = root_guard.path
    root_guard.close()
    args = cli_module._parse_arguments([
        "download", "queue", "--channel-id", str(IDENTITY[0]), "--scope", "channel",
        "--database", str(tmp_path / "catalog.sqlite3"), "--download-dir", str(root),
        "--max-media-items", "1", "--max-transfer-bytes", str(F_CAP), "--private-downloads",
    ])
    steps: list[str] = []

    class Planner:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def build(self, _selection):
            return _plan()

    class Queue:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def run(self, plan):
            assert steps == ["confirmation"]
            final, _ = destination_paths(root, plan.pending[0].candidate)
            for path in (final.parent.parent, final.parent):
                guard = _open_private_directory_guard(path)
                guard.verify(path)
                guard.close()
            steps.append("queue")
            return SimpleNamespace(outcomes=((IDENTITY, "COMPLETED", ""),), cancelled=False,
                                   transferred_bytes=SIZE, attempts=1, elapsed_seconds=0.1, failed=False)

    def confirm(*_args, **_kwargs):
        steps.append("confirmation")
        return "s"

    def forbidden(*_args, **_kwargs):
        raise AssertionError("gateway and credentials must not be used in this test")

    monkeypatch.setattr("telegram_courses.s5_downloads.DownloadPlanner", Planner)
    monkeypatch.setattr("telegram_courses.s5_downloads.DownloadQueue", Queue)
    monkeypatch.setattr(cli_module, "supervised_confirmation", confirm)
    assert cli_module._download_batch(args=args, selection_prompt=lambda _prompt: "unused",
                                      gateway_factory=forbidden, credentials_loader=forbidden) == 0
    assert steps == ["confirmation", "queue"]


def test_cli_s9_path_stops_before_confirmation_when_limit_check_is_not_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, _alias = _ledger(tmp_path)
    _set_cli_supervisor_environment(monkeypatch, ledger)
    parsed = cli_module._parse_arguments([
        "download", "queue", "--channel-id", str(IDENTITY[0]),
        "--scope", "channel", "--database", str(tmp_path / "fixture.sqlite3"),
        "--download-dir", str(tmp_path / "downloads"), "--workers", "1",
        "--attempts-per-media", "1", "--max-media-items", "1",
        "--max-transfer-bytes", "3",
    ])

    planner_calls = 0

    class _Planner:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def selectable_nodes(self, *_args, **_kwargs):
            return ()

        async def build(self, _selection):
            nonlocal planner_calls
            planner_calls += 1
            return _plan()

    monkeypatch.setattr("telegram_courses.s5_downloads.DownloadPlanner", _Planner)
    def run_inline(coroutine):
        try:
            coroutine.send(None)
        except StopIteration as completed:
            return completed.value
        raise AssertionError("synthetic planner unexpectedly suspended")

    monkeypatch.setattr(cli_module.asyncio, "run", run_inline)
    prompts: list[str] = []
    with pytest.raises(ConfigurationError):
        cli_module._download_batch(
            args=parsed,
            selection_prompt=lambda prompt: prompts.append(prompt) or "sim",
            gateway_factory=lambda _credentials: None,
            credentials_loader=lambda: None,
        )
    assert prompts == []
    assert planner_calls == 2
    assert ledger.snapshot()["media"][0]["attempts"] == 0
