"""Read-only course context for planning and pre-execution revalidation."""

from __future__ import annotations

from telegram_courses.catalog_repository import (
    InteractiveCatalogSnapshot,
    SQLiteCatalogRepository,
)
from telegram_courses.catalog_selection import (
    CourseMediaOption,
    course_hierarchy,
    course_media_options,
    selectable_courses,
)
from telegram_courses.course_download_planning import (
    ObservedExclusion,
    course_download_selection,
)
from telegram_courses.downloads import DownloadError
from telegram_courses.s5_downloads import DownloadPlanner, DownloadSelection


def order_is_ambiguous(
    nodes: tuple[object, ...], course_id: int, snapshot: InteractiveCatalogSnapshot
) -> bool:
    by_id = {node.node_id: node for node in snapshot.nodes}
    relevant = [node for node in nodes if node.kind in {"module", "lesson"}]
    if any(node.ordinal is None for node in relevant):
        return True
    siblings: dict[int | None, set[int]] = {}
    for node in relevant:
        values = siblings.setdefault(node.parent_id, set())
        if node.ordinal in values:
            return True
        values.add(node.ordinal)
    course = by_id.get(course_id)
    return course is None or course.ordinal is None



async def load_course_review_context(
    planner: DownloadPlanner,
    *,
    channel_id: int,
    course_id: int,
    selection_mode: str,
    exact_selection: DownloadSelection | None,
) -> tuple[
    InteractiveCatalogSnapshot,
    object,
    tuple[CourseMediaOption, ...],
    bool,
    DownloadSelection | None,
    tuple[ObservedExclusion, ...],
    tuple[object, ...],
]:
    snapshot = await SQLiteCatalogRepository(planner.database).load_interactive_snapshot(channel_id)
    course = next(
        (item for item in selectable_courses(snapshot) if item.node_id == course_id),
        None,
    )
    if course is None:
        raise DownloadError("INVALID_SELECTION")
    options = course_media_options(snapshot, course_id)
    ambiguous = order_is_ambiguous(
        course_hierarchy(snapshot, course_id), course_id, snapshot,
    )
    observed_exclusions = tuple(
        ObservedExclusion(
            (
                item.identity.channel_id,
                item.identity.telegram_message_id,
                item.identity.media_ordinal,
            ),
            item.original_filename,
            item.file_size_bytes,
            item.reason or "ASSOCIATION_NOT_SELECTABLE",
        )
        for item in options if not item.selectable
    ) if selection_mode == "ALL_CATALOGED" else ()

    if selection_mode == "ALL_CATALOGED":
        selectable_options = tuple(item for item in options if item.selectable)
        selection = (
            course_download_selection(
                channel_id,
                course_id,
                media_identities=tuple(
                    (
                        item.identity.channel_id,
                        item.identity.telegram_message_id,
                        item.identity.media_ordinal,
                    )
                    for item in selectable_options
                ),
            )
            if selectable_options else None
        )
        context_options = options
    else:
        if exact_selection is None:
            raise DownloadError("INVALID_SELECTION")
        selection = exact_selection
        selected_ids = set(exact_selection.media_identities or ())
        context_options = tuple(
            item for item in options
            if (
                item.identity.channel_id,
                item.identity.telegram_message_id,
                item.identity.media_ordinal,
            ) in selected_ids
        )

    catalog_context: tuple[object, ...] = (
        snapshot.channel.channel_id,
        snapshot.channel.title,
        snapshot.scan_status,
        snapshot.scan_stop_reason,
        snapshot.scan_finished_at,
        snapshot.catalog_finished_at,
        snapshot.catalog_complete,
        course.node_id,
        course.title,
        course.ordinal,
        tuple(
            (
                item.identity.channel_id,
                item.identity.telegram_message_id,
                item.identity.media_ordinal,
                item.course_id,
                item.module_id,
                item.lesson_id,
                item.module_title,
                item.lesson_title,
                item.kind,
                item.telegram_media_id,
                item.original_filename,
                item.mime_type,
                item.file_size_bytes,
                item.selectable,
                item.reason,
                item.ordinal_path,
            )
            for item in context_options
        ),
    )
    return (
        snapshot, course, options, ambiguous, selection,
        observed_exclusions, catalog_context,
    )
