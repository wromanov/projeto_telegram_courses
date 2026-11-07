"""Rich presentation for offline catalog browsing and course media selection."""

from __future__ import annotations

import asyncio
import re
import sqlite3
import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

from telegram_courses.catalog import CatalogError
from telegram_courses.catalog_repository import (
    InteractiveCatalogSnapshot,
    SQLiteCatalogRepository,
)
from telegram_courses.catalog_selection import (
    CourseMediaOption,
    MediaIdentity,
    SelectionInputError,
    apply_selection_command,
    course_hierarchy,
    course_media_options,
    make_course_selection,
    parse_selection_command,
    selectable_courses,
)
from telegram_courses.course_download_planning import (
    CoursePlanReview,
    ObservedExclusion,
    course_download_selection,
    create_course_plan_review,
)
from telegram_courses.course_execution import ConfirmedCoursePlan
from telegram_courses.course_review_context import (
    load_course_review_context,
)
from telegram_courses.course_review_context import (
    order_is_ambiguous as _order_is_ambiguous,
)
from telegram_courses.downloads import DownloadError
from telegram_courses.s5_downloads import DownloadPlanner, DownloadSelection

MEDIA_PAGE_SIZE = 20


def _safe_text(value: str | None, fallback: str = "(sem título)") -> str:
    raw = value if value else fallback
    return "".join(
        " " if character in "\r\n\t" else character
        for character in raw
        if unicodedata.category(character) not in {"Cc", "Cf", "Cs"}
    )


def _add_plain_row(table: Table, *cells: str) -> None:
    """Render catalog data as literal text, never as Rich markup."""
    table.add_row(*(Text(cell) for cell in cells))


def _select_number(text: str, count: int) -> int | None:
    value = text.strip()
    if value.casefold() == "q":
        return None
    if len(value) > 32 or re.fullmatch(r"[0-9]+", value) is None:
        raise SelectionInputError("informe um número da lista ou Q para voltar")
    index = int(value)
    if not 1 <= index <= count:
        raise SelectionInputError("número fora da lista")
    return index - 1


def _node_depth(node_id: int, by_id: dict[int, object]) -> int:
    depth = 0
    current = by_id[node_id]
    seen: set[int] = set()
    while current.parent_id is not None and current.parent_id in by_id:
        if current.parent_id in seen:
            return depth
        seen.add(current.parent_id)
        depth += 1
        current = by_id[current.parent_id]
    return depth




def _render_catalog(snapshot: InteractiveCatalogSnapshot, console: Console) -> None:
    status = (
        "varredura completa observada; completude do curso não comprovada"
        if snapshot.catalog_complete
        else "catálogo parcial ou estado de varredura desconhecido"
    )
    if snapshot.scan_stop_reason:
        status += f" ({_safe_text(snapshot.scan_stop_reason)})"
    console.print(f"Canal: {_safe_text(snapshot.channel.title)}", markup=False)
    console.print(f"Catálogo: {status}", markup=False)
    console.print(
        f"Build do catálogo: {_safe_text(snapshot.catalog_finished_at, 'desconhecido')} | "
        f"varredura: {_safe_text(snapshot.scan_finished_at, 'desconhecida')}",
        markup=False,
    )
    unassociated = tuple(
        media for media in snapshot.media
        if media.catalog_node_id is None
        or media.catalog_kind in {None, "unclassified"}
    )
    if unassociated:
        console.print(
            "Mídias observadas sem associação classificável a curso neste canal:",
            markup=False,
        )
        unassociated_table = Table("ID local", "Arquivo observado", "Tipo", "Tamanho", "Associação")
        for media in unassociated:
            association = (
                "sem nó associado" if media.catalog_node_id is None
                else "nó ausente no catálogo" if media.catalog_kind is None
                else "nó não classificado"
            )
            _add_plain_row(unassociated_table,
                f"{media.telegram_message_id}:{media.media_ordinal + 1}",
                _safe_text(media.original_filename, "(nome indisponível)"),
                _safe_text(media.kind), _format_size(media.file_size_bytes), association,
            )
        console.print(unassociated_table)
    courses = selectable_courses(snapshot)
    if not courses:
        console.print("Nenhum curso ativo e válido neste catálogo.", markup=False)
        return
    course_ordinals = [course.ordinal for course in courses]
    if (
        any(ordinal is None for ordinal in course_ordinals)
        or len(set(course_ordinals)) != len(course_ordinals)
    ):
        console.print(
            "Aviso: há ordinais de curso ausentes ou repetidos; desempate determinístico pela identidade local.",
            markup=False,
        )
    table = Table("#", "Curso", "Código", "ID local", "Ordem")
    for index, course in enumerate(courses, start=1):
        _add_plain_row(table,
            str(index), _safe_text(course.title), _safe_text(course.code, "—"),
            str(course.node_id),
            str(course.ordinal if course.ordinal is not None else "desconhecida"),
        )
    console.print(table)


