"""Rich-only presentation for synthetic course execution."""

from __future__ import annotations

import asyncio
import unicodedata
from dataclasses import replace

from rich.console import Console
from rich.markup import escape
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Column, Table
from rich.text import Text

from telegram_courses.course_download_planning import CoursePlanReview
from telegram_courses.course_execution import CourseExecutionSummary, ProgressSnapshot
from telegram_courses.course_offline_execution import (
    OfflineCourseSandbox,
    OfflineExecutionAuthorization,
)


def _literal(value: str | None) -> str:
    raw = value or "Indisponível"
    return "".join(
        character for character in raw
        if unicodedata.category(character) not in {"Cc", "Cf", "Cs"}
    )


class RichCourseProgress:
    """Renderer intended for ProgressDispatcher's bounded background worker."""

    def __init__(self, review: CoursePlanReview, console: Console) -> None:
        self.plan = review.plan
        context_items = review.catalog_context[-1] if review.catalog_context else ()
        self._modules = {
            (item[0], item[1], item[2]): item[6]
            for item in context_items if isinstance(item, tuple) and len(item) > 6
        }
        self.console = console
        self._progress: Progress | None = None
        self._file_task: int | None = None
        self._batch_task: int | None = None

    def __call__(self, snapshot: ProgressSnapshot) -> None:
        if self._progress is None:
            self._progress = Progress(
                TextColumn("{task.fields[label]}", table_column=Column(ratio=2, overflow="fold")),
                BarColumn(bar_width=12),
                TextColumn("{task.fields[detail]}", table_column=Column(ratio=4, overflow="fold")),
                console=self.console, auto_refresh=False,
                redirect_stdout=False, redirect_stderr=False,
                expand=True,
            )
            self._progress.start()
            self._file_task = self._progress.add_task("arquivo", total=None, label="Arquivo", detail="")
            self._batch_task = self._progress.add_task("lote", total=None, label="Lote", detail="")
        item = next((item for item in self.plan.pending if item.identity == snapshot.identity), None)
        candidate = item.candidate if item else None
        filename = _literal(candidate.original_filename if candidate else None)
        module = self._modules.get(snapshot.identity)
        name = escape(f"{_literal(self.plan.scope_title)} / {_literal(module)} / {filename}")
        file_bytes = str(snapshot.file_bytes) if snapshot.file_bytes is not None else "Indisponível"
        file_total = str(snapshot.file_total) if snapshot.file_total is not None else "Indisponível"
        percent = (
            f"{100 * snapshot.file_bytes / snapshot.file_total:.1f}%"
            if snapshot.file_bytes is not None and snapshot.file_total is not None
            and snapshot.file_total > 0 else "Indisponível"
        )
        speed = f"{snapshot.speed_mb_s:.2f} MB/s" if snapshot.speed_mb_s is not None else "Indisponível"
        eta = f"{snapshot.eta_seconds:.1f}s" if snapshot.eta_seconds is not None else "Indisponível"
        status = snapshot.file_status
        detail = escape(
            f"{snapshot.position}/{snapshot.total_files} | {status} | {file_bytes}/{file_total} bytes ({percent}) "
            f"| velocidade {speed} | decorrido {snapshot.elapsed_seconds:.1f}s | ETA {eta}"
        )
        self._progress.update(
            self._file_task, total=snapshot.file_total,
            completed=snapshot.file_bytes or 0, label=name, detail=detail,
        )
        batch_percent = (
            f"{100 * snapshot.batch_validated_bytes / snapshot.batch_total_bytes:.1f}%"
            if snapshot.batch_total_bytes is not None and snapshot.batch_total_bytes > 0
            else "Indisponível"
        )
        batch_detail = escape(
            f"elegíveis validados {snapshot.batch_validated_bytes}/"
            f"{snapshot.batch_total_bytes if snapshot.batch_total_bytes is not None else 'Indisponível'} bytes ({batch_percent}) | "
            f"concluídos {snapshot.completed_files}/{snapshot.total_files} | "
            f"já válidos {snapshot.already_valid_files} | recebidos {snapshot.received_bytes} bytes "
            f"(incluem prova/sobreposição) | orçamento "
            f"{snapshot.budget_charged_bytes if snapshot.budget_charged_bytes is not None else 'Indisponível'} bytes "
            f"| incertos {snapshot.budget_uncertain_bytes if snapshot.budget_uncertain_bytes is not None else 'Indisponível'} "
            f"| prova {snapshot.proof_received_bytes} bytes | sobreposição {snapshot.overlap_received_bytes} bytes "
            f"| prova verificada {snapshot.proof_verified_bytes} bytes | sobreposição prevista {snapshot.planned_overlap_bytes} bytes "
            "| ETA Indisponível"
        )
        self._progress.update(
            self._batch_task, total=snapshot.batch_total_bytes,
            completed=snapshot.batch_validated_bytes, label="Lote", detail=batch_detail, refresh=True,
        )

    def close(self) -> None:
        if self._progress is not None:
            self._progress.stop()


