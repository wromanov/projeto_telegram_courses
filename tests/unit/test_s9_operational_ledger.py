"""S9 ledger tests use only temporary, synthetic, offline data."""

import json
import os
import sqlite3
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

import telegram_courses.s9_operational_ledger as ledger_module
from telegram_courses.s9_operational_ledger import (
    DISK_RESERVE,
    F_CAP,
    GIB,
    MIB,
    TOTAL_CAP,
    LedgerError,
    S9OperationalLedger,
    _create_private_directory,
    _verify_windows_private_directory,
    media_m_cap,
)


@pytest.fixture
def planned_ledger(tmp_path: Path) -> S9OperationalLedger:
    return S9OperationalLedger.create(
        _private_ledger_path(tmp_path, "isolated-ledger.sqlite")
    )


def _private_ledger_path(tmp_path: Path, filename: str) -> Path:
    guard = _create_private_directory(tmp_path / f"{filename}.private")
    path = guard.path / filename
    guard.close()
    return path


def _rechain_audit(db: sqlite3.Connection) -> None:
    run_id = db.execute("SELECT run_id FROM meta WHERE singleton=1").fetchone()[0]
    rows = db.execute(
        "SELECT sequence,event_id,event_type,created_ns,details_json "
        "FROM audit_events ORDER BY sequence"
    ).fetchall()
    previous_hash = ledger_module._AUDIT_ZERO_HASH
    for sequence, event_id, event_type, created_ns, details_json in rows:
        event_hash = ledger_module._audit_hash(
            sequence, event_id, event_type, run_id, created_ns,
            details_json, previous_hash,
        )
        db.execute(
            "UPDATE audit_events SET previous_hash=?,event_hash=? WHERE sequence=?",
            (previous_hash, event_hash, sequence),
        )
        previous_hash = event_hash


class _SyntheticAclApi:
    def __init__(self, entries, *, protected: bool = True, fail: bool = False) -> None:
        self.entries = entries
        self.protected = protected
        self.fail = fail

    def attributes(self, _path: Path) -> int:
        return 0x10

    def current_user_sid(self) -> str:
        return "S-1-5-21-1000"

    def inspect_acl(self, _path: Path):
        if self.fail:
            raise OSError("synthetic ACL lookup failure")
        return self.current_user_sid(), self.protected, self.entries


def _valid_synthetic_acl_entries():
    return (
        (0, 3, 0x001F01FF, "S-1-5-21-1000"),
        (0, 3, 0x001F01FF, "S-1-5-18"),
        (0, 3, 0x001F01FF, "S-1-5-32-544"),
    )


def test_private_directory_policy_accepts_only_expected_dacl() -> None:
    _verify_windows_private_directory(
        Path("synthetic-private"), _SyntheticAclApi(_valid_synthetic_acl_entries()),
    )


def test_shared_or_unknown_dacl_fails_closed() -> None:
    broad = _valid_synthetic_acl_entries() + (
        (0, 3, 0x001F01FF, "S-1-1-0"),
    )
    with pytest.raises(LedgerError, match="LEDGER_PRIVATE_DIRECTORY_UNVERIFIED"):
        _verify_windows_private_directory(
            Path("synthetic-shared"), _SyntheticAclApi(broad),
        )
    with pytest.raises(LedgerError, match="LEDGER_PRIVATE_DIRECTORY_UNVERIFIED"):
        _verify_windows_private_directory(
            Path("synthetic-unknown"), _SyntheticAclApi((), fail=True),
        )