def _format_size(value: int | None) -> str:
    return "desconhecido" if value is None else f"{value:,} bytes"


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "não verificável"
    return f"{value:,} bytes ({value / 1024**3:.2f} GiB)"


def _render_course(
    snapshot: InteractiveCatalogSnapshot,
    course: object,
    options: tuple[CourseMediaOption, ...],
    selected: frozenset[MediaIdentity],
    console: Console,
    *,
    page: int = 0,
) -> None:
    hierarchy = course_hierarchy(snapshot, course.node_id)
    ambiguous = _order_is_ambiguous(hierarchy, course.node_id, snapshot)
    console.print(f"Curso: {_safe_text(course.title)}", markup=False)
    console.print(
        "Ordem determinística do catálogo; sequência pedagógica não comprovada."
        if ambiguous else
        "Ordem determinística do catálogo; sequência pedagógica não presumida.",
        markup=False,
    )
    if ambiguous:
        console.print(
            "Aviso: há ordinal ausente ou repetido; o desempate exibido usa a identidade local.",
            markup=False,
        )
    if not snapshot.catalog_complete:
        console.print(
            "Catálogo parcial: esta tela cobre somente conteúdo observado; não indica completude remota.",
            markup=False,
        )
    by_id = {node.node_id: node for node in snapshot.nodes}
    tree = Table("Hierarquia observada", "Ativo", "Ordem")
    for node in hierarchy:
        _add_plain_row(tree,
            "  " * max(0, _node_depth(node.node_id, by_id) - _node_depth(course.node_id, by_id) - 1)
            + f"{node.kind}: {_safe_text(node.title)}",
            "sim" if node.is_active else "não",
            str(node.ordinal if node.ordinal is not None else "desconhecida"),
        )
    if hierarchy:
        console.print(tree)
    total_pages = max(1, (len(options) + MEDIA_PAGE_SIZE - 1) // MEDIA_PAGE_SIZE)
    page = min(max(page, 0), total_pages - 1)
    start = page * MEDIA_PAGE_SIZE
    end = min(start + MEDIA_PAGE_SIZE, len(options))
    table = Table("#", "Módulo / aula", "Arquivo observado", "Tamanho", "Estado")
    for index, item in enumerate(options[start:end], start=start + 1):
        state = (
            "marcado" if item.identity in selected else "selecionável"
        ) if item.selectable else f"bloqueado: {item.reason or 'não selecionável'}"
        _add_plain_row(table,
            str(index),
            f"{_safe_text(item.module_title, '—')} / {_safe_text(item.lesson_title, '—')}",
            f"{_safe_text(item.original_filename, f'mídia {item.identity.media_ordinal + 1}')} "
            f"({_safe_text(item.kind)})",
            _format_size(item.file_size_bytes), state,
        )
    if options:
        console.print(table, markup=False)
        console.print(
            f"Página {page + 1} de {total_pages} | opções numeradas globalmente: 1–{len(options)}",
            markup=False,
        )
    unknown_sizes = tuple(
        (index, item) for index, item in enumerate(options[start:end], start=start + 1)
        if item.file_size_bytes is None
    )
    if unknown_sizes:
        unknown_labels = "; ".join(
            f"{index}: {_safe_text(item.original_filename, 'mídia sem nome')} "
            f"({item.identity.telegram_message_id}:{item.identity.media_ordinal + 1})"
            for index, item in unknown_sizes
        )
        console.print(
            f"Tamanho desconhecido; itens permanecem visíveis: {unknown_labels}.",
            markup=False,
        )
    console.print("Tamanho desconhecido não remove o item da seleção.", markup=False)
    invalid = sum(1 for item in options if not item.selectable)
    unknown_total = sum(1 for item in options if item.file_size_bytes is None)
    console.print(
        f"Arquivos observados neste curso: {len(options)} | marcados: {len(selected)} | "
        f"associação não selecionável: {invalid} | tamanhos desconhecidos: {unknown_total}",
        markup=False,
    )
    console.print(
        "Comandos: números/listas/intervalos selecionam; R remove; T marca itens "
        "selecionáveis; P prepara os marcados; B planeja todos os itens catalogados "
        "do curso; A/N navegam páginas; L limpa; V revisa; Q volta.",
        markup=False,
    )


def _render_course_plan(
    snapshot: InteractiveCatalogSnapshot,
    course: object,
    options: tuple[CourseMediaOption, ...],
    review: CoursePlanReview,
    *,
    ambiguous_order: bool,
    console: Console,
) -> None:
    plan = review.plan
    console.print("TELEGRAM COURSES — PLANO DE DOWNLOAD", markup=False)
    console.print(f"Canal: {_safe_text(snapshot.channel.title)}", markup=False)
    console.print(f"Curso: {_safe_text(course.title)}", markup=False)
    console.print(
        "Modo: arquivos selecionados" if review.selection_mode == "SELECTED"
        else "Modo: todos os arquivos observados com associação válida a aula neste curso",
        markup=False,
    )
    console.print(
        "Catálogo completo apenas no escopo da varredura observada; isso não prova completude remota."
        if plan.catalog_complete
        else "Catálogo parcial ou estado de varredura desconhecido; somente conteúdo observado entra nesta prévia.",
        markup=False,
    )
    console.print(
        "Ordem S5 determinística; ordem pedagógica não presumida."
        if not ambiguous_order
        else "Aviso: ordem S5 determinística, mas ordinais ausentes/repetidos impedem inferir sequência pedagógica.",
        markup=False,
    )
    conditional = sum(
        item.status == "CONDITIONAL_RESUME_CANDIDATE" for item in plan.pending
    )
    completed_v2 = len(plan.completed_v2)
    console.print(f"Estado da prévia: {review.result_status}", markup=False)
    console.print(
        f"Selecionados/considerados: {review.selected_count} | elegíveis com candidato: {len(plan.eligible)} | "
        f"pendentes: {len(plan.pending)} | já válidos: {len(plan.already_valid)} | "
        f"retomada condicional: {conditional} | concluídos V2: {completed_v2} | "
        f"bloqueados: {len(plan.blocked)} | "
        f"excluídos no plano: {len(plan.excluded)} | fora do plano por associação: "
        f"{len(review.observed_exclusions)} | tamanho desconhecido: {review.unknown_size_count}",
        markup=False,
    )
    console.print(
        f"Tamanho conhecido observado: {_format_bytes(review.known_size_bytes)} | "
        f"transferência estimada pendente: {_format_bytes(plan.pending_bytes)} | "
        f"espaço adicional estimado: {_format_bytes(plan.additional_disk_bytes)} | "
        f"margem S5: {_format_bytes(plan.safety_margin)} | "
        f"tamanho conhecido fora do plano: {_format_bytes(review.observed_exclusion_known_size_bytes)}",
        markup=False,
    )
    console.print(f"Destino: {_safe_text(review.download_root)}", markup=False)
    console.print(
        f"Espaço disponível: {_format_bytes(review.available_disk_bytes)} "
        f"(checagem: {review.disk_limit_result})",
        markup=False,
    )
    item_cap = "sem limite" if review.max_media_items is None else str(review.max_media_items)
    byte_cap = "sem limite" if review.max_transfer_bytes is None else _format_bytes(review.max_transfer_bytes)
    console.print(
        f"Limites: itens={item_cap} ({review.item_limit_result}); "
        f"bytes pendentes={byte_cap} ({review.byte_limit_result}); resultado={review.limit_result}",
        markup=False,
    )
    if (
        review.max_transfer_bytes is not None
        and review.telegram_reservation_floor_bytes > review.max_transfer_bytes
    ):
        console.print(
            "Atenção: o gateway Telegram reserva pedidos alinhados a 1 KiB. "
            "O teto aprovado pode bloquear a fila antes do fim; reserva mínima "
            "estimada para uma passagem sequencial sem repetição ou prova: "
            f"{_format_bytes(review.telegram_reservation_floor_bytes)}. "
            "O limite não foi aumentado; provas e tentativas podem exigir mais.",
            markup=False,
        )
    console.print(
        f"Integridade prevista: {review.integrity_mode} | workers: 1 | tentativas por mídia: 3",
        markup=False,
    )

    options_by_identity = {item.identity: item for item in options}
    destinations_by_identity = {item.identity: item for item in review.destinations}
    pending_order = {item.identity: index for index, item in enumerate(plan.pending, start=1)}
    console.print(
        "Sequência do plano; a coluna Fila mostra a subsequência que uma fila futura avaliaria.",
        markup=False,
    )
    for index, item in enumerate(plan.items, start=1):
        option = options_by_identity.get(MediaIdentity(*item.identity))
        candidate = item.candidate
        filename = (
            candidate.original_filename if candidate and candidate.original_filename
            else option.original_filename if option and option.original_filename
            else "(nome indisponível)"
        )
        hierarchy = (
            f"{option.module_title or '—'} / {option.lesson_title or '—'}"
            if option else "associação fora da lista selecionável"
        )
        size = candidate.expected_bytes if candidate else item.observed_size_bytes
        destination = destinations_by_identity.get(item.identity)
        final_path = destination.final_path if destination else None
        state = item.status
        if item.reason == "UNKNOWN_SIZE":
            state = "EXCLUDED / UNKNOWN_SIZE"
        console.print(
            f"{index:02d} | fila={pending_order.get(item.identity, '—')} | "
            f"id={item.identity[0]}:{item.identity[1]}:{item.identity[2]} | "
            f"{state} | tamanho={_format_size(size)} | motivo={_safe_text(item.reason, '—')}",
            markup=False,
        )
        console.print(
            f"   {_safe_text(hierarchy)} | {_safe_text(filename)} | "
            f"destino={_safe_text(final_path, '—')}",
            markup=False,
        )
    if review.block_reasons:
        console.print(
            "Bloqueios: " + ", ".join(_safe_text(reason) for reason in review.block_reasons),
            markup=False,
        )
    if review.unknown_size_count:
        console.print(
            "Tamanhos desconhecidos aparecem como exclusões ou observações fora do plano; "
            "não foram convertidos em zero nem omitidos.",
            markup=False,
        )
    if review.observed_exclusions:
        console.print("Observados fora do plano por associação não selecionável:", markup=False)
        for item in review.observed_exclusions:
            console.print(
                f"id={item.identity[0]}:{item.identity[1]}:{item.identity[2]} | "
                f"{_safe_text(item.filename, '(nome indisponível)')} | "
                f"tamanho={_format_size(item.size_bytes)} | motivo={_safe_text(item.reason)}",
                markup=False,
            )
    console.print("Esta prévia não chama fila, sessão Telegram nem download.", markup=False)


def _load_course_review_context(
    planner: DownloadPlanner, *, channel_id: int, course_id: int,
    selection_mode: str, exact_selection: DownloadSelection | None,
):
    return asyncio.run(load_course_review_context(
        planner, channel_id=channel_id, course_id=course_id,
        selection_mode=selection_mode, exact_selection=exact_selection,
    ))


def _render_no_eligible_course_items(
    exclusions: tuple[ObservedExclusion, ...], console: Console,
) -> None:
    console.print(
        "SEM_ELEGIVEIS: não há arquivos com associação válida a aula neste curso.",
        markup=False,
    )
    for item in exclusions:
        console.print(
            f"id={item.identity[0]}:{item.identity[1]}:{item.identity[2]} | "
            f"{_safe_text(item.filename, '(nome indisponível)')} | "
            f"tamanho={_format_size(item.size_bytes)} | motivo={_safe_text(item.reason)}",
            markup=False,
        )


def _prompt_transfer_cap(
    selection_prompt: Callable[[str], str], console: Console, label: str,
) -> int | None:
    while True:
        try:
            answer = selection_prompt(f"Limite de {label} para esta execução (inteiro positivo, Q cancela): ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if answer.casefold() == "q":
            return None
        if answer.isdecimal() and 0 < int(answer) <= 2**63 - 1:
            return int(answer)
        console.print("Informe um inteiro positivo válido ou Q para cancelar.", markup=False)


def _review_and_confirm_course_plan(
    *,
    planner: DownloadPlanner,
    selection: DownloadSelection | None,
    selection_mode: str,
    snapshot: InteractiveCatalogSnapshot,
    course: object,
    download_root: str | Path,
    max_media_items: int | None,
    max_transfer_bytes: int | None,
    require_transfer_caps: bool = False,
    selection_prompt: Callable[[str], str],
    console: Console,
) -> ConfirmedCoursePlan | None:
    for attempt in range(3):
        try:
            (
                current_snapshot, current_course, current_options,
                current_ambiguous_order, current_selection,
                observed_exclusions, catalog_context,
            ) = _load_course_review_context(
                planner,
                channel_id=snapshot.channel.channel_id,
                course_id=course.node_id,
                selection_mode=selection_mode,
                exact_selection=selection,
            )
            if current_selection is None:
                _render_no_eligible_course_items(observed_exclusions, console)
                return
            plan = asyncio.run(planner.build(current_selection))
            if require_transfer_caps and plan.pending:
                if max_media_items is None:
                    max_media_items = _prompt_transfer_cap(
                        selection_prompt, console, "arquivos",
                    )
                    if max_media_items is None:
                        console.print("Plano cancelado sem limite de arquivos.", markup=False)
                        return
                if max_transfer_bytes is None:
                    max_transfer_bytes = _prompt_transfer_cap(
                        selection_prompt, console, "bytes transferidos",
                    )
                    if max_transfer_bytes is None:
                        console.print("Plano cancelado sem limite de bytes.", markup=False)
                        return
            plan_ids = {item.identity for item in plan.items}
            review = create_course_plan_review(
                plan,
                selection_mode=selection_mode,
                download_root=download_root,
                max_media_items=max_media_items,
                max_transfer_bytes=max_transfer_bytes,
                observed_exclusions=tuple(
                    item for item in observed_exclusions
                    if item.identity not in plan_ids
                ),
                catalog_context=catalog_context,
            )
        except DownloadError as error:
            console.print(f"Plano indisponível: {error.category}.", markup=False)
            return
        except CatalogError as error:
            console.print(f"Plano indisponível: {error.category}.", markup=False)
            return
        except sqlite3.Error:
            console.print("Plano indisponível: CATALOG_SCHEMA_OR_DATABASE_ERROR.", markup=False)
            return

        _render_course_plan(
            current_snapshot, current_course, current_options, review,
            ambiguous_order=current_ambiguous_order, console=console,
        )
        if not review.can_confirm:
            console.print(
                "Este plano não pode ser confirmado nas condições atuais; ajuste seleção ou limites.",
                markup=False,
            )
            return
        try:
            answer = selection_prompt("Confirmar esta revisão [s/N]? ")
        except (EOFError, KeyboardInterrupt):
            console.print("Revisão cancelada; nenhum download foi iniciado.", markup=False)
            return
        if answer.strip().casefold() not in {"s", "sim", "y", "yes"}:
            console.print("Plano não confirmado; nenhum download foi iniciado.", markup=False)
            return

        try:
            (
                _fresh_snapshot, _fresh_course, _fresh_options,
                _fresh_ambiguous_order, fresh_selection,
                fresh_observed_exclusions, fresh_catalog_context,
            ) = _load_course_review_context(
                planner,
                channel_id=snapshot.channel.channel_id,
                course_id=course.node_id,
                selection_mode=selection_mode,
                exact_selection=selection,
            )
            if fresh_selection is None:
                console.print(
                    "A confirmação foi descartada: SEM_ELEGIVEIS após a revalidação.",
                    markup=False,
                )
                _render_no_eligible_course_items(fresh_observed_exclusions, console)
                return
            fresh_plan = asyncio.run(planner.build(fresh_selection))
            fresh_plan_ids = {item.identity for item in fresh_plan.items}
            fresh_review = create_course_plan_review(
                fresh_plan,
                selection_mode=selection_mode,
                download_root=download_root,
                max_media_items=max_media_items,
                max_transfer_bytes=max_transfer_bytes,
                observed_exclusions=tuple(
                    item for item in fresh_observed_exclusions
                    if item.identity not in fresh_plan_ids
                ),
                catalog_context=fresh_catalog_context,
            )
        except (DownloadError, CatalogError, sqlite3.Error):
            console.print(
                "A confirmação foi descartada: não foi possível revalidar o plano fresco.",
                markup=False,
            )
            return
        if review.matches_after_confirmation(fresh_review):
            console.print(
                "Plano validado. Transferência real exige uma autorização separada.",
                markup=False,
            )
            return ConfirmedCoursePlan(Path(planner.database).absolute(), fresh_review)
        console.print(
            "O plano ou as condições mudaram após a revisão. A confirmação anterior foi descartada.",
            markup=False,
        )
    console.print(
        "Revalidação mudou repetidamente; revisão bloqueada. Nenhum download foi iniciado.",
        markup=False,
    )


def _run_authorized_offline_fixture(
    confirmation: ConfirmedCoursePlan | None,
    sandbox: object | None,
    selection_prompt: Callable[[str], str],
    console: Console,
) -> None:
    """Test-only dependency injection; there is no corresponding CLI option."""
    if confirmation is None or sandbox is None:
        return
    from telegram_courses.course_offline_execution import OfflineCourseSandbox
    from telegram_courses.course_progress_rich import run_offline_with_rich

    if type(sandbox) is not OfflineCourseSandbox:
        raise DownloadError("OFFLINE_SANDBOX_INVALID")
    try:
        answer = selection_prompt("Autorizar execução sintética offline [s/N]? ")
    except (EOFError, KeyboardInterrupt):
        console.print("Execução sintética cancelada antes do início.", markup=False)
        return
    if answer.strip().casefold() not in {"s", "sim", "y", "yes"}:
        console.print("Execução sintética não autorizada.", markup=False)
        return
    try:
        authorization = sandbox.authorize(confirmation)
        asyncio.run(run_offline_with_rich(sandbox, authorization, console))
    except DownloadError as error:
        console.print(f"Execução sintética bloqueada: {error.category}.", markup=False)


def _render_selection(
    snapshot: InteractiveCatalogSnapshot, course: object,
    options: tuple[CourseMediaOption, ...],
    selected: frozenset[MediaIdentity], console: Console, *, channel_id: int,
) -> None:
    selection = make_course_selection(
        options, selected, channel_id=channel_id,
        course_id=course.node_id,
    )
    chosen = [item for item in options if item.identity in selected]
    console.print(f"Revisão — {_safe_text(course.title)}", markup=False)
    ambiguous = _order_is_ambiguous(
        course_hierarchy(snapshot, course.node_id), course.node_id, snapshot,
    )
    console.print(
        "Sequência da revisão: ordem determinística do catálogo; sequência pedagógica não confirmada.",
        markup=False,
    )
    if ambiguous:
        console.print(
            "Aviso: ordinais ausentes ou repetidos; desempate determinístico pela identidade local.",
            markup=False,
        )
    table = Table("#", "Identidade local", "Módulo / aula", "Arquivo", "Tamanho")
    for index, item in enumerate(chosen, start=1):
        _add_plain_row(table,
            str(index),
            f"{item.identity.channel_id}:{item.identity.telegram_message_id}:"
            f"{item.identity.media_ordinal}",
            f"{_safe_text(item.module_title, '—')} / {_safe_text(item.lesson_title, '—')}",
            f"{_safe_text(item.original_filename, f'mídia {item.identity.media_ordinal + 1}')} "
            f"({_safe_text(item.kind)})",
            _format_size(item.file_size_bytes),
        )
    console.print(table if chosen else "Nenhum arquivo marcado.")
    known_bytes = sum(item.file_size_bytes for item in chosen if item.file_size_bytes is not None)
    unknown_sizes = sum(item.file_size_bytes is None for item in chosen)
    console.print(
        f"Marcados: {len(selection.identities)} | Tamanho conhecido: {known_bytes:,} bytes | "
        f"Sem tamanho: {unknown_sizes}",
        markup=False,
    )
    console.print("Esta revisão não inicia downloads.", markup=False)


def run_interactive_catalog(
    database: str | Path,
    *,
    download_root: str | Path = "downloads",
    max_media_items: int | None = None,
    max_transfer_bytes: int | None = None,
    selection_prompt: Callable[[str], str] = input,
    require_tty: bool = True,
    offline_sandbox: object | None = None,
    live_executor: Callable[[ConfirmedCoursePlan], object] | None = None,
) -> int:
    if offline_sandbox is not None:
        from telegram_courses.course_offline_execution import OfflineCourseSandbox

        if (
            type(offline_sandbox) is not OfflineCourseSandbox
            or Path(database).resolve() != offline_sandbox.database
            or Path(download_root).resolve() != offline_sandbox.download_root
        ):
            raise DownloadError("OFFLINE_SANDBOX_INVALID")
    if require_tty and not sys.stdin.isatty():
        Console(file=sys.stderr, no_color=True).print(
            "A navegação interativa requer um terminal (TTY).", markup=False
        )
        return 2
    console = Console(file=sys.stdout, no_color=not sys.stdout.isatty())
    execution_status = 0
    repository = SQLiteCatalogRepository(database)
    try:
        channels = asyncio.run(repository.list_interactive_channels())
        if not channels:
            console.print("Nenhum canal catalogado neste banco.", markup=False)
            return 0
        while True:
            table = Table("#", "Canal", "Canal ID", "Parser", "Build", "Nós ativos")
            for index, channel in enumerate(channels, start=1):
                _add_plain_row(table,
                    str(index), _safe_text(channel.title), str(channel.channel_id),
                    _safe_text(channel.parser_key, "—"),
                    _safe_text(channel.catalog_status, "sem build"),
                    str(channel.active_node_count),
                )
            console.print("Canais no catálogo local", markup=False)
            console.print(table)
            try:
                channel_index = _select_number(
                    selection_prompt("Canal ou Q para sair: "), len(channels)
                )
            except SelectionInputError as error:
                console.print(str(error), markup=False)
                continue
            if channel_index is None:
                return execution_status
            snapshot = asyncio.run(
                repository.load_interactive_snapshot(channels[channel_index].channel_id)
            )
            while True:
                _render_catalog(snapshot, console)
                courses = selectable_courses(snapshot)
                if not courses:
                    break
                try:
                    course_index = _select_number(
                        selection_prompt("Curso ou Q para voltar aos canais: "), len(courses)
                    )
                except SelectionInputError as error:
                    console.print(str(error), markup=False)
                    continue
                if course_index is None:
                    break
                course = courses[course_index]
                options = course_media_options(snapshot, course.node_id)
                selected: frozenset[MediaIdentity] = frozenset()
                page = 0
                while True:
                    _render_course(snapshot, course, options, selected, console, page=page)
                    try:
                        command_text = selection_prompt("Seleção: ")
                        command = parse_selection_command(command_text, len(options))
                        if command.action == "back":
                            break
                        if command.action == "review":
                            _render_selection(
                                snapshot, course, options, selected, console,
                                channel_id=snapshot.channel.channel_id,
                            )
                            continue
                        if command.action == "remove_mode":
                            remove_text = selection_prompt("Itens para desmarcar: ")
                            remove_command = parse_selection_command(remove_text, len(options))
                            if remove_command.action != "indices":
                                raise SelectionInputError("informe os números dos itens para desmarcar")
                            selected = apply_selection_command(
                                options, selected, remove_command, removing=True
                            )
                            continue
                        total_pages = max(1, (len(options) + MEDIA_PAGE_SIZE - 1) // MEDIA_PAGE_SIZE)
                        if command.action == "previous_page":
                            page = max(0, page - 1)
                            continue
                        if command.action == "next_page":
                            page = min(total_pages - 1, page + 1)
                            continue
                        planner = DownloadPlanner(database, download_root)
                        if command.action == "prepare":
                            course_selection = make_course_selection(
                                options,
                                selected,
                                channel_id=snapshot.channel.channel_id,
                                course_id=course.node_id,
                            )
                            if not course_selection.identities:
                                console.print(
                                    "SEM_SELECAO: marque ao menos um arquivo; nenhum plano foi criado.",
                                    markup=False,
                                )
                                continue
                            planner_selection = course_download_selection(
                                course_selection.channel_id,
                                course_selection.course_id,
                                media_identities=tuple(
                                    (item.channel_id, item.telegram_message_id, item.media_ordinal)
                                    for item in course_selection.identities
                                ),
                            )
                            confirmation = _review_and_confirm_course_plan(
                                planner=planner,
                                selection=planner_selection,
                                selection_mode="SELECTED",
                                snapshot=snapshot,
                                course=course,
                                download_root=download_root,
                                max_media_items=max_media_items,
                                max_transfer_bytes=max_transfer_bytes,
                                require_transfer_caps=live_executor is not None,
                                selection_prompt=selection_prompt,
                                console=console,
                            )
                            _run_authorized_offline_fixture(
                                confirmation, offline_sandbox, selection_prompt, console,
                            )
                            if offline_sandbox is None and confirmation is not None and live_executor is not None:
                                result = live_executor(confirmation)
                                if type(result) is int and result != 0:
                                    execution_status = result
                            continue
                        if command.action == "all_course":
                            confirmation = _review_and_confirm_course_plan(
                                planner=planner,
                                selection=None,
                                selection_mode="ALL_CATALOGED",
                                snapshot=snapshot,
                                course=course,
                                download_root=download_root,
                                max_media_items=max_media_items,
                                max_transfer_bytes=max_transfer_bytes,
                                require_transfer_caps=live_executor is not None,
                                selection_prompt=selection_prompt,
                                console=console,
                            )
                            _run_authorized_offline_fixture(
                                confirmation, offline_sandbox, selection_prompt, console,
                            )
                            if offline_sandbox is None and confirmation is not None and live_executor is not None:
                                result = live_executor(confirmation)
                                if type(result) is int and result != 0:
                                    execution_status = result
                            continue
                        selected = apply_selection_command(options, selected, command)
                    except (SelectionInputError, EOFError) as error:
                        if isinstance(error, EOFError):
                            return 0
                        console.print(str(error), markup=False)
                    except KeyboardInterrupt:
                        return 130
    except CatalogError as error:
        console.print(f"Catálogo indisponível: {error}", file=sys.stderr, markup=False)
        return 4
    except EOFError:
        return 0
    except KeyboardInterrupt:
        return 130


def run_interactive_program(
    database: str | Path,
    *,
    download_root: str | Path,
    max_media_items: int | None,
    max_transfer_bytes: int | None,
    selection_prompt: Callable[[str], str] = input,
    require_tty: bool = True,
    live_executor: Callable[[ConfirmedCoursePlan], object] | None = None,
    discover_and_catalog: Callable[[str | Path, Callable[[str], str]], int] | None = None,
) -> int:
    """Public terminal menu for local browsing and bounded catalog creation."""
    if require_tty and not sys.stdin.isatty():
        Console(file=sys.stderr, no_color=True).print(
            "A navegação interativa requer um terminal (TTY).", markup=False,
        )
        return 2
    console = Console(file=sys.stdout, no_color=not sys.stdout.isatty())
    exit_status = 0
    while True:
        console.print("TELEGRAM COURSES", markup=False)
        console.print("[1] Abrir catálogo local", markup=False)
        console.print("[2] Descobrir canais e construir catálogo", markup=False)
        console.print("[Q] Sair", markup=False)
        try:
            action = selection_prompt("Opção: ").strip().casefold()
        except (EOFError, KeyboardInterrupt):
            return exit_status
        if action == "q":
            return exit_status
        if action == "1":
            result = run_interactive_catalog(
                database,
                download_root=download_root,
                max_media_items=max_media_items,
                max_transfer_bytes=max_transfer_bytes,
                selection_prompt=selection_prompt,
                require_tty=False,
                live_executor=live_executor,
            )
            if result != 0:
                exit_status = result
            continue
        if action == "2":
            if discover_and_catalog is None:
                console.print("Descoberta não disponível nesta configuração.", markup=False)
            else:
                result = discover_and_catalog(database, selection_prompt)
                if result != 0:
                    exit_status = result
            continue
        console.print("Escolha 1, 2 ou Q.", markup=False)
