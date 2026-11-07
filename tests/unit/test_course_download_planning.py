from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from telegram_courses.course_download_planning import create_course_plan_review
from telegram_courses.download_repository import DownloadCandidate
from telegram_courses.s5_downloads import DownloadPlan, DownloadSelection, PlanItem


def _plan(*, expected_bytes: int = 4, status: str = "PENDING") -> DownloadPlan:
    candidate = DownloadCandidate(
        media_item_id=1,
        channel_id=-1001,
        telegram_message_id=10,
        media_ordinal=0,
        telegram_media_id="synthetic-media",
        expected_bytes=expected_bytes,
        original_filename="lesson.bin",
        lineage=(("lesson", "Lesson 1"),),
    )
    item = PlanItem(
        (-1001, 10, 0), candidate, status,
        estimated_payload_bytes=expected_bytes,
        estimated_additional_disk_bytes=expected_bytes,
        observed_size_bytes=expected_bytes,
    )
    return DownloadPlan(
        "stable-plan-id", DownloadSelection(-1001, "course", 5),
        "Course A", False, 1, (item,),
    )


def _review(plan: DownloadPlan, root: Path, **changes):
    return create_course_plan_review(
        plan,
        selection_mode="SELECTED",
        download_root=root,
        disk_usage=changes.pop("disk_usage", lambda _path: SimpleNamespace(free=10**12)),
        **changes,
    )


def test_review_fingerprint_covers_status_destination_integrity_caps_and_disk(tmp_path) -> None:
    plan = _plan()
    root = tmp_path / "downloads"
    baseline = _review(plan, root)

    blocked_item = replace(plan.items[0], status="BLOCKED", reason="MEDIA_NOT_OBSERVED")
    blocked_plan = replace(plan, items=(blocked_item,))
    changed_size = _plan(expected_bytes=5)
    changed_root = _review(plan, tmp_path / "other")
    changed_integrity = _review(plan, root, integrity_mode="OPERATIONAL_ONLY")
    changed_limits = _review(plan, root, max_media_items=1, max_transfer_bytes=4)
    changed_disk = _review(
        plan, root, disk_usage=lambda _path: SimpleNamespace(free=1),
    )

    assert baseline.plan.plan_id == blocked_plan.plan_id
    assert baseline.fingerprint() != _review(blocked_plan, root).fingerprint()
    assert baseline.fingerprint() != _review(changed_size, root).fingerprint()
    assert baseline.fingerprint() != changed_root.fingerprint()
    assert baseline.fingerprint() != changed_integrity.fingerprint()
    assert baseline.fingerprint() != changed_limits.fingerprint()
    assert baseline.fingerprint() != changed_disk.fingerprint()


def test_unknown_size_is_visible_and_fails_only_a_configured_byte_cap(tmp_path) -> None:
    unknown = PlanItem(
        (-1001, 11, 0), None, "EXCLUDED", "UNKNOWN_SIZE",
        observed_size_bytes=None,
    )
    plan = DownloadPlan(
        "unknown-plan", DownloadSelection(-1001, "course", 5),
        "Course A", False, 1, (unknown,),
    )
    no_cap = _review(plan, tmp_path / "downloads")
    capped = _review(plan, tmp_path / "downloads", max_transfer_bytes=100)

    assert no_cap.selected_count == 1
    assert no_cap.unknown_size_count == 1
    assert no_cap.known_size_bytes == 0
    assert no_cap.byte_limit_result == "NOT_CONFIGURED"
    assert no_cap.result_status == "SEM_ELEGIVEIS"
    assert capped.byte_limit_result == "FAIL"
    assert capped.result_status == "BLOQUEADO"


def test_review_distinguishes_all_already_valid_from_a_new_completion(tmp_path) -> None:
    review = _review(_plan(status="ALREADY_VALID"), tmp_path / "downloads")

    assert review.result_status == "TODOS_JA_VALIDOS"
    assert len(review.plan.already_valid) == 1
    assert review.can_confirm
    assert not review.plan.pending


def test_destination_and_disk_failures_block_confirmation_without_writes(tmp_path) -> None:
    too_long_root = tmp_path / ("x" * 230)
    review = _review(
        _plan(), too_long_root,
        disk_usage=lambda _path: SimpleNamespace(free=0),
    )

    assert review.destination_errors[0].error == "PATH_TOO_LONG"
    assert review.disk_limit_result == "FAIL"
    assert review.result_status == "BLOQUEADO"
    assert not review.can_confirm
    assert not too_long_root.exists()


def test_free_space_comparison_uses_exact_gib_boundary(tmp_path) -> None:
    plan = _plan()
    first = _review(plan, tmp_path, disk_usage=lambda _: SimpleNamespace(free=10**12))
    for delta in (0, 1, 1024**3 - 1, 1024**3, 1024**3 + 1):
        for direction in (-1, 1):
            free = 10**12 + direction * delta
            second = _review(plan, tmp_path, disk_usage=lambda _, value=free: SimpleNamespace(free=value))
            assert first.disk_limit_result == second.disk_limit_result == "PASS"
            assert first.matches_after_confirmation(second) is (delta < 1024**3)


def test_small_change_still_rejects_insufficient_capacity(tmp_path) -> None:
    plan = _plan()
    threshold = plan.additional_disk_bytes + plan.safety_margin
    first = _review(plan, tmp_path, disk_usage=lambda _: SimpleNamespace(free=threshold))
    second = _review(plan, tmp_path, disk_usage=lambda _: SimpleNamespace(free=threshold - 1))
    assert first.can_confirm
    assert not second.can_confirm
    assert not first.matches_after_confirmation(second)


def test_unverified_disk_blocks_pending_but_not_already_valid(tmp_path) -> None:
    def unavailable(_path):
        raise OSError("synthetic disk probe failure")

    pending = _review(_plan(), tmp_path, disk_usage=unavailable)
    assert pending.disk_limit_result == "UNVERIFIED"
    assert "DISK_SPACE_UNVERIFIED" in pending.block_reasons
    assert not pending.can_confirm

    valid = _review(_plan(status="ALREADY_VALID"), tmp_path, disk_usage=unavailable)
    assert valid.disk_limit_result == "NOT_REQUIRED"
    assert valid.can_confirm
