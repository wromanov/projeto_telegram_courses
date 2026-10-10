"""Pure catalog models, parser registry, generic parsing, and validation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class CatalogError(Exception):
    """Safe catalog-domain failure with a stable public category."""

    def __init__(self, category: str) -> None:
        if category not in {
            "UNKNOWN_PARSER_KEY",
            "CHANNEL_NOT_FOUND",
            "INVALID_SOURCE",
            "INVALID_CATALOG",
            "SOURCE_CHANGED",
        }:
            raise ValueError("invalid catalog error category")
        self.category = category
        super().__init__(category.lower().replace("_", " "))


@dataclass(frozen=True)
class SourceMedia:
    telegram_message_id: int
    media_ordinal: int
    kind: str
    telegram_media_id: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None


@dataclass(frozen=True)
class SourceMessage:
    channel_id: int
    telegram_message_id: int
    date_utc: str
    edit_date_utc: str | None
    text: str | None
    grouped_id: int | None
    media: tuple[SourceMedia, ...] = ()


def source_fingerprint(messages: Sequence[SourceMessage]) -> str:
    """Hash the complete source snapshot without persisting message content."""
    payload = [
        {
            "channel_id": message.channel_id,
            "telegram_message_id": message.telegram_message_id,
            "date_utc": message.date_utc,
            "edit_date_utc": message.edit_date_utc,
            "text": message.text,
            "grouped_id": message.grouped_id,
            "media": [
                {
                    "telegram_message_id": item.telegram_message_id,
                    "media_ordinal": item.media_ordinal,
                    "kind": item.kind,
                    "telegram_media_id": item.telegram_media_id,
                    "original_filename": item.original_filename,
                    "mime_type": item.mime_type,
                    "file_size_bytes": item.file_size_bytes,
                }
                for item in sorted(message.media, key=lambda media: media.media_ordinal)
            ],
        }
        for message in sorted(messages, key=lambda item: item.telegram_message_id)
    ]
    encoded = json.dumps(
        payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ParserContext:
    channel_id: int
    parser_key: str
    grammar_version: str


@dataclass(frozen=True)
class ParsedNode:
    node_key: str
    kind: str
    parent_key: str | None
    title: str | None
    code: str | None
    ordinal: int
    source_message_id: int | None


@dataclass(frozen=True)
class MediaLink:
    telegram_message_id: int
    media_ordinal: int
    catalog_node_key: str


@dataclass(frozen=True)
class UnclassifiedSource:
    telegram_message_id: int
    reason: str


@dataclass(frozen=True)
class ParseResult:
    nodes: tuple[ParsedNode, ...]
    media_links: tuple[MediaLink, ...]
    unresolved: tuple[UnclassifiedSource, ...] = ()


class CatalogParser(Protocol):
    key: str
    grammar_version: str

    def parse(
        self, context: ParserContext, messages: Sequence[SourceMessage]
    ) -> ParseResult: ...


@dataclass(frozen=True)
class ParserSelection:
    parser: CatalogParser
    reason: str


class GenericParser:
    """One stable, unclassified node per source message; never infers hierarchy."""

    key = "generic"
    grammar_version = "generic-v1"

    def parse(
        self, context: ParserContext, messages: Sequence[SourceMessage]
    ) -> ParseResult:
        nodes: list[ParsedNode] = []
        media_links: list[MediaLink] = []
        for ordinal, message in enumerate(
            sorted(messages, key=lambda item: item.telegram_message_id), start=1
        ):
            if message.channel_id != context.channel_id:
                raise CatalogError("INVALID_SOURCE")
            node_key = f"message:{message.telegram_message_id}"
            nodes.append(
                ParsedNode(
                    node_key=node_key,
                    kind="unclassified",
                    parent_key=None,
                    title=message.text,
                    code=None,
                    ordinal=ordinal,
                    source_message_id=message.telegram_message_id,
                )
            )
            media_links.extend(
                MediaLink(
                    telegram_message_id=media.telegram_message_id,
                    media_ordinal=media.media_ordinal,
                    catalog_node_key=node_key,
                )
                for media in sorted(message.media, key=lambda item: item.media_ordinal)
            )
        return ParseResult(tuple(nodes), tuple(media_links))


@dataclass(frozen=True)
class CatalogPlan:
    context: ParserContext
    nodes: tuple[ParsedNode, ...]
    media_links: tuple[MediaLink, ...]
    message_count: int
    unresolved: tuple[UnclassifiedSource, ...]


class ParserRegistry:
    """Explicit per-channel parser selection with Generic as the only fallback."""

    def __init__(self, parsers: Sequence[CatalogParser] = ()) -> None:
        self._parsers: dict[str, CatalogParser] = {}
        self.register(GenericParser())
        for parser in parsers:
            self.register(parser)

    def register(self, parser: CatalogParser) -> None:
        key = getattr(parser, "key", None)
        version = getattr(parser, "grammar_version", None)
        if (
            not isinstance(key, str)
            or not key
            or not key.isascii()
            or not key.replace("-", "").replace("_", "").isalnum()
            or not isinstance(version, str)
            or not version
        ):
            raise ValueError("invalid parser registration")
        if key in self._parsers:
            raise ValueError("parser key already registered")
        self._parsers[key] = parser

    def select(self, configured_key: str | None) -> ParserSelection:
        key = "generic" if configured_key is None else configured_key
        parser = self._parsers.get(key)
        if parser is None:
            raise CatalogError("UNKNOWN_PARSER_KEY")
        reason = "channel configuration" if configured_key is not None else "generic fallback"
        return ParserSelection(parser, reason)

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._parsers))


class CatalogBuilder:
    """Validate parser output and produce a deterministic catalog plan."""

    _parent_kinds = {
        "track": frozenset(),
        "course": frozenset({"track"}),
        "module": frozenset({"course"}),
        "lesson": frozenset({"course", "module"}),
        "unclassified": frozenset(),
    }

    def build(
        self,
        context: ParserContext,
        messages: Sequence[SourceMessage],
        parsed: ParseResult,
    ) -> CatalogPlan:
        ordered_messages = tuple(
            sorted(messages, key=lambda item: item.telegram_message_id)
        )
        source_ids = [item.telegram_message_id for item in ordered_messages]
        if (
            len(source_ids) != len(set(source_ids))
            or any(item.channel_id != context.channel_id for item in ordered_messages)
            or any(item.telegram_message_id <= 0 for item in ordered_messages)
        ):
            raise CatalogError("INVALID_SOURCE")
        source_set = set(source_ids)
        media_keys = {
            (message.telegram_message_id, media.media_ordinal)
            for message in ordered_messages
            for media in message.media
        }
        if len(media_keys) != sum(len(message.media) for message in ordered_messages):
            raise CatalogError("INVALID_SOURCE")

        nodes = tuple(sorted(parsed.nodes, key=lambda node: (node.ordinal, node.node_key)))
        by_key: dict[str, ParsedNode] = {}
        for node in nodes:
            if (
                not node.node_key
                or node.node_key in by_key
                or node.kind not in self._parent_kinds
                or type(node.ordinal) is not int
                or node.ordinal < 0
                or (
                    node.source_message_id is not None
                    and node.source_message_id not in source_set
                )
            ):
                raise CatalogError("INVALID_CATALOG")
            by_key[node.node_key] = node

        for node in nodes:
            allowed = self._parent_kinds[node.kind]
            if node.parent_key is None:
                if node.kind in {"module", "lesson"}:
                    raise CatalogError("INVALID_CATALOG")
                continue
            parent = by_key.get(node.parent_key)
            if parent is None or parent.kind not in allowed:
                raise CatalogError("INVALID_CATALOG")

        link_keys: set[tuple[int, int]] = set()
        links = tuple(
            sorted(
                parsed.media_links,
                key=lambda link: (link.telegram_message_id, link.media_ordinal),
            )
        )
        for link in links:
            media_key = (link.telegram_message_id, link.media_ordinal)
            node = by_key.get(link.catalog_node_key)
            if (
                media_key not in media_keys
                or media_key in link_keys
                or node is None
                or node.kind not in {"lesson", "unclassified"}
                or node.source_message_id != link.telegram_message_id
            ):
                raise CatalogError("INVALID_CATALOG")
            link_keys.add(media_key)

        unresolved_ids = [item.telegram_message_id for item in parsed.unresolved]
        if any(message_id not in source_set for message_id in unresolved_ids):
            raise CatalogError("INVALID_CATALOG")
        return CatalogPlan(
            context=context,
            nodes=nodes,
            media_links=links,
            message_count=len(ordered_messages),
            unresolved=tuple(sorted(parsed.unresolved, key=lambda item: item.telegram_message_id)),
        )
