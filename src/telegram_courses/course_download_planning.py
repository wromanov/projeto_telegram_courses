"""Application helpers for reviewing a fresh, course-scoped S5 plan."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from telegram_courses.downloads import DownloadError, destination_paths
from telegram_courses.s5_downloads import DownloadPlan, DownloadSelection, PlanItem

DISK_RECONFIRM_DELTA_BYTES = 1024 ** 3


@dataclass(frozen=True)
class DestinationReview:
    identity: tuple[int, int, int]
    final_path: str | None
    partial_path: str | None
    error: str | None = None


@dataclass(frozen=True)
class ObservedExclusion:
    identity: tuple[int, int, int]
    filename: str | None
    size_bytes: int | None
    reason: str


@dataclass(frozen=True)
class CoursePlanReview:
    plan: DownloadPlan
    selection_mode: str
    download_root: str
    integrity_mode: str
    max_media_items: int | None
    max_transfer_bytes: int | None
    disk_probe_path: str | None
    available_disk_bytes: int | None
    destinations: tuple[DestinationReview, ...]
    item_limit_result: str
    byte_limit_result: str
    disk_limit_result: str
    observed_exclusions: tuple[ObservedExclusion, ...] = ()
    catalog_context: tuple[object, ...] = ()

    @property
    def selected_count(self) -> int:
        return len(self.plan.items)

    @property
    def known_size_bytes(self) -> int:
        return sum(
            _observed_size(item) for item in self.plan.items
            if _observed_size(item) is not None
        )

    @property
    def unknown_size_count(self) -> int:
        return (
            sum(_observed_size(item) is None for item in self.plan.items)
            + sum(item.size_bytes is None for item in self.observed_exclusions)
        )

    @property
    def observed_exclusion_known_size_bytes(self) -> int:
        return sum(
            item.size_bytes for item in self.observed_exclusions
            if item.size_bytes is not None
        )

    @property
    def telegram_reservation_floor_bytes(self) -> int:
        """Peak aligned-request reservation for one sequential, retry-free pass.

        Proof and retries may require more. This is advisory and does not grant
        or increase a transfer budget.
        """
        received = 0
        peak = 0
        for item in self.plan.pending:
            if item.candidate is None:
                continue
            size = (
                item.estimated_payload_bytes
                if item.estimated_payload_bytes is not None
                else item.candidate.expected_bytes
            )
            if size > 0:
                aligned = ((size + 1023) // 1024) * 1024
                peak = max(peak, received + aligned)
                received += size
        return peak

    @property
    def limit_result(self) -> str:
        results = (self.item_limit_result, self.byte_limit_result)
        if "FAIL" in results:
            return "FAIL"
        if all(result == "NOT_CONFIGURED" for result in results):
            return "NOT_CONFIGURED"
        return "PASS"

    @property
    def destination_errors(self) -> tuple[DestinationReview, ...]:
        return tuple(item for item in self.destinations if item.error is not None)

    @property
    def block_reasons(self) -> tuple[str, ...]:
        reasons = [item.reason for item in self.plan.blocked if item.reason]
        for item in self.plan.completed_v2:
            if not (
                self.integrity_mode == "OPERATIONAL_ONLY"
                and item.reason == "OPERATIONAL_ONLY"
            ):
                reasons.append("V2_COMPLETION_MODE_MISMATCH")
        reasons.extend(item.error for item in self.destination_errors if item.error)
        if self.limit_result == "FAIL":
            if self.item_limit_result == "FAIL":
                reasons.append("MEDIA_LIMIT_EXCEEDED")
            if self.byte_limit_result == "FAIL":
                reasons.append("TRANSFER_BUDGET_EXCEEDED_OR_UNKNOWN_SIZE")
        if self.disk_limit_result == "FAIL":
            reasons.append("INSUFFICIENT_DISK_SPACE")
        elif self.disk_limit_result == "UNVERIFIED":
            reasons.append("DISK_SPACE_UNVERIFIED")
        return tuple(dict.fromkeys(reasons))

    @property
    def result_status(self) -> str:
        if self.block_reasons:
            return "BLOQUEADO"
        if not self.plan.items or not self.plan.eligible:
            return "SEM_ELEGIVEIS"
        if (
            not self.plan.pending
            and len(self.plan.already_valid) == len(self.plan.items)
        ):
            return "TODOS_JA_VALIDOS"
        if self.plan.excluded or self.observed_exclusions:
            return "PARCIAL_COM_EXCLUSOES"
        return "PLANO_REVISAVEL"

    @property
    def can_confirm(self) -> bool:
        return self.result_status in {
            "TODOS_JA_VALIDOS", "PARCIAL_COM_EXCLUSOES", "PLANO_REVISAVEL",
        }

    def fingerprint(self) -> tuple[object, ...]:
        """Compare all confirmation-relevant facts, not only ``plan_id``."""
        selection = self.plan.selection
        items = tuple(_item_fingerprint(item) for item in self.plan.items)
        destinations = tuple(
            (item.identity, item.final_path, item.partial_path, item.error)
            for item in self.destinations
        )
        observed_exclusions = tuple(
            (item.identity, item.filename, item.size_bytes, item.reason)
            for item in self.observed_exclusions
        )
        return (
            selection.channel_id,
            selection.scope,
            selection.node_id,
            selection.media_identities,
            self.selection_mode,
            self.plan.plan_id,
            self.plan.scope_title,
            self.plan.catalog_complete,
            self.plan.lesson_count,
            items,
            self.download_root,
            destinations,
            observed_exclusions,
            self.catalog_context,
            self.integrity_mode,
            self.max_media_items,
            self.max_transfer_bytes,
            self.item_limit_result,
            self.byte_limit_result,
            self.disk_probe_path,
            self.disk_limit_result,
            self.plan.pending_bytes,
            self.plan.additional_disk_bytes,
            self.plan.safety_margin,
        )

    def matches_after_confirmation(self, fresh: CoursePlanReview) -> bool:
        """Compare a fresh plan with the reviewed plan and its disk capacity."""
        if not self.can_confirm or not fresh.can_confirm:
            return False
        if self.fingerprint() != fresh.fingerprint():
            return False
        before = self.available_disk_bytes
        after = fresh.available_disk_bytes
        if before is None or after is None:
            return before is after
        return abs(before - after) < DISK_RECONFIRM_DELTA_BYTES


def _observed_size(item: PlanItem) -> int | None:
    if item.candidate is not None:
        return item.candidate.expected_bytes
    return item.observed_size_bytes


def _candidate_fingerprint(item: PlanItem) -> tuple[object, ...] | None:
    candidate = item.candidate
    if candidate is None:
        return None
    return (
        candidate.media_item_id,
        candidate.channel_id,
        candidate.telegram_message_id,
        candidate.media_ordinal,
        candidate.telegram_media_id,
        candidate.expected_bytes,
        candidate.original_filename,
        candidate.lineage,
    )


def _item_fingerprint(item: PlanItem) -> tuple[object, ...]:
    return (
        item.identity,
        _candidate_fingerprint(item),
        item.status,
        item.reason,
        item.part_bytes,
        item.wire_offset,
        item.overlap_bytes,
        item.estimated_payload_bytes,
        item.estimated_additional_disk_bytes,
        item.observed_size_bytes,
    )


def _existing_directory(path: Path) -> Path | None:
    probe = path.expanduser().absolute()
    try:
        while not probe.exists():
            parent = probe.parent
            if parent == probe:
                return None
            probe = parent
        if probe.is_file():
            probe = probe.parent
        return probe
    except OSError:
        return None


def create_course_plan_review(
    plan: DownloadPlan,
    *,
    selection_mode: str,
    download_root: str | Path,
    integrity_mode: str = "REMOTE_HASH_REQUIRED",
    max_media_items: int | None = None,
    max_transfer_bytes: int | None = None,
    observed_exclusions: tuple[ObservedExclusion, ...] = (),
    catalog_context: tuple[object, ...] = (),
    disk_usage: Callable[[str | Path], object] = shutil.disk_usage,
) -> CoursePlanReview:
    root = Path(download_root).expanduser().absolute()
    destinations: list[DestinationReview] = []
    for item in plan.items:
        if item.candidate is None:
            continue
        try:
            final_path, partial_path = destination_paths(root, item.candidate)
        except DownloadError as error:
            destinations.append(DestinationReview(
                item.identity, None, None, error.category,
            ))
        else:
            destinations.append(DestinationReview(
                item.identity, str(final_path), str(partial_path),
            ))

    probe = _existing_directory(root)
    available: int | None = None
    if probe is not None:
        try:
            disk = disk_usage(probe)
            value = getattr(disk, "free", None)
            if type(value) is int and value >= 0:
                available = value
        except (OSError, PermissionError, TypeError, ValueError):
            available = None

    item_result = (
        "NOT_CONFIGURED" if max_media_items is None
        else "PASS" if len(plan.items) <= max_media_items
        else "FAIL"
    )
    unknown_size = any(item.reason == "UNKNOWN_SIZE" for item in plan.excluded)
    byte_result = (
        "NOT_CONFIGURED" if max_transfer_bytes is None
        else "PASS" if plan.pending_bytes <= max_transfer_bytes and not unknown_size
        else "FAIL"
    )
    if not plan.pending:
        disk_result = "NOT_REQUIRED"
    elif available is None:
        disk_result = "UNVERIFIED"
    elif available >= plan.additional_disk_bytes + plan.safety_margin:
        disk_result = "PASS"
    else:
        disk_result = "FAIL"

    return CoursePlanReview(
        plan=plan,
        selection_mode=selection_mode,
        download_root=str(root),
        integrity_mode=integrity_mode,
        max_media_items=max_media_items,
        max_transfer_bytes=max_transfer_bytes,
        disk_probe_path=str(probe) if probe is not None else None,
        available_disk_bytes=available,
        destinations=tuple(destinations),
        item_limit_result=item_result,
        byte_limit_result=byte_result,
        disk_limit_result=disk_result,
        observed_exclusions=observed_exclusions,
        catalog_context=catalog_context,
    )


def course_download_selection(
    channel_id: int,
    course_id: int,
    *,
    media_identities: tuple[tuple[int, int, int], ...] | None,
) -> DownloadSelection:
    """Create the course scope consumed by the existing S5 planner."""
    return DownloadSelection(
        channel_id=channel_id,
        scope="course",
        node_id=course_id,
        media_identities=media_identities,
    )
