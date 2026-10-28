"""Deterministic local S0 command line entry point."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import io
import os
import re
import sys
import unicodedata
from collections.abc import Callable, Sequence

from rich.console import Console
from rich.table import Table

from telegram_courses import __version__
from telegram_courses.auth import AuthenticationError
from telegram_courses.auth_application import AuthenticationApplication
from telegram_courses.catalog import CatalogError
from telegram_courses.catalog_application import CatalogApplication
from telegram_courses.catalog_repository import SQLiteCatalogRepository
from telegram_courses.channel_discovery import (
    ChannelDiscoveryApplication,
    ChannelDiscoveryError,
    DiscoveryErrorCategory,
    DiscoveryOutcomeState,
    DiscoveryResult,
    select_channel,
)
from telegram_courses.config import (
    ConfigurationError,
    TelegramCredentials,
    load_configuration,
    load_telegram_credentials,
)
from telegram_courses.credentials import (
    CredentialVault,
    CredentialVaultError,
    validate_credentials,
)
from telegram_courses.download_repository import DownloadRepository
from telegram_courses.downloads import (
    CHUNK_BYTES,
    DownloadError,
    DownloadGatewayError,
    SingleMediaDownloadApplication,
)
from telegram_courses.message_scanner import ScanGatewayError
from telegram_courses.operational_logging import (
    configure_operational_logging,
    emit_operational_event,
)
from telegram_courses.telethon_gateway import TelethonGateway


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ConfigurationError from None


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    raw_arguments = list(argv) if argv is not None else sys.argv[1:]

    def supplied_once(option: str) -> bool:
        count = sum(
            token == option or token.startswith(f"{option}=")
            for token in raw_arguments
        )
        if count > 1:
            raise ConfigurationError from None
        return count == 1

    parser = _ArgumentParser(prog="telegram-courses", add_help=True)
    parser.add_argument(
        "command", choices=("smoke", "auth", "channels", "scan", "credentials", "catalog", "download")
    )
    parser.add_argument(
        "credentials_action", nargs="?", choices=("setup", "status", "build", "list", "show", "items", "plan", "queue")
    )
    parser.add_argument("--config", action="append")
    parser.add_argument("--log-level", action="append")
    parser.add_argument("--channel-id", type=int)
    parser.add_argument("--telegram-message-id", type=int)
    parser.add_argument("--media-ordinal", type=int)
    parser.add_argument(
        "--download-dir",
        default=os.environ.get("TELEGRAM_COURSES_DOWNLOAD_DIR", "downloads"),
    )
    parser.add_argument("--max-messages", type=int)
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--incremental", action="store_true")
    parser.add_argument("--reconcile-window", type=int)
    parser.add_argument("--database", default="data/catalog.sqlite3")
    parser.add_argument("--parser-key")
    parser.add_argument("--scope", choices=("channel", "course", "module", "lesson"), default="channel")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--attempts-per-media", type=int, default=3)
    parser.add_argument("--max-media-items", type=int)
    parser.add_argument("--max-transfer-bytes", type=int)
    parser.add_argument(
        "--integrity-mode",
        choices=("REMOTE_HASH_REQUIRED", "OPERATIONAL_ONLY", "TRUSTED_REFERENCE"),
        default="REMOTE_HASH_REQUIRED",
    )
    parser.add_argument("--reference-manifest")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(raw_arguments)
    if (args.config is not None and len(args.config) != 1) or (
        args.log_level is not None and len(args.log_level) != 1
    ):
        raise ConfigurationError
    args.config = args.config[0] if args.config else None
    args.log_level = args.log_level[0] if args.log_level else None
    args.cli_download_dir = (
        args.download_dir if supplied_once("--download-dir") else None
    )
    args.cli_database_path = args.database if supplied_once("--database") else None
    args.cli_workers = args.workers if supplied_once("--workers") else None
    args.cli_attempts_per_media = (
        args.attempts_per_media
        if supplied_once("--attempts-per-media")
        else None
    )
    if args.command != "download" and (
        args.max_media_items is not None or args.max_transfer_bytes is not None
        or args.integrity_mode != "REMOTE_HASH_REQUIRED" or args.reference_manifest is not None
    ):
        raise ConfigurationError from None
    if args.command != "scan" and (
        args.incremental or args.reconcile_window is not None
    ):
        raise ConfigurationError from None
    if args.command in {"credentials", "catalog"} and args.credentials_action is None:
        raise ConfigurationError from None
    if args.command not in {"credentials", "catalog", "download"} and args.credentials_action is not None:
        raise ConfigurationError from None
    if args.command == "credentials" and args.credentials_action not in {"setup", "status"}:
        raise ConfigurationError from None
    if args.command == "catalog" and args.credentials_action not in {"build", "list", "show", "items"}:
        raise ConfigurationError from None
    if args.parser_key is not None and args.command != "catalog":
        raise ConfigurationError from None
    if args.parser_key is not None and args.credentials_action != "build":
        raise ConfigurationError from None
    if args.command == "scan":
        if (
            args.channel_id is None
            or not args.channel_id
            or not args.max_messages
            or args.timeout_seconds is None
        ):
            raise ConfigurationError from None
        if args.max_messages <= 0 or args.timeout_seconds <= 0:
            raise ConfigurationError from None
        if args.incremental:
            if args.reconcile_window is None or args.reconcile_window < 0:
                raise ConfigurationError from None
        elif args.reconcile_window is not None:
            raise ConfigurationError from None
    elif args.command == "download":
        if (
            args.integrity_mode == "TRUSTED_REFERENCE"
        ) != (args.reference_manifest is not None):
            raise ConfigurationError from None
        if args.credentials_action in {"plan", "queue"}:
            if (args.channel_id is None or args.channel_id == 0
                    or args.telegram_message_id is not None or args.media_ordinal is not None
                    or args.max_messages is not None or args.timeout_seconds is not None
                    or not 1 <= args.workers <= 2 or args.confirm and args.credentials_action != "queue"
                    or not 1 <= args.attempts_per_media <= 3
                    or args.max_media_items is not None and args.max_media_items <= 0
                    or args.max_transfer_bytes is not None and args.max_transfer_bytes <= 0):
                raise ConfigurationError from None
        elif (
            args.credentials_action is not None
            or args.max_media_items is not None or args.max_transfer_bytes is not None
            or args.channel_id is None or args.channel_id == 0
            or args.telegram_message_id is None or args.telegram_message_id <= 0
            or args.media_ordinal is None or args.media_ordinal < 0
            or args.max_messages is not None or args.timeout_seconds is not None
        ):
            raise ConfigurationError from None
        if args.credentials_action not in {"plan", "queue"} and (
            args.cli_workers is not None or args.cli_attempts_per_media is not None
        ):
            raise ConfigurationError from None
    elif args.command == "catalog":
        if args.max_messages is not None or (
            args.credentials_action == "build" and (args.channel_id is None or not args.channel_id)
        ) or (
            args.credentials_action in {"list"} and args.channel_id is not None
        ):
            raise ConfigurationError from None
    elif any(value is not None for value in (args.channel_id, args.max_messages, args.telegram_message_id, args.media_ordinal)):
        raise ConfigurationError from None
    return args


def _download_single(
    *, channel_id: int, message_id: int, media_ordinal: int, database: str,
    download_dir: str, integrity_mode: str = "REMOTE_HASH_REQUIRED",
    reference_manifest_path: str | None = None,
    gateway_factory: Callable[[TelegramCredentials], object] = TelethonGateway,
    credentials_loader: Callable[[], TelegramCredentials] = load_telegram_credentials,
) -> int:
    if integrity_mode != "REMOTE_HASH_REQUIRED":
        Console(file=sys.stdout, force_terminal=False, no_color=True).print(
            f"modo selecionado={integrity_mode} garantia pretendida="
            f"{'UNVERIFIED_ORIGIN' if integrity_mode == 'OPERATIONAL_ONLY' else 'REFERENCE_MATCH'} "
            "limitação=V2_EFFECTIVE_NO; estimativa=use download queue plan; "
            "bloqueado antes de banco/RPC/payload",
            markup=False, highlight=False,
        )
        return 4
    from telegram_courses.auth import AuthState

    async def run() -> object:
        class _LazyGateway:
            def __init__(self) -> None:
                self.gateway: object | None = None

            async def stream_media(self, *args: object, **kwargs: object):
                if self.gateway is None:
                    try:
                        self.gateway = gateway_factory(credentials_loader())
                        state = await self.gateway.restore()
                    except ConfigurationError:
                        raise DownloadGatewayError("CONFIGURATION") from None
                    except Exception:
                        raise DownloadGatewayError("GATEWAY_FAILURE") from None
                    if state is not AuthState.AUTHENTICATED:
                        raise DownloadGatewayError("SESSION_INVALID")
                async for chunk in self.gateway.stream_media(*args, **kwargs):
                    yield chunk

        lazy_gateway = _LazyGateway()
        try:
            repository = DownloadRepository(database)
            await repository.migrate()
            candidate = await repository.select_candidate(channel_id, message_id, media_ordinal)
            if candidate is None:
                raise DownloadError("MEDIA_NOT_ELIGIBLE")
            initial = await repository.get_record(candidate.media_item_id)
            Console(file=sys.stdout, force_terminal=False, no_color=True).print(
                f"selected channel_id={channel_id} telegram_message_id={message_id} "
                f"media_ordinal={media_ordinal} expected_bytes={candidate.expected_bytes} "
                f"initial_state={initial.state if initial else 'NEW'}",
                markup=False, highlight=False,
            )
            application = SingleMediaDownloadApplication(
                repository, lazy_gateway, download_dir,
                progress_callback=lambda current, total: Console(
                    file=sys.stdout, force_terminal=False, no_color=True
                ).print(f"progress bytes={current}/{total}", markup=False, highlight=False),
            )
            return await application.download(
                channel_id, message_id, media_ordinal,
                integrity_mode=integrity_mode,
                reference_manifest_path=reference_manifest_path,
            )
        finally:
            if lazy_gateway.gateway is not None:
                await lazy_gateway.gateway.close()

    result = asyncio.run(run())
    Console(file=sys.stdout, force_terminal=False, no_color=True).print(
        f"download result={result.result} channel_id={channel_id} "
        f"telegram_message_id={message_id} media_ordinal={media_ordinal} "
        f"bytes={result.transferred_bytes} path={result.final_path}",
        markup=False, highlight=False,
    )
    return 0


def _download_batch(
    *, args: argparse.Namespace,
    selection_prompt: Callable[[str], str],
    gateway_factory: Callable[[TelegramCredentials], object],
    credentials_loader: Callable[[], TelegramCredentials],
) -> int:
    from telegram_courses.s5_downloads import (
        DownloadPlanner,
        DownloadQueue,
        DownloadSelection,
    )

    planner = DownloadPlanner(args.database, args.download_dir)
    console = Console(file=_CatalogOutput(sys.stdout), force_terminal=False, no_color=True, color_system=None)

    async def make_plan():
        node_id = None
        if args.scope != "channel":
            choices = planner.selectable_nodes(args.channel_id, args.scope)
            if not choices:
                raise DownloadError("NO_SELECTABLE_CONTENT")
            for index, (_, title) in enumerate(choices, start=1):
                console.print(f"[{index}] {_safe_terminal_text(title)}", markup=False, highlight=False)
            if not sys.stdin.isatty() and selection_prompt is input:
                raise ConfigurationError from None
            answer = selection_prompt("Selecione o conteúdo ou Q para cancelar: ").strip()
            if answer.casefold() == "q":
                return None
            if not answer.isdecimal() or not 1 <= int(answer) <= len(choices):
                raise ConfigurationError from None
            node_id = choices[int(answer) - 1][0]
        return await planner.build(DownloadSelection(args.channel_id, args.scope, node_id))

    plan = asyncio.run(make_plan())
    if plan is None:
        console.print("seleção cancelada", markup=False, highlight=False)
        return 0
    console.print(
        f"Plano {plan.plan_id} | {_safe_terminal_text(plan.scope_title)} | aulas={plan.lesson_count} "
        f"elegíveis={len(plan.eligible)} pendentes={len(plan.pending)} já válidas={len(plan.already_valid)} "
        f"bloqueadas={len(plan.blocked)} excluídas={len(plan.excluded)} "
        f"bytes pendentes={plan.pending_bytes} margem={plan.safety_margin}",
        markup=False, highlight=False,
    )
    for item in plan.pending:
        if item.status == "CONDITIONAL_RESUME_CANDIDATE" and item.candidate is not None:
            expected = item.candidate.expected_bytes
            console.print(
                "CONDITIONAL_RESUME_CANDIDATE "
                f"message={item.identity[1]} E={expected} P={item.part_bytes} "
                f"E-P={expected - item.part_bytes} W={item.wire_offset} O={item.overlap_bytes} "
                f"payload_estimate={item.estimated_payload_bytes} "
                f"additional_disk_estimate={item.estimated_additional_disk_bytes} "
                "estimate=PROVISIONAL remote_validation=REQUIRED",
                markup=False, highlight=False,
            )
    selected_count = len(plan.items)
    expected_bytes = sum(
        item.candidate.expected_bytes for item in plan.eligible if item.candidate is not None
    )
    unknown_sizes = sum(item.reason == "UNKNOWN_SIZE" for item in plan.excluded)
    deterministic_plan = asyncio.run(planner.build(plan.selection))
    deterministic_order = (
        plan.plan_id == deterministic_plan.plan_id
        and tuple(item.identity for item in plan.items)
        == tuple(item.identity for item in deterministic_plan.items)
    )
    limit_checks = []
    if args.max_media_items is not None:
        limit_checks.append(selected_count <= args.max_media_items)
    if args.max_transfer_bytes is not None:
        limit_checks.extend((plan.pending_bytes <= args.max_transfer_bytes, unknown_sizes == 0))
    limit_check = "NOT_CONFIGURED" if not limit_checks else "PASS" if all(limit_checks) else "FAIL"
    for name, value in (
        ("MODULE_SELECTED", "YES" if args.scope == "module" else "NO"),
        ("LESSON_COUNT", plan.lesson_count),
        ("MEDIA_COUNT", selected_count),
        ("TOTAL_EXPECTED_BYTES", expected_bytes),
        ("DETERMINISTIC_ORDER", "PASS" if deterministic_order else "FAIL"),
        ("SELECTED_MEDIA_COUNT", selected_count),
        ("PENDING_MEDIA_COUNT", len(plan.pending)),
        ("ALREADY_VALID_COUNT", len(plan.already_valid)),
        ("EXCLUDED_COUNT", len(plan.excluded) + len(plan.blocked)),
        ("PENDING_BYTES", plan.pending_bytes),
        ("CONFIGURED_MEDIA_LIMIT", args.max_media_items if args.max_media_items is not None else "UNLIMITED"),
        ("CONFIGURED_BYTE_LIMIT", args.max_transfer_bytes if args.max_transfer_bytes is not None else "UNLIMITED"),
        ("LIMIT_CHECK_RESULT", limit_check),
    ):
        console.print(f"{name}={value}", markup=False, highlight=False)
    reasons: dict[str, int] = {}
    for item in (*plan.excluded, *plan.blocked):
        reasons[item.reason or item.status] = reasons.get(item.reason or item.status, 0) + 1
    for reason, count in sorted(reasons.items()):
        console.print(f"  {reason}: {count}", markup=False, highlight=False)
    if not plan.catalog_complete:
        console.print("catálogo parcial: o plano cobre somente o conteúdo observado", markup=False, highlight=False)
    mode = args.integrity_mode
    guarantee = {
        "REMOTE_HASH_REQUIRED": "REMOTE_HASH_FULL / V1 fail-closed",
        "OPERATIONAL_ONLY": "OPERATIONAL_ONLY / UNVERIFIED_ORIGIN",
        "TRUSTED_REFERENCE": "REFERENCE_MATCH; hashes remotos permanecem independentes",
    }[mode]
    if mode == "OPERATIONAL_ONLY":
        reread = sum(
            ((item.part_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES) * CHUNK_BYTES
            for item in plan.pending
        )
        transfer = sum(
            ((max(0, item.candidate.expected_bytes - item.wire_offset) + CHUNK_BYTES - 1)
             // CHUNK_BYTES) * CHUNK_BYTES
            for item in plan.pending if item.candidate is not None
        )
        cost = f"releitura_reservada={reread} transfer_reservado={transfer} total={reread + transfer} bytes"
        limitation = "origem não verificada criptograficamente"
    elif mode == "TRUSTED_REFERENCE":
        transfer = sum(item.estimated_payload_bytes or 0 for item in plan.pending)
        cost = f"payload_estimado={transfer} bytes; releitura_integral_de_prefixo=0"
        limitation = "referência local e manifesto devem permanecer estáveis; não prova origem Telegram"
    else:
        cost = "releitura adicional=0; custo exato de hashes depende das faixas remotas"
        limitation = "qualquer ausência, indisponibilidade, resposta inválida ou divergência não permite downgrade"
    console.print(
        f"modo selecionado={mode} garantia pretendida={guarantee} "
        f"limitação={limitation} custo={cost}",
        markup=False, highlight=False,
    )
    if args.credentials_action == "plan":
        return 0 if deterministic_order else 4
    if mode == "TRUSTED_REFERENCE":
        if len(plan.pending) != 1 or plan.pending[0].candidate is None:
            console.print("bloqueado: TRUSTED_REFERENCE exige exatamente um item pendente", markup=False, highlight=False)
            return 4
        from telegram_courses.s6_integrity import load_reference
        candidate = plan.pending[0].candidate
        try:
            load_reference(
                args.reference_manifest,
                channel_id=candidate.channel_id,
                telegram_message_id=candidate.telegram_message_id,
                media_ordinal=candidate.media_ordinal,
                telegram_media_id=candidate.telegram_media_id,
                expected_bytes=candidate.expected_bytes,
            )
        except (OSError, ValueError):
            console.print("bloqueado: referência ou manifesto inválido para o item selecionado", markup=False, highlight=False)
            return 4
    if mode != "REMOTE_HASH_REQUIRED":
        console.print(
            "execução bloqueada: V2_EFFECTIVE=NO; nenhum modo V2 pode iniciar RPC ou payload",
            markup=False, highlight=False,
        )
        return 4
    if limit_check == "FAIL" or not deterministic_order:
        console.print("execução bloqueada: prévia ou limites configurados não aprovados", markup=False, highlight=False)
        return 4
    if not plan.pending:
        console.print(
            "status=SKIPPED nenhuma transferência pendente; conteúdo completo ou sem itens elegíveis",
            markup=False,
            highlight=False,
        )
        return 0
    if args.confirm:
        confirmed = True
    else:
        if not sys.stdin.isatty() and selection_prompt is input:
            raise ConfigurationError from None
        confirmed = selection_prompt("Iniciar os downloads? [s/N] ").strip().casefold() in {"s", "sim", "y", "yes"}
    if not confirmed:
        console.print("execução não confirmada", markup=False, highlight=False)
        return 0

    from telegram_courses.auth import AuthState

    class _LazyGateway:
        def __init__(self) -> None:
            self.gateway = None
            self._initialization: asyncio.Task[object] | None = None

        async def _initialize(self) -> object:
            try:
                self.gateway = gateway_factory(credentials_loader())
                state = await self.gateway.restore()
            except ConfigurationError:
                raise DownloadGatewayError("CONFIGURATION") from None
            except Exception:
                raise DownloadGatewayError("GATEWAY_FAILURE") from None
            if state is not AuthState.AUTHENTICATED:
                raise DownloadGatewayError("SESSION_INVALID")
            return self.gateway

        async def stream_media(self, *call_args: object, **kwargs: object):
            if self._initialization is None:
                self._initialization = asyncio.create_task(self._initialize())
            gateway = await self._initialization
            async for chunk in gateway.stream_media(*call_args, **kwargs):
                yield chunk
        async def get_file_hashes(self, *call_args: object, **kwargs: object):
            if self._initialization is None:
                self._initialization = asyncio.create_task(self._initialize())
            gateway = await self._initialization
            getter = getattr(gateway, "get_file_hashes", None)
            if not callable(getter):
                raise DownloadGatewayError("REMOTE_HASHES_UNAVAILABLE")
            return await getter(*call_args, **kwargs)
        async def close(self) -> None:
            if self.gateway is not None:
                await self.gateway.close()

    async def execute():
        gateway = _LazyGateway()
        try:
            repository = DownloadRepository(args.database)
            app = SingleMediaDownloadApplication(
                repository, gateway, args.download_dir,
                progress_callback=lambda current, total: console.print(
                    f"progresso bytes={current}/{total}", markup=False, highlight=False
                ),
            )
            queue = DownloadQueue(
                repository, app, workers=args.workers,
                attempts_per_media=args.attempts_per_media,
                max_media_items=args.max_media_items,
                max_transfer_bytes=args.max_transfer_bytes,
                integrity_mode=args.integrity_mode,
                reference_manifest_path=args.reference_manifest,
                progress_callback=lambda state: console.print(
                    f"fila total={state['total']} pendentes={state['pending']} "
                    f"em_execução={state['running']} concluídos={state['completed']} "
                    f"já_baixados={state['already_valid']} falhos={state['failed']} "
                    f"bytes={state['bytes_transferred']}/{state['bytes_expected']} "
                    f"tempo={state['elapsed_seconds']}s velocidade={state['bytes_per_second']}B/s",
                    markup=False, highlight=False,
                ),
            )
            return await queue.run(plan)
        finally:
            await gateway.close()

    result = asyncio.run(execute())
    for identity, status, detail in result.outcomes:
        if status in {"COMPLETED_V2", "RECOVERED_V2", "ALREADY_COMPLETED_V2"}:
            console.print(
                f"evidência obtida item={identity} resultado={status} detalhe={detail}",
                markup=False, highlight=False,
            )
    counts = {key: sum(status == key for _, status, _ in result.outcomes)
              for key in (
                  "COMPLETED", "COMPLETED_V2", "RECOVERED_V2", "ALREADY_COMPLETED_V2",
                  "ALREADY_VALID", "FAILED", "BLOCKED", "CANCELLED",
              )}
    completed_count = counts["COMPLETED"]
    failed_count = counts["FAILED"] + counts["BLOCKED"]
    skipped_count = counts["ALREADY_VALID"] + sum(
        status in {"EXCLUDED", "SKIPPED"} for _, status, _ in result.outcomes
    )
    if result.cancelled:
        final_status = "CANCELLED"
    elif failed_count:
        final_status = "PARTIAL" if completed_count or counts["ALREADY_VALID"] else "FAILED"
    elif completed_count:
        final_status = "COMPLETED"
    else:
        final_status = "SKIPPED"
    console.print(
        f"status={final_status} fila concluída total={len(result.outcomes)} concluídos={counts['COMPLETED']} "
        f"concluídos_v2={counts['COMPLETED_V2'] + counts['RECOVERED_V2']} "
        f"já_concluídos_v2={counts['ALREADY_COMPLETED_V2']} "
        f"já válidos={counts['ALREADY_VALID']} falhos={counts['FAILED']} bloqueados={counts['BLOCKED']} "
        f"bytes transferidos={result.transferred_bytes} tentativas={result.attempts} "
        f"tempo={result.elapsed_seconds:.1f}s",
        markup=False, highlight=False,
    )
    emit_operational_event(
        "download.queue.finished",
        component="cli.download",
        status=final_status,
        items_total=len(result.outcomes),
        items_completed=completed_count,
        items_failed=failed_count,
        items_skipped=skipped_count,
        workers=args.workers,
    )
    return 130 if result.cancelled else (4 if result.failed else 0)


def _scan_channel(
    *,
    channel_id: int,
    max_messages: int,
    timeout_seconds: float,
    database: str,
    gateway_factory: Callable[[TelegramCredentials], object],
    credentials_loader: Callable[[], TelegramCredentials] = load_telegram_credentials,
    incremental: bool = False,
    reconcile_window: int = 0,
) -> int:
    from telegram_courses.message_scanner import ScanRequest
    from telegram_courses.scan_application import ScanApplication
    from telegram_courses.sqlite_repository import SQLiteMessageRepository

    application = ScanApplication(
        gateway_factory,
        credentials_loader,
        SQLiteMessageRepository(database),
    )
    outcome = asyncio.run(
        application.scan(
            channel_id,
            ScanRequest(
                max_messages=max_messages,
                timeout_seconds=timeout_seconds,
                mode="INCREMENTAL" if incremental else "FULL",
                reconcile_window=reconcile_window if incremental else 0,
            ),
        )
    )
    console = Console(file=sys.stdout, force_terminal=False, no_color=True)
    if incremental:
        catalog_result = None
        catalog_state = "NOT_REBUILT"
        if outcome.status.value == "COMPLETE":
            try:
                catalog_result = asyncio.run(
                    CatalogApplication(SQLiteCatalogRepository(database)).build(channel_id)
                )
                catalog_state = f"COMPLETE parser={catalog_result.parser_key}"
            except Exception as error:
                category = getattr(error, "category", type(error).__name__.upper())
                catalog_state = f"FAILED reason={category}"
        unverified = (
            "pending" if outcome.messages_unverified is None
            else str(outcome.messages_unverified)
        )
        high_water = (
            str(outcome.high_water_confirmed)
            if outcome.has_confirmed_high_water
            else "none"
        )
        console.print(
            f"sync channel={channel_id} mode=incremental max_messages={max_messages} "
            f"reconcile_window={reconcile_window} run={outcome.run_id} "
            f"status={outcome.status.value} new={outcome.messages_inserted} "
            f"updated={outcome.messages_updated} unchanged={outcome.messages_unchanged} "
            f"unverified={unverified} media_unverified={outcome.media_unverified} "
            f"checkpoint_confirmed={high_water} "
            f"cursor={outcome.last_message_id if outcome.last_message_id is not None else 'none'}"
            + f" catalog={catalog_state}"
            + (f" stop={outcome.stop_reason}" if outcome.stop_reason else ""),
            markup=False,
            highlight=False,
        )
    else:
        console.print(
            f"scan run={outcome.run_id} status={outcome.status.value} "
            f"messages={outcome.messages_seen} media={outcome.media_seen} "
            f"media_unverified={outcome.media_unverified}"
            + (f" stop={outcome.stop_reason}" if outcome.stop_reason else ""),
            markup=False,
            highlight=False,
        )
    if incremental:
        return 0 if outcome.status.value == "COMPLETE" and catalog_result is not None else 4
    return 0 if outcome.status.value == "COMPLETE" else 4


class _CatalogOutput:
    """Write Catalog text using escapes only for unencodable characters."""

    def __init__(self, stream: io.TextIOBase) -> None:
        self._stream = stream

    @property
    def encoding(self) -> str:
        return getattr(self._stream, "encoding", None) or "utf-8"

    def write(self, text: str) -> int:
        safe_text = text.encode(self.encoding, errors="backslashreplace").decode(self.encoding)
        self._stream.write(safe_text)
        return len(text)

    def flush(self) -> None:
        self._stream.flush()

    def __getattr__(self, name: str) -> object:
        return getattr(self._stream, name)


def _catalog_command(args: argparse.Namespace, selection_prompt: Callable[[str], str]) -> int:
    repository = SQLiteCatalogRepository(args.database)
    application = CatalogApplication(repository)
    console = Console(file=_CatalogOutput(sys.stdout), force_terminal=False, no_color=True, color_system=None, width=140)

    async def run() -> tuple[object, ...] | object:
        if args.credentials_action == "build":
            return await application.build(args.channel_id, explicit_parser_key=args.parser_key)
        await repository.migrate()
        if args.credentials_action == "list":
            return await repository.list_catalog_channels()
        channel_id = args.channel_id
        channels = await repository.list_catalog_channels()
        if channel_id is None:
            if not sys.stdin.isatty() and selection_prompt is input:
                raise ConfigurationError
            if not channels:
                return ()
            table = Table("#", "Canal", "ID", "Parser", show_lines=False)
            for index, item in enumerate(channels, start=1):
                table.add_row(str(index), _safe_terminal_text(item.title or "(sem título)"), str(item.channel_id), item.parser_key or "generic")
            console.print(table)
            answer = selection_prompt("Selecione o número do canal ou Q para cancelar: ").strip()
            if answer.casefold() == "q":
                return ()
            if not answer.isdecimal() or not 1 <= int(answer) <= len(channels):
                raise ConfigurationError
            channel_id = channels[int(answer) - 1].channel_id
        if args.credentials_action == "show":
            return await repository.get_catalog_nodes(channel_id)
        return await repository.get_catalog_items(channel_id)

    result = asyncio.run(run())
    if args.credentials_action == "build":
        console.print(
            f"catalog build complete channel={result.channel_id} parser={result.parser_key} "
            f"messages={result.source_message_count} nodes={result.catalog_node_count} "
            f"unresolved={result.unresolved_count}",
            markup=False, highlight=False,
        )
    elif args.credentials_action == "list":
        if not result:
            console.print("no catalog builds", markup=False, highlight=False)
        else:
            table = Table("Canal", "ID", "Parser", "Estado", "Mensagens", "Nós ativos", "Sem classificação")
            for item in result:
                table.add_row(_safe_terminal_text(item.title or "(sem título)"), str(item.channel_id), item.parser_key or "generic", item.catalog_status, str(item.source_message_count), str(item.active_node_count), str(item.unclassified_count))
            console.print(table)
    elif args.credentials_action == "show":
        if not result:
            console.print("catálogo vazio", markup=False, highlight=False)
        else:
            by_id = {item.node_id: item for item in result}
            def depth(item: object) -> int:
                level, parent = 0, item.parent_id
                seen: set[int] = set()
                while parent in by_id and parent not in seen:
                    seen.add(parent)
                    level += 1
                    parent = by_id[parent].parent_id
                return level
            table = Table("Tipo", "Código", "Ordem", "Título", "Mensagem", "Estado")
            for item in sorted(result, key=lambda node: (not node.is_active, depth(node), node.ordinal or 0, node.node_id)):
                title = _safe_terminal_text(item.title or "")
                table.add_row("  " * depth(item) + item.kind, item.code or "", str(item.ordinal or ""), title, str(item.source_message_id or ""), "ativo" if item.is_active else "inativo")
            console.print(table)
    else:
        if not result:
            console.print("nenhuma mensagem local", markup=False, highlight=False)
        else:
            table = Table("Mensagem", "Data UTC", "Classificação", "Texto", "Mídia")
            for item in result:
                media = ", ".join(
                    f"{m.kind}:{m.original_filename or m.telegram_media_id or 'sem identificador'}"
                    + (f" ({m.file_size_bytes} bytes)" if m.file_size_bytes is not None else " (tamanho desconhecido)")
                    for m in item.media
                )
                classification = ", ".join(item.node_kinds) or "—"
                if item.unresolved_reason:
                    classification += f" (não resolvido: {item.unresolved_reason})"
                table.add_row(str(item.telegram_message_id), item.date_utc, classification, _safe_terminal_text(item.text or ""), _safe_terminal_text(media))
            console.print(table)
    return 0


def _phone_prompt() -> str:
    return input("Phone: ")


def _secret_prompt(label: str) -> str:
    if not sys.stdin.isatty():
        raise ConfigurationError from None
    return getpass.getpass(label)


def _require_interactive() -> None:
    if not sys.stdin.isatty():
        raise ConfigurationError from None


def _credentials_setup(
    *,
    api_id_prompt: Callable[[], str],
    api_hash_prompt: Callable[[], str],
    vault_factory: Callable[[], CredentialVault],
) -> int:
    _require_interactive()
    api_id = api_id_prompt()
    api_hash = api_hash_prompt()
    credentials = validate_credentials(api_id, api_hash)
    vault_factory().setup(credentials)
    Console(file=sys.stdout, force_terminal=False, no_color=True).print(
        "credentials setup successful", markup=False, highlight=False
    )
    return 0


def _credentials_status(
    *, vault_factory: Callable[[], CredentialVault]
) -> int:
    available = vault_factory().status()
    state = "yes" if available else "no"
    Console(file=sys.stdout, force_terminal=False, no_color=True).print(
        f"credentials vault configured: {state}\ncredentials available: {state}",
        markup=False,
        highlight=False,
    )
    return 0


def _discovery_gateway(credentials: TelegramCredentials) -> TelethonGateway:
    return TelethonGateway(
        credentials,
        receive_updates=False,
        catch_up=False,
    )


def _scan_gateway(credentials: TelegramCredentials) -> TelethonGateway:
    return TelethonGateway(
        credentials,
        receive_updates=False,
        catch_up=False,
        request_retries=0,
        connection_retries=0,
    )


def _safe_terminal_text(value: str) -> str:
    return "".join(
        " " if character in "\r\n\t" else character
        for character in value
        if unicodedata.category(character) not in {"Cc", "Cf", "Cs"}
    )


def _render_discovery(result: DiscoveryResult) -> None:
    console = Console(
        file=sys.stdout,
        force_terminal=False,
        no_color=True,
        color_system=None,
        width=120,
    )
    if result.complete:
        console.print("discovery complete", markup=False, highlight=False)
    else:
        console.print(
            f"discovery partial: {result.stop_reason.value}",
            markup=False,
            highlight=False,
        )
    if not result.channels:
        console.print(
            "no eligible channels" if result.complete else "no candidates in partial discovery",
            markup=False,
            highlight=False,
        )
        return
    for index, channel in enumerate(result.channels, start=1):
        title = _safe_terminal_text(channel.title)
        username = (
            f" @{_safe_terminal_text(channel.username)}"
            if channel.username
            else ""
        )
        console.print(
            f"[{index}] {title}{username} | {channel.kind.value}",
            markup=False,
            highlight=False,
        )


def _select_from_local_snapshot(
    result: DiscoveryResult, selection: str
) -> int | None:
    if not isinstance(selection, str):
        raise ChannelDiscoveryError(DiscoveryErrorCategory.INVALID_SELECTION)
    selected_text = selection.strip()
    if not selected_text or selected_text.casefold() == "q":
        return None
    if re.fullmatch(r"[0-9]+", selected_text):
        try:
            index = int(selected_text)
        except ValueError:
            raise ChannelDiscoveryError(
                DiscoveryErrorCategory.INVALID_SELECTION
            ) from None
        if 1 <= index <= len(result.channels):
            return result.channels[index - 1].telegram_chat_id
        raise ChannelDiscoveryError(DiscoveryErrorCategory.INVALID_SELECTION)
    if re.fullmatch(r"-[0-9]+", selected_text) is None:
        raise ChannelDiscoveryError(DiscoveryErrorCategory.INVALID_SELECTION)
    try:
        selected_id = int(selected_text)
    except ValueError:
        raise ChannelDiscoveryError(
            DiscoveryErrorCategory.INVALID_SELECTION
        ) from None
    return select_channel(result, selected_id).telegram_chat_id


def _discover_channels(
    *,
    gateway_factory: Callable[[TelegramCredentials], object],
    selection_prompt: Callable[[str], str],
) -> int:
    if not sys.stdin.isatty() and selection_prompt is input:
        raise ConfigurationError from None
    application = ChannelDiscoveryApplication(
        gateway_factory,
        load_telegram_credentials,
    )
    try:
        outcome = asyncio.run(application.discover())
    except KeyboardInterrupt:
        Console(file=sys.stdout, force_terminal=False, no_color=True).print(
            "discovery cancelled", markup=False, highlight=False
        )
        return 130

    if outcome.state is DiscoveryOutcomeState.AUTH_REQUIRED:
        Console(file=sys.stdout, force_terminal=False, no_color=True).print(
            "run `telegram-courses auth` before channel discovery",
            markup=False,
            highlight=False,
        )
        return 3
    if outcome.state is DiscoveryOutcomeState.SESSION_INVALID:
        Console(file=sys.stdout, force_terminal=False, no_color=True).print(
            "session invalid; run `telegram-courses auth` before channel discovery",
            markup=False,
            highlight=False,
        )
        return 3

    assert outcome.result is not None
    result = outcome.result
    _render_discovery(result)
    if not result.channels:
        return 0 if result.complete else 4
    try:
        selection = selection_prompt("Select a number or Q to cancel: ")
    except KeyboardInterrupt:
        Console(file=sys.stdout, force_terminal=False, no_color=True).print(
            "selection cancelled", markup=False, highlight=False
        )
        return 0
    selected_id = _select_from_local_snapshot(result, selection)
    if selected_id is None:
        Console(file=sys.stdout, force_terminal=False, no_color=True).print(
            "selection cancelled", markup=False, highlight=False
        )
        return 0
    selected_summary = next(
        item for item in result.channels
        if item.telegram_chat_id == selected_id
    )
    Console(file=sys.stdout, force_terminal=False, no_color=True).print(
        f"selected telegram_chat_id={selected_id} "
        f"kind={selected_summary.kind.value}",
        markup=False,
        highlight=False,
    )
    return 0


def _authenticate(
    *,
    gateway_factory: Callable[..., object] = TelethonGateway,
    phone_prompt: Callable[[], str] = _phone_prompt,
    code_prompt: Callable[[], str] | None = None,
    password_prompt: Callable[[], str] | None = None,
) -> int:
    injected_prompts = code_prompt is not None and password_prompt is not None
    if code_prompt is None or password_prompt is None:
        code_prompt = code_prompt or (lambda: _secret_prompt("Code: "))
        password_prompt = password_prompt or (
            lambda: _secret_prompt("2FA password: ")
        )
    application = AuthenticationApplication(
        gateway_factory=gateway_factory,
        credentials=load_telegram_credentials,
        phone_prompt=phone_prompt,
        code_prompt=code_prompt,
        password_prompt=password_prompt,
        interactive_check=None if injected_prompts else _require_interactive,
    )
    outcome = asyncio.run(application.authenticate())
    if outcome.state.name != "AUTHENTICATED":
        raise AuthenticationError from None
    Console(file=sys.stdout, force_terminal=False, no_color=True).print(
        "authentication successful", markup=False, highlight=False
    )
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    gateway_factory: Callable[..., object] = TelethonGateway,
    discovery_gateway_factory: Callable[[TelegramCredentials], object] | None = None,
    scan_gateway_factory: Callable[[TelegramCredentials], object] | None = None,
    phone_prompt: Callable[[], str] = _phone_prompt,
    code_prompt: Callable[[], str] | None = None,
    password_prompt: Callable[[], str] | None = None,
    selection_prompt: Callable[[str], str] = input,
    api_id_prompt: Callable[[], str] = lambda: input("Telegram API ID: "),
    api_hash_prompt: Callable[[], str] = lambda: _secret_prompt("Telegram API HASH: "),
    credential_vault_factory: Callable[[], CredentialVault] = CredentialVault,
    credentials_loader: Callable[[], TelegramCredentials] = load_telegram_credentials,
    download_gateway_factory: Callable[[TelegramCredentials], object] | None = None,
) -> int:
    try:
        args = _parse_arguments(argv)
        configuration = load_configuration(
            config_path=args.config,
            log_level=args.log_level,
            workers=args.cli_workers,
            attempts_per_media=args.cli_attempts_per_media,
            download_dir=args.cli_download_dir,
            database_path=args.cli_database_path,
        )
        args.workers = configuration.workers
        args.attempts_per_media = configuration.attempts_per_media
        args.download_dir = configuration.download_dir
        args.database = configuration.database_path
        configure_operational_logging(configuration.log_level)
        if args.command == "credentials":
            if args.credentials_action == "setup":
                return _credentials_setup(
                    api_id_prompt=api_id_prompt,
                    api_hash_prompt=api_hash_prompt,
                    vault_factory=credential_vault_factory,
                )
            return _credentials_status(vault_factory=credential_vault_factory)
        if args.command == "catalog":
            return _catalog_command(args, selection_prompt)
        if args.command == "auth":
            return _authenticate(
                gateway_factory=gateway_factory,
                phone_prompt=phone_prompt,
                code_prompt=code_prompt,
                password_prompt=password_prompt,
            )
        if args.command == "channels":
            return _discover_channels(
                gateway_factory=(
                    discovery_gateway_factory or _discovery_gateway
                ),
                selection_prompt=selection_prompt,
            )
        if args.command == "scan":
            return _scan_channel(
                channel_id=args.channel_id,
                max_messages=args.max_messages,
                timeout_seconds=args.timeout_seconds,
                database=args.database,
                gateway_factory=scan_gateway_factory or _scan_gateway,
                credentials_loader=credentials_loader,
                incremental=args.incremental,
                reconcile_window=args.reconcile_window or 0,
            )
        if args.command == "download":
            if args.credentials_action in {"plan", "queue"}:
                return _download_batch(
                    args=args,
                    selection_prompt=selection_prompt,
                    gateway_factory=download_gateway_factory or gateway_factory,
                    credentials_loader=credentials_loader,
                )
            return _download_single(
                channel_id=args.channel_id, message_id=args.telegram_message_id,
                media_ordinal=args.media_ordinal, database=args.database,
                download_dir=args.download_dir,
                integrity_mode=args.integrity_mode,
                reference_manifest_path=args.reference_manifest,
                gateway_factory=download_gateway_factory or gateway_factory,
                credentials_loader=credentials_loader,
            )
        line = (
            f"telegram-courses {__version__} config={configuration.config} "
            f"log_level={configuration.log_level}"
        )
        Console(
            file=sys.stdout,
            force_terminal=False,
            no_color=True,
            color_system=None,
            width=120,
        ).print(line, markup=False, highlight=False, soft_wrap=True)
        return 0
    except ConfigurationError:
        configure_operational_logging("INFO")
        emit_operational_event(
            "configuration.rejected",
            component="cli.config",
            level=30,
            category="CONFIGURATION",
            status="FAILED",
        )
        sys.stderr.write("configuration error\n")
        return 2
    except CredentialVaultError:
        sys.stderr.write("credentials vault error\n")
        return 2
    except AuthenticationError as error:
        emit_operational_event(
            "operation.failed", component="cli.auth", level=40,
            category="AUTHENTICATION", status="FAILED",
        )
        sys.stderr.write(f"{error}\n")
        return 3
    except ChannelDiscoveryError as error:
        category = getattr(error, "category", "ACCESS")
        if not isinstance(category, str):
            category = getattr(category, "value", "ACCESS")
        emit_operational_event(
            "operation.failed", component="cli.discovery", level=40,
            category=category, status="FAILED",
        )
        sys.stderr.write(f"{error}\n")
        return 3
    except TimeoutError:
        emit_operational_event(
            "operation.failed", component="cli.scan", level=40,
            category="TIMEOUT", status="FAILED",
        )
        sys.stderr.write("scan timeout\n")
        return 4
    except ScanGatewayError as error:
        emit_operational_event(
            "operation.failed", component="cli.scan", level=40,
            category=error.category, status="FAILED",
        )
        sys.stderr.write(f"scan failed category={error.category}\n")
        return 4
    except CatalogError as error:
        emit_operational_event(
            "operation.failed", component="cli.catalog", level=40,
            category=error.category, status="FAILED",
        )
        sys.stderr.write(f"catalog failed category={error.category}\n")
        return 4
    except DownloadError as error:
        status = (
            "BLOCKED"
            if error.category in {"INSUFFICIENT_DISK_SPACE", "TRANSFER_BUDGET_EXHAUSTED"}
            else "FAILED"
        )
        emit_operational_event(
            "operation.failed", component="cli.download", level=40,
            category=error.category, status=status,
        )
        sys.stderr.write(f"download failed category={error.category}\n")
        return 4
    except KeyboardInterrupt:
        emit_operational_event(
            "operation.cancelled", component="cli", level=30,
            status="CANCELLED",
        )
        sys.stderr.write("operation cancelled\n")
        return 130
    except Exception:
        # Configuration may have failed before the logger was initialized;
        # do not reuse an earlier invocation's possibly closed stderr.
        configure_operational_logging("INFO")
        emit_operational_event(
            "operation.failed", component="cli", level=40,
            category="INTERNAL", status="FAILED",
        )
        sys.stderr.write("internal error\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
