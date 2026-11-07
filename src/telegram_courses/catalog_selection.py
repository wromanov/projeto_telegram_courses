"""Pure course-scoped catalog selection models and command parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from telegram_courses.catalog_repository import (
    InteractiveCatalogMediaView,
    InteractiveCatalogSnapshot,
)

MAX_SELECTION_INPUT_CHARS = 256
MAX_SELECTION_TERMS = 64


@dataclass(frozen=True, order=True)
class MediaIdentity:
    channel_id: int
    telegram_message_id: int
    media_ordinal: int


@dataclass(frozen=True)
class CourseMediaOption:
    identity: MediaIdentity
    course_id: int
    module_id: int | None
    lesson_id: int | None
    module_title: str | None
    lesson_title: str | None
    kind: str
    telegram_media_id: str | None
    original_filename: str | None
    mime_type: str | None
    file_size_bytes: int | None
    selectable: bool
    reason: str | None = None
    ordinal_path: tuple[int, ...] = ()


@dataclass(frozen=True)
class CourseMediaSelection:
    channel_id: int
    course_id: int
    identities: tuple[MediaIdentity, ...]


@dataclass(frozen=True)
class SelectionCommand:
    action: str
    indices: tuple[int, ...] = ()


class SelectionInputError(ValueError):
    """Invalid interactive command; callers must preserve current selection."""


_INDEX_TERM = re.compile(r"([0-9]+)(?:-([0-9]+))?\Z")


def parse_selection_command(text: str, item_count: int) -> SelectionCommand:
    if not isinstance(text, str) or len(text) > MAX_SELECTION_INPUT_CHARS:
        raise SelectionInputError("entrada inválida ou longa demais")
    value = text.strip()
    if not value:
        raise SelectionInputError("informe uma opção")
    command = value.casefold()
    if command == "q":
        return SelectionCommand("back")
    if command in {"v", "revisar"}:
        return SelectionCommand("review")
    if command in {"p", "plano"}:
        return SelectionCommand("prepare")
    if command in {"b", "baixar-todos"}:
        return SelectionCommand("all_course")
    if command in {"a", "anterior"}:
        return SelectionCommand("previous_page")
    if command in {"n", "proxima"}:
        return SelectionCommand("next_page")
    if command == "t":
        return SelectionCommand("all")
    if command == "l":
        return SelectionCommand("clear")
    if command == "r":
        return SelectionCommand("remove_mode")
    terms = value.split(",")
    if len(terms) > MAX_SELECTION_TERMS:
        raise SelectionInputError("selecione menos itens por vez")
    indices: set[int] = set()
    for raw_term in terms:
        term = raw_term.strip()
        match = _INDEX_TERM.fullmatch(term)
        if match is None:
            raise SelectionInputError("use números, listas ou intervalos válidos")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end < start or end > item_count:
            raise SelectionInputError("índice ou intervalo fora da lista")
        indices.update(range(start, end + 1))
    return SelectionCommand("indices", tuple(sorted(indices)))


def _lineage(node_id: int, by_id: dict[int, object]) -> tuple[object, ...] | None:
    reverse: list[object] = []
    seen: set[int] = set()
    current: int | None = node_id
    while current is not None:
        if current in seen or current not in by_id:
            return None
        seen.add(current)
        node = by_id[current]
        reverse.append(node)
        current = node.parent_id
    return tuple(reversed(reverse))


def _valid_kind_path(kinds: tuple[str, ...]) -> bool:
    return (
        kinds in {("course",), ("track", "course")}
        or kinds in {
            ("course", "module"), ("track", "course", "module"),
            ("course", "lesson"), ("track", "course", "lesson"),
            ("course", "module", "lesson"),
            ("track", "course", "module", "lesson"),
        }
    )


def selectable_courses(snapshot: InteractiveCatalogSnapshot) -> tuple[object, ...]:
    by_id = {node.node_id: node for node in snapshot.nodes}
    courses = []
    for node in snapshot.nodes:
        if node.kind != "course" or not node.is_active:
            continue
        lineage = _lineage(node.node_id, by_id)
        if lineage and _valid_kind_path(tuple(item.kind for item in lineage)) and all(
            item.is_active for item in lineage
        ):
            courses.append((tuple(item.ordinal or 0 for item in lineage), node))
    courses.sort(key=lambda pair: (pair[0], pair[1].node_id))
    return tuple(node for _, node in courses)


def course_hierarchy(
    snapshot: InteractiveCatalogSnapshot, course_id: int
) -> tuple[object, ...]:
    by_id = {node.node_id: node for node in snapshot.nodes}
    result = []
    for node in snapshot.nodes:
        if node.kind not in {"module", "lesson"}:
            continue
        lineage = _lineage(node.node_id, by_id)
        if not lineage or not any(item.node_id == course_id for item in lineage):
            continue
        kinds = tuple(item.kind for item in lineage)
        if _valid_kind_path(kinds):
            result.append((tuple(item.ordinal or 0 for item in lineage), node))
    result.sort(key=lambda pair: (pair[0], pair[1].node_id))
    return tuple(node for _, node in result)


def course_media_options(
    snapshot: InteractiveCatalogSnapshot, course_id: int
) -> tuple[CourseMediaOption, ...]:
    by_id = {node.node_id: node for node in snapshot.nodes}
    staged: list[tuple[tuple[int, ...], InteractiveCatalogMediaView, tuple[object, ...], str | None]] = []
    for media in snapshot.media:
        if media.catalog_node_id is None:
            continue
        lineage = _lineage(media.catalog_node_id, by_id)
        if not lineage or not any(node.node_id == course_id for node in lineage):
            continue
        if not any(node.kind == "course" and node.node_id == course_id for node in lineage):
            continue
        kinds = tuple(node.kind for node in lineage)
        structurally_valid = _valid_kind_path(kinds)
        active = all(node.is_active for node in lineage)
        lesson = lineage[-1] if lineage[-1].kind == "lesson" else None
        reason = None
        if not structurally_valid:
            reason = "linhagem inválida"
        elif not active or media.catalog_active is False:
            reason = "associação inativa"
        elif lesson is None:
            reason = "mídia sem associação a aula"
        order = tuple(node.ordinal or 0 for node in lineage)
        staged.append((order, media, lineage, reason))
    staged.sort(key=lambda item: (
        item[0], item[1].telegram_message_id, item[1].media_ordinal,
    ))
    counts: dict[MediaIdentity, int] = {}
    for _, media, _, _ in staged:
        identity = MediaIdentity(
            media.channel_id, media.telegram_message_id, media.media_ordinal
        )
        counts[identity] = counts.get(identity, 0) + 1
    options = []
    for order, media, lineage, reason in staged:
        identity = MediaIdentity(
            media.channel_id, media.telegram_message_id, media.media_ordinal
        )
        if counts[identity] > 1:
            reason = "identidade ambígua"
        module = next((node for node in reversed(lineage) if node.kind == "module"), None)
        lesson = lineage[-1] if lineage[-1].kind == "lesson" else None
        options.append(CourseMediaOption(
            identity=identity,
            course_id=course_id,
            module_id=module.node_id if module else None,
            lesson_id=lesson.node_id if lesson else None,
            module_title=module.title if module else None,
            lesson_title=lesson.title if lesson else None,
            kind=media.kind,
            telegram_media_id=media.telegram_media_id,
            original_filename=media.original_filename,
            mime_type=media.mime_type,
            file_size_bytes=media.file_size_bytes,
            selectable=reason is None,
            reason=reason,
            ordinal_path=order,
        ))
    return tuple(options)


def apply_selection_command(
    options: tuple[CourseMediaOption, ...],
    selected: frozenset[MediaIdentity],
    command: SelectionCommand,
    *,
    removing: bool = False,
) -> frozenset[MediaIdentity]:
    selectable_ids = {item.identity for item in options if item.selectable}
    if command.action == "clear":
        return frozenset()
    if command.action == "all":
        if removing:
            return frozenset()
        return frozenset(selectable_ids)
    if command.action != "indices":
        return selected
    identities = []
    for index in command.indices:
        item = options[index - 1]
        if not item.selectable:
            raise SelectionInputError("esse item não pode ser selecionado neste curso")
        identities.append(item.identity)
    if removing:
        return selected.difference(identities)
    return selected.union(identities)


def make_course_selection(
    options: tuple[CourseMediaOption, ...], selected: frozenset[MediaIdentity],
    *, channel_id: int, course_id: int,
) -> CourseMediaSelection:
    ordered = tuple(item.identity for item in options if item.identity in selected)
    return CourseMediaSelection(channel_id, course_id, ordered)
