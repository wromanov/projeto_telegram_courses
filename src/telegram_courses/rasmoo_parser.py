"""Pure parser for the explicitly confirmed RASMOO catalog formats."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Sequence

from telegram_courses.catalog import (
    CatalogError,
    MediaLink,
    ParsedNode,
    ParserContext,
    ParseResult,
    SourceMessage,
    UnclassifiedSource,
)

_INDEX_REFERENCE = re.compile(r"#F\d+\b")
_DOCUMENT_REFERENCE = re.compile(r"#Doc\d+\b")
_VIDEO_HEADER = re.compile(r"^(#F\d+)\s+(\d+)\s+(.+?)\s*$")
_NUMBERED_TITLE = re.compile(r"^(\d+)\s+(.+?)\s*$")
_INDEX_HEADER = re.compile(r"^(={1,3})\s*(\d+)\s+(.+?)\s*$")


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _node_key(kind: str, path: tuple[tuple[str, str], ...]) -> str:
    return kind + ":" + "/".join(
        f"{code}:{_normalized(title)}" for code, title in path
    )


class RasmooParser:
    """Interpret confirmed index, media-post, and general document syntax only."""

    key = "rasmoo"
    grammar_version = "rasmoo-sp02-v1"

    def parse(
        self, context: ParserContext, messages: Sequence[SourceMessage]
    ) -> ParseResult:
        if context.parser_key != self.key or context.grammar_version != self.grammar_version:
            raise CatalogError("INVALID_SOURCE")

        ordered = tuple(sorted(messages, key=lambda item: item.telegram_message_id))
        nodes: dict[str, ParsedNode] = {}
        index_contexts: dict[str, set[tuple[tuple[str, str], ...]]] = defaultdict(set)
        ref_messages: dict[str, set[int]] = defaultdict(set)
        index_lesson_occurrences: dict[
            str, list[tuple[tuple[tuple[str, str], ...], int, int]]
        ] = defaultdict(list)
        index_ordinals: dict[str, int] = defaultdict(int)
        media_refs: dict[
            str, list[tuple[int, tuple[tuple[str, str], ...], str, int]]
        ] = defaultdict(list)
        unresolved: dict[int, set[str]] = defaultdict(set)
        document_origins: dict[str, set[int]] = defaultdict(set)
        document_media: set[int] = set()
        next_ordinal = 0

        def mark(message_id: int, reason: str) -> None:
            unresolved[message_id].add(reason)

        def ensure_node(
            kind: str,
            path: tuple[tuple[str, str], ...],
            title: str,
            code: str | None,
            source_id: int | None,
            parent: str | None,
        ) -> str:
            nonlocal next_ordinal
            key = _node_key(kind, path)
            existing = nodes.get(key)
            if existing is None:
                next_ordinal += 1
                nodes[key] = ParsedNode(
                    key, kind, parent, title, code, next_ordinal, source_id
                )
            elif source_id is not None and existing.source_message_id is None:
                nodes[key] = ParsedNode(
                    existing.node_key,
                    existing.kind,
                    existing.parent_key,
                    existing.title,
                    existing.code,
                    existing.ordinal,
                    source_id,
                )
            return key

        def ensure_structure(
            track: tuple[str, str] | None,
            course: tuple[str, str] | None,
            module: tuple[str, str] | None,
            source_id: int,
        ) -> tuple[str | None, str | None, str | None, tuple[tuple[str, str], ...]]:
            path: tuple[tuple[str, str], ...] = ()
            track_key = course_key = module_key = None
            if track is not None:
                path = (track,)
                track_key = ensure_node("track", path, track[1], track[0], source_id, None)
            if course is not None:
                if track is None:
                    return track_key, course_key, module_key, ()
                path += (course,)
                course_key = ensure_node("course", path, course[1], course[0], source_id, track_key)
            if module is not None:
                if course is None or course_key is None:
                    return track_key, course_key, module_key, path
                path += (module,)
                module_key = ensure_node("module", path, module[1], module[0], source_id, course_key)
            return track_key, course_key, module_key, path

        for message in ordered:
            if message.channel_id != context.channel_id or message.telegram_message_id <= 0:
                raise CatalogError("INVALID_SOURCE")
            lines = (message.text or "").splitlines()
            nonempty = [(index, line.strip()) for index, line in enumerate(lines) if line.strip()]
            if not nonempty:
                if message.media:
                    mark(message.telegram_message_id, "media_without_confirmed_reference")
                continue

            first_index, first = nonempty[0]
            video_header = _VIDEO_HEADER.fullmatch(first)
            document_header = _DOCUMENT_REFERENCE.search(first)

            if video_header is not None:
                reference, lesson_ordinal, lesson_title = video_header.groups()
                track = course = module = None
                local_path: tuple[tuple[str, str], ...] = ()
                mode = "track"
                # The media-post path has exactly the observed unmarked / = / == forms.
                for _, line in nonempty[1:]:
                    if line.startswith("#"):
                        mark(message.telegram_message_id, "unexpected_reference_in_media_post")
                        continue
                    if line.startswith("="):
                        match = re.fullmatch(r"(=+)\s*(\d+)\s+(.+?)\s*", line)
                        if match is None or match.group(1) not in {"=", "=="}:
                            mark(message.telegram_message_id, "unsupported_media_post_marker")
                            mode = "invalid"
                            continue
                        marker, code, title = match.groups()
                        item = (code, title)
                        if marker == "=":
                            course = item
                            module = None
                            mode = "module"
                        else:
                            if course is None:
                                mark(message.telegram_message_id, "module_without_course")
                                mode = "invalid"
                            else:
                                module = item
                                mode = "done"
                        continue
                    match = _NUMBERED_TITLE.fullmatch(line)
                    if match is None or track is not None or mode != "track":
                        mark(message.telegram_message_id, "unsupported_media_post_line")
                        mode = "invalid"
                        continue
                    track = (match.group(1), match.group(2))
                    mode = "course"

                _, _, _, local_path = ensure_structure(track, course, module, message.telegram_message_id)
                if not local_path or track is None or course is None or module is None:
                    mark(message.telegram_message_id, "incomplete_media_post_context")
                else:
                    ref_messages[reference].add(message.telegram_message_id)
                    media_refs[reference].append(
                        (
                            message.telegram_message_id,
                            local_path,
                            lesson_title,
                            int(lesson_ordinal),
                        )
                    )
                continue

            if document_header is not None:
                reference = document_header.group(0)
                document_origins[reference].add(message.telegram_message_id)
                if message.media:
                    document_media.add(message.telegram_message_id)
                continue

            track = course = module = None
            local_path: tuple[tuple[str, str], ...] = ()
            recognized = False
            for _, line in nonempty:
                if line.startswith("#Doc"):
                    refs = _DOCUMENT_REFERENCE.findall(line)
                    if refs:
                        recognized = True
                        for reference in refs:
                            document_origins[reference].add(message.telegram_message_id)
                        continue
                    mark(message.telegram_message_id, "unsupported_document_reference")
                    continue
                if line.startswith("#F"):
                    refs = _INDEX_REFERENCE.findall(line)
                    residue = _INDEX_REFERENCE.sub("", line).strip()
                    if not refs or residue:
                        mark(message.telegram_message_id, "unsupported_content_reference")
                        continue
                    if module is None or course is None or track is None:
                        mark(message.telegram_message_id, "content_reference_without_module_context")
                        continue
                    recognized = True
                    for reference in refs:
                        index_contexts[reference].add(local_path)
                        ref_messages[reference].add(message.telegram_message_id)
                        module_key = _node_key("module", local_path)
                        index_ordinals[module_key] += 1
                        index_lesson_occurrences[reference].append(
                            (local_path, message.telegram_message_id, index_ordinals[module_key])
                        )
                    continue
                match = _INDEX_HEADER.fullmatch(line)
                if match is None:
                    mark(message.telegram_message_id, "unrecognized_index_line")
                    continue
                recognized = True
                marker, code, title = match.groups()
                item = (code, title)
                if marker == "=":
                    track, course, module = item, None, None
                    _, _, _, local_path = ensure_structure(track, None, None, message.telegram_message_id)
                elif marker == "==":
                    course, module = item, None
                    if track is None:
                        mark(message.telegram_message_id, "course_without_track_context")
                        local_path = ()
                    else:
                        _, _, _, local_path = ensure_structure(track, course, None, message.telegram_message_id)
                else:
                    module = item
                    if track is None or course is None:
                        mark(message.telegram_message_id, "module_without_course_context")
                        local_path = ()
                    else:
                        _, _, _, local_path = ensure_structure(track, course, module, message.telegram_message_id)
            if not recognized and not message.media:
                mark(message.telegram_message_id, "unrecognized_message")
            elif message.media:
                mark(message.telegram_message_id, "media_without_content_reference")

        media_links: list[MediaLink] = []
        for reference, index_paths in index_contexts.items():
            if len(index_paths) != 1:
                for message_id in ref_messages[reference]:
                    mark(message_id, "conflicting_reference_context")
                for message_id, _, _, _ in media_refs.get(reference, ()):
                    mark(message_id, "conflicting_reference_context")
                continue
            path = next(iter(index_paths))
            posts = media_refs.get(reference, [])
            compatible_posts = [item for item in posts if item[1] == path]
            module_key = _node_key("module", path)
            lesson_key = f"lesson:{reference}"
            occurrences = index_lesson_occurrences[reference]
            index_ordinal = min((item[2] for item in occurrences), default=1)
            if len(posts) != len(compatible_posts) or len(compatible_posts) > 1:
                nodes[lesson_key] = ParsedNode(
                    lesson_key, "lesson", module_key, None, reference, index_ordinal, None
                )
                for message_id in ref_messages[reference]:
                    mark(message_id, "conflicting_reference_post")
                for message_id, _, _, _ in posts:
                    mark(message_id, "conflicting_reference_post")
                continue
            if not compatible_posts:
                nodes[lesson_key] = ParsedNode(
                    lesson_key, "lesson", module_key, None, reference, index_ordinal, None
                )
                for message_id in ref_messages[reference]:
                    mark(message_id, "unresolved_content_reference")
                continue
            message_id, _, lesson_title, lesson_ordinal = compatible_posts[0]
            nodes[lesson_key] = ParsedNode(
                lesson_key,
                "lesson",
                module_key,
                lesson_title,
                reference,
                max(lesson_ordinal, len(nodes) + 1),
                message_id,
            )
            post_media = next(m.media for m in ordered if m.telegram_message_id == message_id)
            media_links.extend(
                MediaLink(message_id, item.media_ordinal, lesson_key) for item in post_media
            )

        for reference, posts in media_refs.items():
            if reference not in index_contexts:
                for message_id, _, _, _ in posts:
                    mark(message_id, "orphan_media_reference")

        for reference, origins in document_origins.items():
            source_candidates = origins & document_media
            source_id = min(source_candidates) if source_candidates else None
            key = f"document:{reference.casefold()}"
            next_ordinal += 1
            nodes[key] = ParsedNode(
                key, "document", None, reference, reference, next_ordinal, source_id
            )
            if source_id is None:
                for origin in origins:
                    mark(origin, "unresolved_document_reference")

        unresolved_rows = tuple(
            UnclassifiedSource(message_id, ",".join(sorted(reasons)))
            for message_id, reasons in sorted(unresolved.items())
        )
        return ParseResult(
            nodes=tuple(nodes.values()),
            media_links=tuple(media_links),
            unresolved=unresolved_rows,
        )