def render_execution_summary(summary: CourseExecutionSummary, console: Console) -> None:
    table = Table("Indicador", "Resultado")
    for label, value in (
        ("Estado", summary.status), ("Selecionados", summary.selected),
        ("Elegíveis", summary.eligible), ("Já válidos", summary.already_valid),
        ("Concluídos", summary.completed), ("Pendentes", summary.pending),
        ("Excluídos", summary.excluded), ("Bloqueados", summary.blocked),
        ("Falhos", summary.failed), ("Cancelados", summary.cancelled),
        ("Bytes recebidos", summary.transferred_bytes),
        ("Bytes concluídos e validados", summary.validated_bytes),
        ("Bytes já válidos", summary.previously_valid_bytes),
        ("Bytes recebidos para prova", summary.proof_received_bytes if summary.proof_received_bytes is not None else "Indisponível"),
        ("Bytes recebidos em sobreposição", summary.overlap_received_bytes if summary.overlap_received_bytes is not None else "Indisponível"),
        ("Bytes de prova verificada", summary.proof_verified_bytes),
        ("Sobreposição prevista", summary.planned_overlap_bytes),
        ("Bytes debitados no orçamento", summary.budget_charged_bytes if summary.budget_charged_bytes is not None else "Indisponível"),
        ("Bytes incertos no orçamento", summary.budget_uncertain_bytes if summary.budget_uncertain_bytes is not None else "Indisponível"),
        ("Falha ao encerrar gateway", "Sim" if summary.cleanup_failed else "Não"),
    ):
        table.add_row(Text(label), Text(str(value)))
    console.print(table)
    for identity, status, reason in summary.outcomes:
        console.print(
            f"{identity[0]}:{identity[1]}:{identity[2]} | {_literal(status)} | {_literal(reason)}",
            markup=False,
        )
    if summary.observed_exclusions:
        console.print("Observados fora do plano:", markup=False)
        for item in summary.observed_exclusions:
            console.print(
                f"{item.identity[0]}:{item.identity[1]}:{item.identity[2]} | "
                f"{_literal(item.filename)} | {_literal(item.reason)}",
                markup=False,
            )
    if summary.presentation_failed or summary.presentation_incomplete:
        console.print("Apresentação de progresso incompleta; resumo obtido da fila.", markup=False)


async def run_offline_with_rich(
    sandbox: OfflineCourseSandbox,
    authorization: OfflineExecutionAuthorization,
    console: Console,
    *,
    cancel_event: asyncio.Event | None = None,
) -> CourseExecutionSummary:
    """Render a separately authorized fake-only sandbox run."""
    presenter = RichCourseProgress(authorization._confirmation.review, console)
    summary = await sandbox.execute(authorization, observer=presenter, cancel_event=cancel_event)
    try:
        render_execution_summary(summary, console)
    except Exception:
        summary = replace(summary, presentation_failed=True)
    return summary


async def run_live_with_rich(
    executor: object,
    authorization: object,
    console: Console,
    *,
    cancel_event: asyncio.Event | None = None,
):
    """Use the same Rich presenter for the operational S5 execution path."""
    from telegram_courses.course_live_execution import (
        LiveCourseExecutor,
        LiveExecutionAuthorization,
    )

    if (
        type(executor) is not LiveCourseExecutor
        or type(authorization) is not LiveExecutionAuthorization
    ):
        raise ValueError("invalid live execution authorization")
    presenter = RichCourseProgress(authorization._confirmation.review, console)
    summary = await executor.execute(
        authorization, observer=presenter, cancel_event=cancel_event,
    )
    try:
        render_execution_summary(summary, console)
    except Exception:
        summary = replace(summary, presentation_failed=True)
    return summary