def test_existing_directory_is_not_changed_when_private_creation_is_requested(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    mode_before = stat.S_IMODE(existing.stat().st_mode)
    with pytest.raises(LedgerError, match="LEDGER_PRIVATE_DIRECTORY_CREATE_FAILED"):
        _create_private_directory(existing)
    assert stat.S_IMODE(existing.stat().st_mode) == mode_before


@pytest.mark.skipif(os.name != "nt", reason="directory handle semantics are Windows-specific")
def test_private_directory_handle_blocks_concurrent_rename(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    guard = _create_private_directory(directory)
    replacement = tmp_path / "replacement"

    def attempt_rename() -> bool:
        try:
            os.rename(directory, replacement)
        except OSError:
            return False
        return True

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            renamed = executor.submit(attempt_rename).result(timeout=5)
        assert renamed is False
        assert directory.is_dir()
        assert not replacement.exists()
    finally:
        guard.close()
    os.rename(directory, replacement)
    assert replacement.is_dir()


@pytest.mark.skipif(os.name != "nt", reason="directory handle semantics are Windows-specific")
def test_private_guard_verifies_path_and_closes_after_validation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "private"
    guard = _create_private_directory(directory)
    guard.verify(directory)
    with pytest.raises(LedgerError, match="LEDGER_PRIVATE_DIRECTORY_UNVERIFIED"):
        guard.verify(tmp_path / "other")
    guard.close()
    guard.close()
    with pytest.raises(LedgerError, match="LEDGER_PRIVATE_DIRECTORY_UNVERIFIED"):
        guard.verify(directory)

    def fail_validation(*_args: object) -> None:
        raise LedgerError("LEDGER_PRIVATE_DIRECTORY_UNVERIFIED")

    monkeypatch.setattr(ledger_module, "_verify_windows_private_directory", fail_validation)
    with pytest.raises(LedgerError, match="LEDGER_PRIVATE_DIRECTORY_UNVERIFIED"):
        S9OperationalLedger.create(directory / "ledger.sqlite")
    assert not (directory / "ledger.sqlite").exists()
    os.rename(directory, tmp_path / "released")


@pytest.mark.skipif(os.name != "nt", reason="directory handle semantics are Windows-specific")
def test_private_guard_rejects_swapped_handle(tmp_path: Path) -> None:
    first = _create_private_directory(tmp_path / "first")
    second = _create_private_directory(tmp_path / "second")
    original = first._handle
    try:
        first._handle = second._handle
        with pytest.raises(LedgerError, match="LEDGER_PRIVATE_DIRECTORY_UNVERIFIED"):
            first.verify(first.path)
    finally:
        first._handle = original
        first.close()
        second.close()


def test_unprotected_shared_directory_cannot_host_ledger(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    if os.name != "nt":
        shared.chmod(0o755)
    with pytest.raises(LedgerError, match="LEDGER_PRIVATE_DIRECTORY_UNVERIFIED"):
        S9OperationalLedger.create(shared / "ledger.sqlite")
    assert not (shared / "ledger.sqlite").exists()


def test_ledger_file_creation_failure_does_not_leave_a_partial_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _private_ledger_path(tmp_path, "creation-failure.sqlite")
    original_open = ledger_module.os.open

    def fail_ledger_open(path, *args, **kwargs):
        if Path(path) == target:
            raise PermissionError("synthetic create failure")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(ledger_module.os, "open", fail_ledger_open)
    with pytest.raises(LedgerError, match="LEDGER_CREATE_FAILED"):
        S9OperationalLedger.create(target)
    assert not target.exists()
    assert not target.with_name(target.name + ".quarantine").exists()


@pytest.fixture
def ledger(planned_ledger: S9OperationalLedger) -> S9OperationalLedger:
    deadline = planned_ledger.start_global_deadline()
    planned_ledger.update_execution(gate="G1", status="RUNNING", elapsed_ms=0, deadline_ns=deadline)
    return planned_ledger


def media(ledger: S9OperationalLedger, identity: str = "synthetic-1") -> str:
    alias = ledger.register_media(identity, profile="F", expected_bytes=MIB)
    ledger.begin_attempt(alias)
    return alias


def test_reservation_observation_uncertainty_and_reopen(ledger: S9OperationalLedger) -> None:
    alias = media(ledger)
    first = ledger.reserve_bytes(alias, 100)
    ledger.settle_bytes(first, observed=70, measurement_source="SYNTHETIC_TEST")
    second = ledger.reserve_bytes(alias, 200)
    ledger.settle_bytes(second)
    third = ledger.reserve_bytes(alias, 300)
    reopened = S9OperationalLedger(ledger.path)
    budget = reopened.snapshot()["budgets"]["F"]
    assert budget == {"cap": F_CAP, "planned": MIB, "reserved": 300,
                      "observed": 70, "uncertain": 200, "consumed": 270,
                      "remaining": F_CAP - 570}
    with pytest.raises(LedgerError, match="RESERVATION_OWNER_LOST"):
        reopened.settle_bytes(third, observed=0, measurement_source="SYNTHETIC_TEST")
    reopened.settle_bytes(third)
    assert reopened.snapshot()["budgets"]["F"]["remaining"] == F_CAP - 570
    with pytest.raises(LedgerError, match="RESERVATION_STATE_INVALID"):
        reopened.settle_bytes(second, observed=0, measurement_source="SYNTHETIC_TEST")


def test_hot_path_uses_incremental_state_until_an_explicit_checkpoint(
    ledger: S9OperationalLedger, monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_validate = S9OperationalLedger._validate
    replay_count = 0

    def count_replay(db: sqlite3.Connection) -> dict[str, object]:
        nonlocal replay_count
        replay_count += 1
        return original_validate(db)

    monkeypatch.setattr(
        S9OperationalLedger, "_validate", staticmethod(count_replay),
    )
    alias = media(ledger, "incremental-cache")
    reservation_id = ledger.reserve_bytes(alias, 257)
    ledger.settle_bytes(
        reservation_id, observed=193, measurement_source="SYNTHETIC_TEST",
    )
    for _ in range(3):
        snapshot = ledger.snapshot()
        assert snapshot["budgets"]["F"]["observed"] == 193
    assert replay_count == 0
    ledger.checkpoint()
    assert replay_count == 1


def test_quarantine_marker_during_epoch_blocks_before_mutation_or_ack(
    ledger: S9OperationalLedger,
) -> None:
    alias = media(ledger, "quarantine-fence")
    before = ledger.snapshot()["critical_audit"]["event_count"]
    marker = ledger.path.with_name(ledger.path.name + ".quarantine")
    marker.write_bytes(b"S9_LEDGER_QUARANTINED_V1\n")
    with pytest.raises(LedgerError, match="CRITICAL_AUDIT_QUARANTINED"):
        ledger.reserve_bytes(alias, 17)
    with pytest.raises(LedgerError, match="CRITICAL_AUDIT_QUARANTINED"):
        ledger.record_critical_event(
            "RECEIPT_PREPARED", details={"receipt_sha256": "a" * 64},
            event_id="f" * 32,
        )
    with sqlite3.connect(ledger.path) as db:
        assert db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == before


def test_cooperative_raw_database_change_is_replayed_and_blocks_receipts(
    ledger: S9OperationalLedger,
) -> None:
    alias = media(ledger, "raw-database-change")
    reservation_id = ledger.reserve_bytes(alias, 100)
    # A real SQLite connection changes the temporary database and WAL. The
    # epoch's data_version signal must trigger fresh full replay before use.
    with sqlite3.connect(ledger.path) as db:
        db.execute(
            "UPDATE reservations SET amount=amount+1 WHERE reservation_id=?",
            (reservation_id,),
        )
    with pytest.raises(LedgerError, match="AUDIT_STATE_MISMATCH"):
        ledger.snapshot()
    assert ledger.path.with_name(ledger.path.name + ".quarantine").is_file()
    with sqlite3.connect(ledger.path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type IN "
            "('RECEIPT_PERSISTED','GATE_FINISHED')"
        ).fetchone()[0] == 0


def test_external_commit_during_delta_is_not_absorbed_before_next_ack(
    ledger: S9OperationalLedger,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_apply = ledger._apply_committed_delta
    original_validate = S9OperationalLedger._validate
    injected = False
    replay_count = 0

    def inject_external_commit(db, audit_event, ack) -> None:
        nonlocal injected
        if not injected:
            external = sqlite3.connect(ledger.path, isolation_level=None)
            try:
                external.execute("BEGIN IMMEDIATE")
                external.execute("UPDATE meta SET created_ns=created_ns+1 WHERE singleton=1")
                external.commit()
            finally:
                external.close()
            injected = True
        original_apply(db, audit_event, ack)

    def count_replay(db: sqlite3.Connection) -> dict[str, object]:
        nonlocal replay_count
        replay_count += 1
        return original_validate(db)

    monkeypatch.setattr(ledger, "_apply_committed_delta", inject_external_commit)
    monkeypatch.setattr(
        S9OperationalLedger, "_validate", staticmethod(count_replay),
    )

    first_ack = ledger.record_critical_event(
        "SECURITY_BLOCK", details={"status": "BLOCKED"}, event_id="a" * 32,
    )
    assert first_ack["event_id"] == "a" * 32
    assert injected is True
    assert replay_count == 1, "the ACK must follow a fresh replay after the external commit"

    second_ack = ledger.record_critical_event(
        "SECURITY_BLOCK", details={"status": "BLOCKED"}, event_id="b" * 32,
    )
    assert second_ack["event_id"] == "b" * 32
    assert replay_count == 1, "the replay must not be repeated or absorbed into a stale baseline"


def test_cooperative_commit_during_fresh_replay_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = S9OperationalLedger.create(_private_ledger_path(tmp_path, "replay-race.sqlite"))
    original_validate = S9OperationalLedger._validate
    injected = False

    def inject_commit_during_replay(db: sqlite3.Connection) -> dict[str, object]:
        nonlocal injected
        if not injected:
            external = sqlite3.connect(ledger.path, isolation_level=None)
            try:
                external.execute("BEGIN IMMEDIATE")
                external.execute(
                    "UPDATE meta SET created_ns=created_ns+1 WHERE singleton=1",
                )
                external.commit()
            finally:
                external.close()
            injected = True
        return original_validate(db)

    monkeypatch.setattr(
        S9OperationalLedger,
        "_validate",
        staticmethod(inject_commit_during_replay),
    )
    with pytest.raises(LedgerError, match="LEDGER_EXTERNAL_WRITER_DURING_REPLAY"):
        ledger.checkpoint()

    assert injected is True
    assert ledger.path.with_name(ledger.path.name + ".quarantine").is_file()


def test_duplicate_reservation_and_attempts_cannot_be_replayed(ledger: S9OperationalLedger) -> None:
    alias = media(ledger)
    rid = "a" * 32
    ledger.reserve_bytes(alias, 20, reservation_id=rid)
    with pytest.raises(LedgerError, match="DUPLICATE_RESERVATION"):
        ledger.reserve_bytes(alias, 20, reservation_id=rid)
    assert ledger.snapshot()["budgets"]["F"]["reserved"] == 20
    ledger.record_interruption(alias)
    assert ledger.begin_attempt(alias, recovery=True) == 2
    with pytest.raises(LedgerError, match="RECOVERY_LIMIT"):
        ledger.begin_attempt(alias, recovery=True)
    assert ledger.begin_attempt(alias) == 3
    with pytest.raises(LedgerError, match="ATTEMPT_LIMIT"):
        ledger.begin_attempt(alias)
    with pytest.raises(LedgerError, match="INTERRUPTION_LIMIT"):
        ledger.record_interruption(alias)


def test_scan_counts_repeated_observations_and_incremental_window(ledger: S9OperationalLedger) -> None:
    first = ledger.begin_scan(max_messages=200)
    ledger.finish_scan(first, 200)
    second = ledger.begin_scan(max_messages=200, incremental=True, reconcile_window=50)
    ledger.finish_scan(second, 200)
    ledger.begin_scan(max_messages=200, incremental=True, reconcile_window=50)
    with pytest.raises(LedgerError, match="SCAN_LIMIT"):
        ledger.begin_scan(max_messages=1)
    assert len(ledger.snapshot()["scans"]) == 3
    with pytest.raises(LedgerError, match="SCAN_WINDOW_INVALID"):
        ledger.begin_scan(max_messages=1, incremental=True, reconcile_window=51)


@pytest.mark.parametrize("value", [-1, 0, True, 201])
def test_scan_rejects_invalid_limits(ledger: S9OperationalLedger, value: int) -> None:
    with pytest.raises(LedgerError):
        ledger.begin_scan(max_messages=value)


def test_profile_f_limits_and_rollback(ledger: S9OperationalLedger) -> None:
    aliases = [ledger.register_media(str(i), profile="F", expected_bytes=128 * MIB) for i in range(8)]
    with pytest.raises(LedgerError, match="MEDIA_LIMIT"):
        ledger.register_media("ninth", profile="F", expected_bytes=1)
    with pytest.raises(LedgerError):
        ledger.register_media("oversized", profile="F", expected_bytes=128 * MIB + 1)
    ledger.begin_attempt(aliases[0])
    rid = ledger.reserve_bytes(aliases[0], F_CAP)
    with pytest.raises(LedgerError, match="BUDGET_EXCEEDED"):
        ledger.reserve_bytes(aliases[0], 1)
    assert len(ledger.snapshot()["reservations"]) == 1
    ledger.settle_bytes(rid, observed=F_CAP, measurement_source="SYNTHETIC_TEST")
    assert ledger.snapshot()["budgets"]["F"]["remaining"] == 0


def test_profile_m_formula_and_combined_budget(ledger: S9OperationalLedger) -> None:
    f = media(ledger)
    m = ledger.register_media("synthetic-m", profile="M", expected_bytes=2 * GIB)
    ledger.begin_attempt(m)
    assert media_m_cap(2 * GIB) == 2_147_745_792
    assert media_m_cap(GIB + 1) == GIB + 2 * 262_144
    ledger.reserve_bytes(f, F_CAP)
    ledger.reserve_bytes(m, media_m_cap(2 * GIB))
    assert ledger.snapshot()["aggregate_remaining"] == 0
    assert TOTAL_CAP == 2_684_616_704
    with pytest.raises(LedgerError, match="ATTEMPT_LIMIT"):
        ledger.begin_attempt(m)
    with pytest.raises(LedgerError, match="MEDIA_LIMIT"):
        ledger.register_media("another-m", profile="M", expected_bytes=GIB)
    with pytest.raises(LedgerError, match="MEDIA_LIMIT"):
        ledger.register_media("old-m", profile="M", expected_bytes=GIB, fresh=False)


def test_concurrent_reservations_are_serialized(ledger: S9OperationalLedger) -> None:
    alias = media(ledger)

    def reserve() -> str:
        try:
            ledger.reserve_bytes(alias, F_CAP)
            return "ok"
        except LedgerError:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: reserve(), range(2)))
    assert sorted(results) == ["blocked", "ok"]
    snapshot = S9OperationalLedger(ledger.path).snapshot()
    assert snapshot["budgets"]["F"]["reserved"] == F_CAP
    assert len(snapshot["reservations"]) == 1


def test_interrupted_transaction_rolls_back_and_pending_reservation_is_charged(ledger: S9OperationalLedger) -> None:
    alias = media(ledger)
    ledger.reserve_bytes(alias, 17)
    script = (
        "import os, sqlite3, sys; db=sqlite3.connect(sys.argv[1], isolation_level=None); "
        "db.execute('BEGIN IMMEDIATE'); db.execute('UPDATE reservations SET amount=100'); "
        "os._exit(9)"
    )
    completed = subprocess.run([sys.executable, "-c", script, os.fspath(ledger.path)],
                               check=False, timeout=15, capture_output=True)
    assert completed.returncode == 9
    reopened = S9OperationalLedger(ledger.path)
    assert reopened.snapshot()["budgets"]["F"]["reserved"] == 17


def test_corrupt_and_foreign_databases_fail_closed(tmp_path: Path, ledger: S9OperationalLedger) -> None:
    foreign = _private_ledger_path(tmp_path, "foreign.sqlite")
    with sqlite3.connect(foreign) as db:
        db.execute("CREATE TABLE unrelated (x)")
    before = foreign.read_bytes()
    with pytest.raises(LedgerError):
        S9OperationalLedger(foreign)
    assert foreign.read_bytes() == before
    with pytest.raises(LedgerError):
        S9OperationalLedger.create(foreign)
    ledger.path.write_bytes(b"invalid sqlite file")
    with pytest.raises(LedgerError):
        ledger.checkpoint()


def test_disk_check_includes_s5_margin_and_s9_extra(ledger: S9OperationalLedger, tmp_path: Path) -> None:
    required = GIB + GIB + DISK_RESERVE
    result = ledger.check_disk(tmp_path, pending_bytes=GIB, free_space=lambda _: required)
    assert result["required"] == required
    with pytest.raises(LedgerError, match="INSUFFICIENT_DISK_SPACE"):
        ledger.check_disk(tmp_path, pending_bytes=GIB, free_space=lambda _: required - 1)
    with pytest.raises(LedgerError, match="DISK_QUERY_FAILED"):
        ledger.check_disk(tmp_path, pending_bytes=1, free_space=lambda _: (_ for _ in ()).throw(OSError()))
    checks = ledger.snapshot()["disk_checks"]
    assert len(checks) == 3
    assert checks[-1]["available"] is None
    assert checks[-1]["available_origin"] == "UNKNOWN"


def test_execution_metadata_and_queue_are_strict(ledger: S9OperationalLedger) -> None:
    ledger.validate_queue(workers=1, attempts_per_media=1)
    for workers, attempts in [(2, 1), (1, 2), (True, 1)]:
        with pytest.raises(LedgerError, match="QUEUE_LIMIT"):
            ledger.validate_queue(workers=workers, attempts_per_media=attempts)
    deadline = ledger.snapshot()["run"]["deadline_ns"]
    ledger.update_execution(gate="G5", status="RUNNING", elapsed_ms=2, deadline_ns=deadline,
                            process_state="RUNNING", working_set=1, peak_working_set=2, private_bytes=3)
    with pytest.raises(LedgerError, match="DEADLINE_OR_TIME_INVALID"):
        ledger.update_execution(gate="G5", status="RUNNING", elapsed_ms=1, deadline_ns=deadline)
    with pytest.raises(LedgerError, match="MEMORY_MEASUREMENT_INCOMPLETE"):
        ledger.update_execution(gate="G5", status="RUNNING", elapsed_ms=3, deadline_ns=deadline, working_set=1)
    run = ledger.snapshot()["run"]
    assert run["memory_origin"] == "MEASURED"
    assert run["working_set"] == 1
    assert run["memory_measured_ns"] > 0
    ledger.update_execution(gate="G5", status="COMPLETED", elapsed_ms=3,
                            deadline_ns=deadline, process_state="EXITED")
    assert ledger.snapshot()["run"]["peak_working_set"] == 2


@pytest.mark.parametrize(("profile", "expected_bytes"), [("F", MIB), ("M", GIB)])
def test_s9_second_queue_accepts_registered_already_valid_media_after_g5_pass(
    ledger: S9OperationalLedger, profile: str, expected_bytes: int,
) -> None:
    identity = (123, 456, 0)
    ledger.register_media(
        ":".join(map(str, identity)), profile=profile,
        expected_bytes=expected_bytes,
    )
    deadline = ledger.snapshot()["run"]["deadline_ns"]
    ledger.update_execution(
        gate="G5", status="RUNNING", elapsed_ms=1,
        deadline_ns=deadline, process_state="EXITED", result="PASS",
    )
    item = SimpleNamespace(
        identity=identity,
        candidate=SimpleNamespace(expected_bytes=expected_bytes),
        status="ALREADY_VALID",
        part_bytes=0,
    )
    plan = SimpleNamespace(
        pending=(), already_valid=(item,), eligible=(item,), items=(item,),
    )
    accounting = ledger_module.S9QueueAccounting.register_plan(
        ledger, plan, profile=profile, measurement_source="SYNTHETIC_TEST",
    )
    assert accounting.idempotent_recheck is True
    accounting.validate_plan(plan)


def test_s9_second_queue_rejects_empty_pending_before_g5_pass(
    ledger: S9OperationalLedger,
) -> None:
    identity = (123, 456, 0)
    ledger.register_media(
        ":".join(map(str, identity)), profile="F", expected_bytes=MIB,
    )
    item = SimpleNamespace(
        identity=identity,
        candidate=SimpleNamespace(expected_bytes=MIB),
        status="ALREADY_VALID",
        part_bytes=0,
    )
    plan = SimpleNamespace(
        pending=(), already_valid=(item,), eligible=(item,), items=(item,),
    )
    with pytest.raises(LedgerError, match="IDEMPOTENT_RECHECK_REQUIRES_G5_PASS"):
        ledger_module.S9QueueAccounting.register_plan(
            ledger, plan, profile="F", measurement_source="SYNTHETIC_TEST",
        )


def test_deadline_expires_and_cannot_restart(planned_ledger: S9OperationalLedger, monkeypatch) -> None:
    ledger = planned_ledger
    now = ledger_module.time.time_ns()
    deadline = ledger.start_global_deadline(seconds=1)
    ledger.update_execution(gate="G1", status="RUNNING", elapsed_ms=0, deadline_ns=deadline)
    with pytest.raises(LedgerError, match="DEADLINE_ALREADY_STARTED"):
        ledger.start_global_deadline()
    monkeypatch.setattr(ledger_module.time, "time_ns", lambda: max(now, deadline))
    with pytest.raises(LedgerError, match="DEADLINE_EXPIRED"):
        ledger.begin_scan(max_messages=1)
    assert S9OperationalLedger(ledger.path).snapshot()["run"]["deadline_ns"] == deadline


def test_invalid_logical_state_blocks_reopening(ledger: S9OperationalLedger) -> None:
    alias = media(ledger)
    ledger.reserve_bytes(alias, 10)
    with sqlite3.connect(ledger.path) as db:
        db.execute("UPDATE reservations SET amount=-1")
    with pytest.raises(LedgerError):
        S9OperationalLedger(ledger.path)


def test_floodwait_stops_future_operations_even_after_reopen(ledger: S9OperationalLedger) -> None:
    alias = media(ledger)
    deadline = ledger.snapshot()["run"]["deadline_ns"]
    ledger.update_execution(gate="G5", status="BLOCKED", elapsed_ms=1, deadline_ns=deadline, cause="FLOODWAIT")
    reopened = S9OperationalLedger(ledger.path)
    with pytest.raises(LedgerError, match="RUN_NOT_ACTIVE"):
        reopened.reserve_bytes(alias, 1)
    with pytest.raises(LedgerError, match="RUN_NOT_ACTIVE"):
        reopened.begin_scan(max_messages=1)
    with pytest.raises(LedgerError, match="FLOODWAIT_ALREADY_OBSERVED"):
        reopened.update_execution(gate="G5", status="RUNNING", elapsed_ms=2, deadline_ns=deadline)


def test_identity_is_pseudonymized_and_inconsistent_registration_rejected(ledger: S9OperationalLedger) -> None:
    raw = "private-synthetic-identity"
    alias = ledger.register_media(raw, profile="F", expected_bytes=100)
    assert raw not in str(ledger.snapshot())
    assert len(alias) == 64
    assert ledger.register_media(raw, profile="F", expected_bytes=100) == alias
    with pytest.raises(LedgerError, match="MEDIA_IDENTITY_CONFLICT"):
        ledger.register_media(raw, profile="F", expected_bytes=101)


def test_planning_allowed_but_work_rejected_without_global_deadline(planned_ledger: S9OperationalLedger) -> None:
    alias = planned_ledger.register_media("synthetic", profile="F", expected_bytes=1)
    planned_ledger.update_execution(gate="G0", status="PLANNED", elapsed_ms=0)
    with pytest.raises(LedgerError, match="DEADLINE_NOT_STARTED"):
        planned_ledger.begin_scan(max_messages=1)
    with pytest.raises(LedgerError, match="DEADLINE_NOT_STARTED"):
        planned_ledger.begin_attempt(alias)
    with pytest.raises(LedgerError, match="DEADLINE_NOT_STARTED"):
        planned_ledger.reserve_bytes(alias, 1)
    with pytest.raises(LedgerError, match="DEADLINE_NOT_STARTED"):
        planned_ledger.update_execution(gate="G1", status="RUNNING", elapsed_ms=0)
    assert planned_ledger.snapshot()["scans"] == []
    planned_ledger.start_global_deadline()
    with pytest.raises(LedgerError, match="RUN_NOT_RUNNING"):
        planned_ledger.begin_scan(max_messages=1)
    with pytest.raises(LedgerError, match="RUN_NOT_RUNNING"):
        planned_ledger.begin_attempt(alias)


@pytest.mark.parametrize("terminal", ["COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "BLOCKED"])
def test_terminal_state_freezes_and_marks_open_work_uncertain(ledger: S9OperationalLedger, terminal: str) -> None:
    alias = media(ledger)
    rid = ledger.reserve_bytes(alias, 30)
    ledger.begin_scan(max_messages=200)
    deadline = ledger.snapshot()["run"]["deadline_ns"]
    ledger.update_execution(gate="G5", status=terminal, elapsed_ms=1, deadline_ns=deadline)
    reopened = S9OperationalLedger(ledger.path)
    snapshot = reopened.snapshot()
    assert snapshot["reservations"][0]["state"] == "UNCERTAIN"
    assert snapshot["scans"][0]["state"] == "UNCERTAIN"
    assert snapshot["budgets"]["F"]["remaining"] == F_CAP - 30
    with pytest.raises(LedgerError, match="TERMINAL_STATE_LOCKED"):
        reopened.update_execution(gate="G5", status="PLANNED", elapsed_ms=2, deadline_ns=deadline)
    with pytest.raises(LedgerError, match="RUN_NOT_ACTIVE"):
        reopened.begin_attempt(alias)
    with pytest.raises(LedgerError, match="RESERVATION_STATE_INVALID"):
        reopened.settle_bytes(rid, observed=0, measurement_source="SYNTHETIC_TEST")


def test_non_wal_ledger_is_rejected_before_writing(ledger: S9OperationalLedger) -> None:
    # A live persistent writer connection intentionally prevents journal-mode
    # changes, so close its epoch before simulating an externally changed file.
    ledger.close()
    with sqlite3.connect(ledger.path, isolation_level=None) as db:
        assert db.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
    before = ledger.path.read_bytes()
    with pytest.raises(LedgerError, match="LEDGER_WAL_REQUIRED"):
        S9OperationalLedger(ledger.path)
    assert ledger.path.read_bytes() == before
    with pytest.raises(LedgerError, match="CRITICAL_AUDIT_QUARANTINED"):
        S9OperationalLedger(ledger.path)


def test_terminal_with_pending_reservation_is_detected_as_invalid(ledger: S9OperationalLedger) -> None:
    alias = media(ledger)
    ledger.reserve_bytes(alias, 1)
    with sqlite3.connect(ledger.path) as db:
        db.execute("UPDATE meta SET status='COMPLETED'")
    with pytest.raises(LedgerError, match="TERMINAL_RESERVATION_INVALID"):
        S9OperationalLedger(ledger.path)
    assert ledger.path.with_name(ledger.path.name + ".quarantine").is_file()


@pytest.mark.parametrize("part", ["parent", "main", "wal", "shm", "journal"])
@pytest.mark.parametrize("reparse", [True, False])
def test_reparse_or_symlink_in_path_or_sidecar_blocks_write(
    ledger: S9OperationalLedger, monkeypatch, part: str, reparse: bool,
) -> None:
    target = ledger.path.parent if part == "parent" else ledger.path if part == "main" else Path(str(ledger.path) + "-" + part)
    original = ledger_module.os.lstat

    def fake_lstat(path):
        if Path(path) == target:
            mode = (stat.S_IFDIR if part == "parent" else stat.S_IFREG) if reparse else stat.S_IFLNK
            return SimpleNamespace(st_mode=mode, st_file_attributes=0x400 if reparse else 0)
        return original(path)

    with monkeypatch.context() as patcher:
        patcher.setattr(ledger_module.os, "lstat", fake_lstat)
        with pytest.raises(LedgerError, match="LEDGER_PATH_UNSAFE"):
            ledger.begin_scan(max_messages=1)
    assert ledger.snapshot()["scans"] == []


def test_existing_sidecar_blocks_new_ledger_without_touching_it(tmp_path: Path) -> None:
    target = _private_ledger_path(tmp_path, "new.sqlite")
    sidecar = Path(str(target) + "-wal")
    sidecar.write_bytes(b"preserve")
    with pytest.raises(LedgerError, match="LEDGER_SIDECAR_EXISTS"):
        S9OperationalLedger.create(target)
    assert not target.exists()
    assert sidecar.read_bytes() == b"preserve"


def test_critical_audit_ack_is_durable_idempotent_and_replay_safe(
    ledger: S9OperationalLedger,
) -> None:
    event_id = "e" * 32
    before = ledger.snapshot()["critical_audit"]["event_count"]
    first = ledger.record_critical_event(
        "SECURITY_BLOCK", details={"status": "BLOCKED"}, event_id=event_id,
    )
    second = ledger.record_critical_event(
        "SECURITY_BLOCK", details={"status": "BLOCKED"}, event_id=event_id,
    )
    snapshot = ledger.snapshot()["critical_audit"]
    assert first == second
    assert snapshot["event_count"] == before + 1
    with pytest.raises(LedgerError, match="AUDIT_EVENT_REPLAY_CONFLICT"):
        ledger.record_critical_event(
            "SECURITY_BLOCK", details={"status": "FAILED"}, event_id=event_id,
        )
    with pytest.raises(LedgerError, match="CRITICAL_AUDIT_QUARANTINED"):
        ledger.start_global_deadline()


def test_g8_baseline_pass_status_is_scoped_to_its_event_type(tmp_path: Path) -> None:
    path = _private_ledger_path(tmp_path, "g8-baseline.sqlite")
    ledger = S9OperationalLedger.create(path)
    details = {
        "gate": "G8",
        "stage": "g8-interruption",
        "status": "PASS",
        "evidence_origin": "SYNTHETIC",
        "manifest_sha256": "a" * 64,
        "database_file": "catalog.sqlite3",
        "download_root": "downloads",
        "database_sha256_before": "b" * 64,
        "g6_receipt_sha256": "c" * 64,
        "g7_receipt_sha256": "d" * 64,
        "predecessor_receipts_sha256": "e" * 64,
    }
    ledger.record_critical_event(
        "G8_DATABASE_BASELINE", details=details, event_id="f" * 32,
    )
    ledger.close()

    reopened = S9OperationalLedger(path)
    try:
        audit = reopened.snapshot()["critical_audit"]
        assert any(
            event["event_type"] == "G8_DATABASE_BASELINE"
            and json.loads(event["details_json"]) == details
            for event in audit["events"]
        )
        with pytest.raises(LedgerError, match="AUDIT_EVENT_INVALID"):
            reopened.record_critical_event(
                "SECURITY_BLOCK", details={"status": "PASS"},
                event_id="1" * 32,
            )
    finally:
        reopened.close()


def test_audit_rejects_secret_canary_in_event_fields(ledger: S9OperationalLedger) -> None:
    canary = "synthetic-canary-secret"
    with pytest.raises(LedgerError, match="AUDIT_EVENT_INVALID") as error:
        ledger.record_critical_event(
            "SECURITY_BLOCK", details={"status": canary},
            event_id="f" * 32,
        )
    assert canary not in str(error.value)
    snapshot = ledger.snapshot()
    assert not any(
        canary in event["details_json"]
        for event in snapshot["critical_audit"]["events"]
    )
    assert snapshot["critical_audit"]["quarantined"] is False
    assert snapshot["critical_audit"]["quarantine_durable"] is False


def test_g8_prefix_proof_audit_accepts_only_hashed_identity_alias(
    ledger: S9OperationalLedger,
) -> None:
    details = {
        "gate": "G8",
        "evidence_kind": "S6_V1_PREFIX_PROOF",
        "evidence_origin": "SYNTHETIC",
        "identity_alias": "a" * 64,
        "receipt_sha256": "b" * 64,
    }
    acknowledgement = ledger.record_critical_event(
        "RECEIPT_PREPARED", details=details, event_id="c" * 32,
    )
    assert acknowledgement["event_id"] == "c" * 32
    with pytest.raises(LedgerError, match="INVALID_IDENTITY"):
        ledger.record_critical_event(
            "RECEIPT_PREPARED",
            details=details | {"identity_alias": "raw-telegram-id"},
            event_id="d" * 32,
        )


def test_reservation_state_must_match_audit_history(ledger: S9OperationalLedger) -> None:
    alias = media(ledger)
    reservation_id = ledger.reserve_bytes(alias, 100)
    with sqlite3.connect(ledger.path) as db:
        db.execute(
            "UPDATE reservations SET amount=1 WHERE reservation_id=?",
            (reservation_id,),
        )
    with pytest.raises(LedgerError, match="AUDIT_STATE_MISMATCH"):
        S9OperationalLedger(ledger.path)
    assert ledger.path.with_name(ledger.path.name + ".quarantine").is_file()


def test_full_validation_reuses_reservation_rows_for_history_comparison(
    ledger: S9OperationalLedger,
) -> None:
    alias = media(ledger)
    reservation_id = ledger.reserve_bytes(alias, 100)
    ledger.settle_bytes(
        reservation_id, observed=100, measurement_source="SYNTHETIC_TEST",
    )
    statements: list[str] = []
    with sqlite3.connect(ledger.path) as db:
        db.set_trace_callback(statements.append)
        S9OperationalLedger._validate(db)
    reservation_reads = [
        statement for statement in statements
        if "from reservations" in statement.lower()
    ]
    assert len(reservation_reads) == 1


def test_corrupt_audit_chain_is_quarantined(tmp_path: Path) -> None:
    ledger = S9OperationalLedger.create(
        _private_ledger_path(tmp_path, "corrupt-audit.sqlite")
    )
    with sqlite3.connect(ledger.path) as db:
        db.execute("UPDATE audit_events SET event_hash=? WHERE sequence=1", ("f" * 64,))
    with pytest.raises(LedgerError, match="AUDIT_CHAIN_INVALID"):
        S9OperationalLedger(ledger.path)
    marker = ledger.path.with_name(ledger.path.name + ".quarantine")
    assert marker.read_bytes() == b"S9_LEDGER_QUARANTINED_V1\n"
    with pytest.raises(LedgerError, match="CRITICAL_AUDIT_QUARANTINED"):
        S9OperationalLedger(ledger.path)


def test_noncanonical_audit_json_fails_closed_even_with_valid_rechain(
    tmp_path: Path,
) -> None:
    ledger = S9OperationalLedger.create(
        _private_ledger_path(tmp_path, "noncanonical-audit.sqlite")
    )
    with sqlite3.connect(ledger.path) as db:
        db.execute(
            "UPDATE audit_events SET details_json=? WHERE sequence=1", ("{ }",)
        )
        _rechain_audit(db)
    with pytest.raises(LedgerError, match="AUDIT_CHAIN_INVALID"):
        S9OperationalLedger(ledger.path)
    assert ledger.path.with_name(ledger.path.name + ".quarantine").is_file()


def test_rechained_historical_reservation_mismatch_is_quarantined(
    ledger: S9OperationalLedger,
) -> None:
    alias = media(ledger)
    reservation_id = ledger.reserve_bytes(alias, 100)
    with sqlite3.connect(ledger.path) as db:
        row = db.execute(
            "SELECT sequence,details_json FROM audit_events "
            "WHERE event_type='BYTES_RESERVED'"
        ).fetchone()
        sequence, details_json = row
        details = json.loads(details_json)
        assert details["reservation_id"] == reservation_id
        details["amount_bytes"] = 99
        canonical = json.dumps(
            details, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
        db.execute(
            "UPDATE audit_events SET details_json=? WHERE sequence=?",
            (canonical, sequence),
        )
        _rechain_audit(db)
    with pytest.raises(LedgerError, match="AUDIT_STATE_MISMATCH"):
        S9OperationalLedger(ledger.path)
    assert ledger.path.with_name(ledger.path.name + ".quarantine").is_file()


def test_audit_write_failure_rolls_back_reservation_and_quarantines_run(
    ledger: S9OperationalLedger,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alias = media(ledger)
    preserved_reservation = ledger.reserve_bytes(alias, 20)
    original_append = ledger_module._append_audit_event

    def fail_reservation(db, event_type, details, event_id):
        if event_type == "BYTES_RESERVED":
            raise sqlite3.OperationalError("synthetic-canary-secret")
        return original_append(db, event_type, details, event_id)

    monkeypatch.setattr(ledger_module, "_append_audit_event", fail_reservation)
    with pytest.raises(LedgerError, match="LEDGER_IO_OR_CORRUPTION") as error:
        ledger.reserve_bytes(alias, 100)
    assert "synthetic-canary-secret" not in str(error.value)
    with sqlite3.connect(ledger.path) as db:
        reservations = db.execute(
            "SELECT reservation_id,amount FROM reservations ORDER BY rowid"
        ).fetchall()
        assert reservations == [(preserved_reservation, 20)]
        assert db.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type='BYTES_RESERVED'"
        ).fetchone()[0] == 1
    with pytest.raises(LedgerError, match="CRITICAL_AUDIT_QUARANTINED"):
        S9OperationalLedger(ledger.path)
    assert ledger.path.with_name(ledger.path.name + ".quarantine").read_bytes() == b"S9_LEDGER_QUARANTINED_V1\n"

    repository_root = Path(__file__).resolve().parents[2]
    reopen_script = """
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[2]) / "src"))
from telegram_courses.s9_operational_ledger import LedgerError, S9OperationalLedger
try:
    ledger = S9OperationalLedger(sys.argv[1])
    ledger.start_global_deadline()
except LedgerError as error:
    if error.args == ("CRITICAL_AUDIT_QUARANTINED",):
        print("QUARANTINED")
    else:
        sys.exit(2)
else:
    sys.exit(1)
"""
    process = subprocess.run(
        [sys.executable, "-c", reopen_script, str(ledger.path), str(repository_root)],
        cwd=repository_root, capture_output=True, text=True, timeout=10, check=False,
    )
    assert process.returncode == 0, process.stderr
    assert process.stdout.strip() == "QUARANTINED"


def test_sqlite_sync_failure_rolls_back_deadline_and_quarantines_run(
    planned_ledger: S9OperationalLedger,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_sync(_db: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("synthetic-canary-secret")

    monkeypatch.setattr(ledger_module, "_commit_durable", fail_sync)
    with pytest.raises(LedgerError, match="LEDGER_IO_OR_CORRUPTION") as error:
        planned_ledger.start_global_deadline()
    assert "synthetic-canary-secret" not in str(error.value)
    with sqlite3.connect(planned_ledger.path) as db:
        assert db.execute("SELECT deadline_ns FROM meta").fetchone()[0] is None
        assert db.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type='RUN_DEADLINE_STARTED'"
        ).fetchone()[0] == 0
    with pytest.raises(LedgerError, match="CRITICAL_AUDIT_QUARANTINED"):
        S9OperationalLedger(planned_ledger.path)


def test_observed_bytes_require_an_explicit_offline_measurement_source(
    ledger: S9OperationalLedger,
) -> None:
    alias = media(ledger)
    reservation_id = ledger.reserve_bytes(alias, 100)
    with pytest.raises(LedgerError, match="TRUSTED_BYTE_SOURCE_UNAVAILABLE"):
        ledger.settle_bytes(reservation_id, observed=70)
    ledger.settle_bytes(
        reservation_id, observed=70, measurement_source="SYNTHETIC_TEST",
    )
    entry = ledger.snapshot()["reservations"][0]
    assert entry["state"] == "OBSERVED"
    assert entry["measurement_source"] == "SYNTHETIC_TEST"
