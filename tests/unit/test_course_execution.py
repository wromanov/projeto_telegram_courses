from __future__ import annotations

from dataclasses import replace
from threading import Event, Thread
from time import monotonic

import pytest
from tests.unit.test_course_download_planning import _plan

from telegram_courses.course_execution import (
    CourseProgressTracker,
    ProgressDispatcher,
    summarize_execution,
)
from telegram_courses.s5_downloads import QueueResult


@pytest.mark.parametrize(
    ("original", "reported", "cancelled", "global_block", "expected"),
    [
        ("PENDING", "COMPLETED", False, None, "CONCLUIDO"),
        ("ALREADY_VALID", "ALREADY_VALID", False, None, "TODOS_JA_VALIDOS"),
        ("PENDING", "FAILED", False, None, "FALHA"),
        ("PENDING", "BLOCKED", False, None, "BLOQUEADO"),
        ("PENDING", "CANCELLED", True, None, "CANCELADO"),
        ("PENDING", "SKIPPED", False, None, "BLOQUEADO"),
        ("PENDING", None, False, "DISK", "BLOQUEADO"),
    ],
)
def test_summary_uses_authoritative_per_item_outcomes(
    original, reported, cancelled, global_block, expected,
) -> None:
    plan = _plan(status=original)
    identity = plan.items[0].identity
    result = QueueResult(((identity, reported, None),), 4, 1, cancelled) if reported else None
    summary = summarize_execution(plan, result, cancelled=cancelled, global_block=global_block)
    assert summary.status == expected
    assert summary.outcomes[0][0] == identity


def test_summary_distinguishes_empty_ineligible_and_partial() -> None:
    base = _plan()
    assert summarize_execution(replace(base, items=())).status == "SEM_SELECAO"
    excluded = replace(base.items[0], candidate=None, status="EXCLUDED", reason="UNKNOWN_SIZE")
    assert summarize_execution(replace(base, items=(excluded,))).status == "SEM_ELEGIVEIS"
    excluded = replace(excluded, identity=(-1001, 11, 0))
    partial = replace(base, items=(base.items[0], excluded))
    result = QueueResult(((base.items[0].identity, "COMPLETED", None),), 4, 1)
    summary = summarize_execution(partial, result)
    assert summary.status == "PARCIAL"
    assert (summary.completed, summary.excluded) == (1, 1)


def test_summary_rejects_duplicate_and_foreign_queue_identities() -> None:
    plan = _plan()
    identity = plan.items[0].identity
    for outcomes in (
        ((identity, "COMPLETED", None), (identity, "COMPLETED", None)),
        (((-1001, 99, 0), "COMPLETED", None),),
    ):
        with pytest.raises(ValueError, match="invalid queue outcomes"):
            summarize_execution(plan, QueueResult(outcomes, 0, 1))


@pytest.mark.parametrize(
    ("states", "cancelled", "expected"),
    [
        (("COMPLETED", "FAILED"), True, "CANCELADO"),
        (("FAILED", "BLOCKED"), False, "FALHA"),
        (("COMPLETED", "BLOCKED"), False, "BLOQUEADO"),
        (("ALREADY_VALID", "EXCLUDED"), False, "PARCIAL"),
    ],
)
def test_summary_precedence_preserves_secondary_counts(states, cancelled, expected) -> None:
    base = _plan()
    first = base.items[0]
    second = replace(first, identity=(-1001, 11, 0))
    if states[1] == "EXCLUDED":
        second = replace(second, candidate=None, status="EXCLUDED", reason="UNKNOWN_SIZE")
    plan = replace(base, items=(first, second))
    outcomes = tuple((item.identity, status, None) for item, status in zip(plan.items, states))
    summary = summarize_execution(plan, QueueResult(outcomes, 0, 1, cancelled))
    assert summary.status == expected
    assert len(summary.outcomes) == 2


def test_progress_uses_received_bytes_and_resets_rate_on_retry() -> None:
    now = [0.0]
    plan = _plan(expected_bytes=10_000_000)
    progress = CourseProgressTracker(plan, lambda: now[0])
    progress.start_attempt(plan.items[0].identity)
    progress.observe_file(2_000_000, 10_000_000)
    progress.observe_queue({"bytes_transferred": 2_000_000})
    assert progress.snapshot().speed_mb_s is None
    now[0] = 2.0
    progress.observe_file(4_000_000, 10_000_000)
    progress.observe_queue({"bytes_transferred": 4_000_000})
    snapshot = progress.snapshot()
    assert snapshot.speed_mb_s == 2.0
    assert snapshot.eta_seconds == 6.0
    progress.start_attempt(plan.items[0].identity)
    assert progress.snapshot().speed_mb_s is None
    assert progress.snapshot().eta_seconds is None
    now[0] = 4.0
    progress.observe_queue({"bytes_transferred": 5_000_000})
    assert progress.snapshot().speed_mb_s == 0.5


