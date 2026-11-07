"""Live course execution composed around the existing S5 queue.

This module has no public CLI bypass. The caller must obtain a fresh, confirmed
course plan and an explicit one-use operator confirmation before constructing a
Telegram gateway. Tests inject only synthetic gateways.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from dataclasses import dataclass, replace
from typing import Callable

from telegram_courses.auth import AuthState, RateLimited
from telegram_courses.catalog import CatalogError
from telegram_courses.config import ConfigurationError, TelegramCredentials
from telegram_courses.course_download_planning import (
    CoursePlanReview,
    create_course_plan_review,
)
from telegram_courses.course_execution import (
    ConfirmedCoursePlan,
    CourseExecutionSummary,
    ProgressSnapshot,
    execute_queue_with_progress,
    summarize_execution,
)
from telegram_courses.course_review_context import load_course_review_context
from telegram_courses.database_preparation import (
    DatabasePreparationError,
    VerifiedDatabaseBackup,
    verify_backup_receipt,
)
from telegram_courses.downloads import DownloadError
from telegram_courses.s5_downloads import DownloadPlanner


@dataclass(frozen=True)
class LiveExecutionAuthorization:
    """One-use authorization bound to the reviewed plan and verified backup."""

    _executor: object
    _confirmation: ConfirmedCoursePlan
    _backup: VerifiedDatabaseBackup
    _nonce: object


GatewayFactory = Callable[[TelegramCredentials, int], object]


def _verify_backup_for_confirmation(
    confirmation: ConfirmedCoursePlan,
    backup: VerifiedDatabaseBackup,
) -> None:
    try:
        verify_backup_receipt(backup, confirmation.database)
    except (DatabasePreparationError, OSError, ValueError):
        raise DownloadError("OPERATIONAL_BACKUP_UNVERIFIED") from None


class LiveCourseExecutor:
    """Revalidate a confirmed plan before handing it to the existing S5 queue."""

    def __init__(
        self,
        gateway_factory: GatewayFactory,
        credentials_loader: Callable[[], TelegramCredentials],
        *,
        attempts_per_media: int = 3,
    ) -> None:
        if type(attempts_per_media) is not int or not 1 <= attempts_per_media <= 3:
            raise ValueError("invalid attempts per media")
        self._gateway_factory = gateway_factory
        self._credentials_loader = credentials_loader
        self._attempts_per_media = attempts_per_media
        self._active_nonce: object | None = None

    def authorize(
        self,
        confirmation: ConfirmedCoursePlan,
        backup: VerifiedDatabaseBackup,
        *,
        selection_prompt: Callable[[str], str],
        require_tty: bool = True,
    ) -> LiveExecutionAuthorization | None:
        """Ask for separate, explicit authorization for real payload transfer."""
        if require_tty and not sys.stdin.isatty():
            raise DownloadError("LIVE_EXECUTION_REQUIRES_TTY")
        review = confirmation.review
        if not isinstance(review, CoursePlanReview) or not review.can_confirm:
            raise DownloadError("LIVE_PLAN_NOT_CONFIRMABLE")
        _verify_backup_for_confirmation(confirmation, backup)
        selection = review.plan.selection
        prompt = (
            "CONFIRMAÇÃO DE EXECUÇÃO REAL: acessar Telegram e transferir "
            f"{len(review.plan.pending)} arquivo(s) do canal {selection.channel_id}, "
            f"curso local {selection.node_id}; destino {review.download_root}; "
            f"limites itens={review.max_media_items or 'sem cap adicional'}, "
            f"bytes={review.max_transfer_bytes or 'sem cap adicional'}, "
            f"integridade={review.integrity_mode}. Autorizar agora? [s/N] "
        )
        try:
            answer = selection_prompt(prompt)
        except (EOFError, KeyboardInterrupt):
            return None
        if answer.strip().casefold() not in {"s", "sim", "y", "yes"}:
            return None
        nonce = object()
        self._active_nonce = nonce
        return LiveExecutionAuthorization(self, confirmation, backup, nonce)

    @staticmethod
    def _reject_s9_supervision() -> None:
        names = (
            "TELEGRAM_COURSES_S9_SUPERVISED_CHILD",
            "TELEGRAM_COURSES_S9_HANDSHAKE_DIR",
            "TELEGRAM_COURSES_S9_HANDSHAKE_NONCE",
            "TELEGRAM_COURSES_S9_LEDGER_PATH",
            "TELEGRAM_COURSES_S9_PROFILE",
        )
        if any(os.environ.get(name) for name in names):
            raise DownloadError("LIVE_EXECUTION_UNSUPPORTED_IN_S9_SUPERVISION")

    async def execute(
        self,
        authorization: LiveExecutionAuthorization,
        *,
        observer: Callable[[ProgressSnapshot], None] | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> CourseExecutionSummary:
        if (
            type(authorization) is not LiveExecutionAuthorization
            or authorization._executor is not self
            or authorization._nonce is not self._active_nonce
            or self._active_nonce is None
        ):
            raise DownloadError("LIVE_EXECUTION_NOT_AUTHORIZED")
        self._active_nonce = None
        self._reject_s9_supervision()
        confirmation = authorization._confirmation
        _verify_backup_for_confirmation(confirmation, authorization._backup)
        if cancel_event is not None and cancel_event.is_set():
            return summarize_execution(confirmation.review.plan, cancelled=True)

        prior = confirmation.review
        planner = DownloadPlanner(confirmation.database, prior.download_root)
        selection = prior.plan.selection
        try:
            (
                _, _, _, _, fresh_selection, exclusions, context,
            ) = await load_course_review_context(
                planner,
                channel_id=selection.channel_id,
                course_id=selection.node_id,
                selection_mode=prior.selection_mode,
                exact_selection=selection if prior.selection_mode == "SELECTED" else None,
            )
            if fresh_selection is None:
                return summarize_execution(
                    prior.plan, global_block="PLAN_CHANGED",
                    observed_exclusions=prior.observed_exclusions,
                )
            plan = await planner.build(fresh_selection)
            item_ids = {item.identity for item in plan.items}
            fresh = create_course_plan_review(
                plan,
                selection_mode=prior.selection_mode,
                download_root=prior.download_root,
                integrity_mode=prior.integrity_mode,
                max_media_items=prior.max_media_items,
                max_transfer_bytes=prior.max_transfer_bytes,
                observed_exclusions=tuple(item for item in exclusions if item.identity not in item_ids),
                catalog_context=context,
            )
        except asyncio.CancelledError:
            return summarize_execution(prior.plan, cancelled=True)
        except (CatalogError, DownloadError, DatabasePreparationError, OSError, sqlite3.Error):
            return summarize_execution(
                prior.plan, global_block="PLAN_REVALIDATION_FAILED",
                observed_exclusions=prior.observed_exclusions,
            )
        if not prior.matches_after_confirmation(fresh):
            return summarize_execution(
                prior.plan, global_block="PLAN_CHANGED",
                observed_exclusions=prior.observed_exclusions,
            )
        if not plan.pending:
            return summarize_execution(plan, observed_exclusions=fresh.observed_exclusions)
        _verify_backup_for_confirmation(confirmation, authorization._backup)
        gateway = None
        summary: CourseExecutionSummary
        cleanup_failed = False
        try:
            credentials = self._credentials_loader()
            gateway = self._gateway_factory(credentials, selection.channel_id)
            state = await gateway.restore()
            if state is not AuthState.AUTHENTICATED:
                summary = summarize_execution(
                    plan,
                    global_block="SESSION_INVALID",
                    observed_exclusions=fresh.observed_exclusions,
                )
            else:
                summary = await execute_queue_with_progress(
                    confirmation.database,
                    prior.download_root,
                    plan,
                    gateway,
                    attempts_per_media=self._attempts_per_media,
                    max_media_items=prior.max_media_items,
                    max_transfer_bytes=prior.max_transfer_bytes,
                    integrity_mode=prior.integrity_mode,
                    observer=observer,
                    cancel_event=cancel_event,
                    observed_exclusions=fresh.observed_exclusions,
                )
        except asyncio.CancelledError:
            summary = summarize_execution(
                plan, cancelled=True,
                observed_exclusions=fresh.observed_exclusions,
            )
        except Exception as error:
            category = (
                "CONFIGURATION" if isinstance(error, ConfigurationError)
                else "RATE_LIMITED" if isinstance(error, RateLimited)
                else error.category if isinstance(error, DownloadError)
                else "LIVE_EXECUTION_FAILED"
            )
            summary = summarize_execution(
                plan, global_block=category,
                observed_exclusions=fresh.observed_exclusions,
            )
        finally:
            close = getattr(gateway, "close", None)
            if callable(close):
                try:
                    await close()
                except Exception:
                    cleanup_failed = True
        return replace(summary, cleanup_failed=cleanup_failed)
