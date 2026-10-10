"""Offline orchestration for explicit catalog builds."""

from __future__ import annotations

from telegram_courses.catalog import CatalogBuilder, ParserRegistry
from telegram_courses.catalog_repository import (
    CatalogBuildRecord,
    SQLiteCatalogRepository,
)


class CatalogApplication:
    def __init__(
        self,
        repository: SQLiteCatalogRepository,
        registry: ParserRegistry | None = None,
        builder: CatalogBuilder | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry or ParserRegistry()
        self.builder = builder or CatalogBuilder()

    async def build(
        self, channel_id: int, *, explicit_parser_key: str | None = None
    ) -> CatalogBuildRecord:
        await self.repository.migrate()
        catalog_input = await self.repository.load_catalog_input(channel_id)
        configured = (
            explicit_parser_key
            if explicit_parser_key is not None
            else catalog_input.configured_parser_key
        )
        selection = self.registry.select(configured)
        parser = selection.parser
        from telegram_courses.catalog import ParserContext

        context = ParserContext(channel_id, parser.key, parser.grammar_version)
        parsed = parser.parse(context, catalog_input.messages)
        plan = self.builder.build(context, catalog_input.messages, parsed)
        return await self.repository.save_catalog(
            plan,
            expected_source_fingerprint=catalog_input.fingerprint,
            expected_configured_parser_key=catalog_input.configured_parser_key,
            explicit_parser_key=explicit_parser_key,
        )