def test_traffic_observer_separates_proof_overlap_and_queue_budget() -> None:
    progress = CourseProgressTracker(_plan(), lambda: 2.0)
    progress.observe_traffic("proof", 120)
    progress.observe_traffic("overlap", 60)
    progress.observe_queue({
        "bytes_transferred": 320,
        "budget_consumed_bytes": 336,
        "budget_uncertain_bytes": 16,
        "completed": 1,
        "already_valid": 0,
    })
    snapshot = progress.snapshot()
    assert snapshot.proof_received_bytes == 120
    assert snapshot.overlap_received_bytes == 60
    assert snapshot.received_bytes == 320
    assert snapshot.budget_charged_bytes == 336
    assert snapshot.budget_uncertain_bytes == 16
    assert snapshot.completed_files == 1


def test_full_file_bar_is_validating_until_queue_reports_completion() -> None:
    plan = _plan()
    tracker = CourseProgressTracker(plan, lambda: 0.0)
    tracker.start_attempt(plan.items[0].identity)
    tracker.observe_file(4, 4)
    assert tracker.snapshot().file_status == "VALIDANDO"
    tracker.observe_queue({"running": 0, "completed": 1})
    assert tracker.snapshot().file_status == "CONCLUÍDO"


def test_batch_progress_counts_only_validated_file_bytes() -> None:
    base = _plan()
    first = base.items[0]
    second_candidate = replace(first.candidate, media_item_id=2, telegram_message_id=11, expected_bytes=6)
    second = replace(first, identity=(-1001, 11, 0), candidate=second_candidate)
    plan = replace(base, items=(first, second))
    tracker = CourseProgressTracker(plan, lambda: 0.0)
    tracker.start_attempt(first.identity)
    tracker.observe_file(4, 4)
    assert (tracker.snapshot().batch_validated_bytes, tracker.snapshot().batch_total_bytes) == (0, 10)
    tracker.observe_queue({"running": 0, "completed": 1})
    assert (tracker.snapshot().batch_validated_bytes, tracker.snapshot().batch_total_bytes) == (4, 10)
    tracker.start_attempt(second.identity)
    tracker.observe_file(6, 6)
    assert tracker.snapshot().batch_validated_bytes == 4
    tracker.observe_queue({"running": 0, "completed": 2})
    assert tracker.snapshot().batch_validated_bytes == 10


def test_slow_observer_does_not_block_queue_callback_and_measures_cost() -> None:
    started, release, published = Event(), Event(), Event()
    now = [0.0]
    tracker = CourseProgressTracker(_plan(), lambda: now[0])

    def slow(_snapshot):
        started.set()
        release.wait(2)

    dispatcher = ProgressDispatcher(slow, clock=lambda: now[0])
    dispatcher.publish(tracker.snapshot())
    assert started.wait(2)

    def publish_again():
        now[0] = 1.0
        dispatcher.publish(tracker.snapshot())
        published.set()

    before = monotonic()
    worker = Thread(target=publish_again)
    worker.start()
    assert published.wait(0.5)
    elapsed = monotonic() - before
    assert elapsed < 0.5
    dispatcher.close(timeout=0.01)
    assert dispatcher.incomplete
    release.set()
    worker.join(1)
    dispatcher._thread.join(2)


def test_failing_observer_is_caught_and_throttling_is_monotonic() -> None:
    called = Event()
    now = [0.0]
    tracker = CourseProgressTracker(_plan(), lambda: now[0])

    def failing(_snapshot):
        called.set()
        raise RuntimeError("synthetic rendering failure")

    dispatcher = ProgressDispatcher(failing, clock=lambda: now[0], min_interval=0.25)
    dispatcher.publish(tracker.snapshot())
    assert called.wait(2)
    now[0] = 0.1
    dispatcher.publish(tracker.snapshot())
    assert dispatcher.last_published == 0.0
    now[0] = 0.25
    dispatcher.publish(tracker.snapshot())
    assert dispatcher.last_published == 0.25
    dispatcher.close(timeout=1)
    assert dispatcher.failed
