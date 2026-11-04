"""Manual, metadata-only target discovery for the confirmed S6 channel."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from typing import Any

CHANNEL_ID = -1002758699600
MAX_DIALOGS = 100
MAX_MESSAGES = 200
EXECUTE_CONFIRMATION = "I CONFIRM S6 METADATA RASMOO"


def _safe_filename(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    name = value.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:160]
    return name or None


def _copy_counts(report: dict[str, Any], gateway: Any) -> None:
    report["dialog_rpcs"] = getattr(gateway, "_metadata_dialog_rpcs", 0)
    report["dialogs_inspected"] = getattr(
        gateway, "_metadata_dialogs_inspected", 0
    )
    report["metadata_rpcs"] = getattr(gateway, "_metadata_message_rpcs", 0)
    report["messages_inspected"] = getattr(
        gateway, "_metadata_messages_inspected", 0
    )


def _copy_peer_recovery_reason(
    report: dict[str, Any], gateway: Any, allowed_reasons: frozenset[str]
) -> None:
    reason = getattr(gateway, "_metadata_peer_recovery_reason", None)
    report["peer_resolution_reason"] = (
        reason if isinstance(reason, str) and reason in allowed_reasons else None
    )


def _dry_run() -> int:
    print(json.dumps({
        "activity": "S6_BOUNDED_TARGET_DISCOVERY",
        "mode": "DRY_RUN",
        "telegram_restore": False,
        "telegram_rpc_calls": 0,
        "sqlite_access": False,
        "media_payload_bytes": 0,
        "getfile_calls": 0,
        "getfilehashes_calls": 0,
        "peer_resolution_reason": None,
        "planned_limits": {
            "channel_id": CHANNEL_ID,
            "dialogs_per_rpc": MAX_DIALOGS,
            "dialog_rpcs": 1,
            "messages": MAX_MESSAGES,
        },
    }, sort_keys=True))
    return 0


async def _execute() -> int:
    if os.environ.get("S6_BOUNDED_TARGET_CONFIRMATION") != EXECUTE_CONFIRMATION:
        print("Confirmation gate missing; no session restore or RPC performed.")
        return 2

    from telegram_courses.auth import AuthState
    from telegram_courses.config import load_telegram_credentials
    from telegram_courses.message_scanner import ScanGatewayError
    from telegram_courses.telethon_gateway import (
        S6_PEER_RECOVERY_REASONS,
        TelethonGateway,
        _ProtectedSessionVault,
    )

    report: dict[str, Any] = {
        "activity": "S6_BOUNDED_TARGET_DISCOVERY",
        "mode": "EXECUTE",
        "channel_id": CHANNEL_ID,
        "identity_authority": "explicit_user_confirmation",
        "status": "NOT_STARTED",
        "peer_resolution_reason": None,
        "dialog_rpcs": 0,
        "dialogs_inspected": 0,
        "metadata_rpcs": 0,
        "messages_inspected": 0,
        "documents": [],
        "getfile_calls": 0,
        "getfilehashes_calls": 0,
        "media_payload_bytes": 0,
        "sqlite_access": False,
    }
    gateway = None
    try:
        vault = _ProtectedSessionVault()
        # `_existing_blob` checks the protected artifact without creating its
        # parent directory. Do not invoke restore if it is absent.
        if not vault._existing_blob():
            report["status"] = "PROTECTED_SESSION_ABSENT"
            return _emit(report, 2)
        credentials = load_telegram_credentials(environ={})
        gateway = TelethonGateway(
            credentials,
            vault=vault,
            receive_updates=False,
            catch_up=False,
            request_retries=0,
            connection_retries=0,
        )
        state = await gateway.restore()
        if state is not AuthState.AUTHENTICATED:
            report["status"] = "SESSION_NOT_AUTHENTICATED"
            report["authentication_state"] = state.value
            return _emit(report, 2)

        matched = await gateway.recover_selected_channel_peer(
            CHANNEL_ID, max_dialogs=MAX_DIALOGS
        )
        _copy_counts(report, gateway)
        _copy_peer_recovery_reason(report, gateway, S6_PEER_RECOVERY_REASONS)
        if not matched:
            report["status"] = "NOT_FOUND_IN_BOUNDED_WINDOW"
            return _emit(report, 2)

        report["status"] = "METADATA_COMPLETE"
        async for message in gateway.iter_channel_metadata(
            CHANNEL_ID, max_messages=MAX_MESSAGES
        ):
            for media in message.media:
                if media.kind != "DOCUMENT":
                    continue
                report["documents"].append({
                    "message_id": message.telegram_message_id,
                    "media_id": media.telegram_media_id,
                    "size_bytes": media.file_size_bytes,
                    "mime_type": media.mime_type,
                    "filename": _safe_filename(media.original_filename),
                    "message_date_utc": message.date_utc,
                })
        _copy_counts(report, gateway)
        _copy_peer_recovery_reason(report, gateway, S6_PEER_RECOVERY_REASONS)
        return _emit(report, 0)
    except ScanGatewayError as error:
        report["status"] = error.category
        if gateway is not None:
            _copy_counts(report, gateway)
            _copy_peer_recovery_reason(report, gateway, S6_PEER_RECOVERY_REASONS)
        return _emit(report, 2)
    except Exception as error:
        # Never print exception text, arguments, credentials, or session data.
        report["status"] = "FAILURE_" + type(error).__name__[:48]
        if gateway is not None:
            _copy_counts(report, gateway)
            _copy_peer_recovery_reason(report, gateway, S6_PEER_RECOVERY_REASONS)
        return _emit(report, 2)
    finally:
        if gateway is not None:
            try:
                await gateway.close()
            except Exception:
                pass


def _emit(report: dict[str, Any], exit_code: int) -> int:
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.dry_run:
        return _dry_run()
    return asyncio.run(_execute())


if __name__ == "__main__":
    sys.exit(main())
