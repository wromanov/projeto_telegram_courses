"""Fail-closed, run-bound human confirmation required before the first S9 RPC."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import TextIO

from telegram_courses.s9_operational_ledger import LedgerError, S9OperationalLedger

G0_CONFIRMATION_TIMEOUT_SECONDS = 60
G0_RECEIPT_FILE = "g0-gate-receipt.json"


class G0ConfirmationError(RuntimeError):
    """G0 was not interactively confirmed or could not be durably recorded."""


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _event_id(run_id: str, nonce_sha256: str, action: str) -> str:
    return hashlib.sha256(
        f"{run_id}:G0:{nonce_sha256}:{action}".encode("ascii"),
    ).hexdigest()[:32]


def _streams_are_tty(stdin: TextIO, stdout: TextIO) -> bool:
    try:
        return bool(stdin.isatty() and stdout.isatty())
    except (AttributeError, OSError):
        return False


def _read_tty_line(
    prompt: str,
    *,
    stdin: TextIO,
    stdout: TextIO,
    timeout_seconds: int,
) -> str:
    """Read one bounded line without accepting redirected or piped input."""
    stdout.write(prompt)
    stdout.flush()
    deadline = time.monotonic() + timeout_seconds
    if os.name == "nt":
        import msvcrt

        chars: list[str] = []
        while time.monotonic() < deadline:
            if not msvcrt.kbhit():
                time.sleep(0.025)
                continue
            char = msvcrt.getwch()
            if char in {"\x00", "\xe0"}:
                msvcrt.getwch()
                continue
            if char in {"\r", "\n"}:
                stdout.write("\n")
                stdout.flush()
                return "".join(chars)
            if char == "\x1b":
                stdout.write("\n")
                stdout.flush()
                return ""
            if char == "\b":
                if chars:
                    chars.pop()
                    stdout.write("\b \b")
                    stdout.flush()
                continue
            if char.isascii() and char.isprintable() and len(chars) < 160:
                chars.append(char)
                stdout.write(char)
                stdout.flush()
        raise TimeoutError

    import select

    remaining = max(0.0, deadline - time.monotonic())
    ready, _, _ = select.select([stdin], [], [], remaining)
    if not ready:
        raise TimeoutError
    return stdin.readline().rstrip("\r\n")


def _record_blocked(
    ledger: S9OperationalLedger,
    *,
    run_id: str,
    nonce_sha256: str,
    channel_ref: str,
    manifest_sha256: str,
    scope_sha256: str,
    confirmation_source: str,
    reason: str,
) -> None:
    ledger.record_critical_event(
        "G0_CONFIRMATION_BLOCKED",
        details={
            "gate": "G0",
            "channel_ref": channel_ref,
            "manifest_sha256": manifest_sha256,
            "scope_sha256": scope_sha256,
            "nonce_sha256": nonce_sha256,
            "confirmation_source": confirmation_source,
            "reason": reason,
        },
        event_id=_event_id(run_id, nonce_sha256, f"blocked-{reason.lower()}"),
    )


def request_g0_confirmation(
    run_directory: str | Path,
    ledger: S9OperationalLedger,
    *,
    run_id: str,
    manifest: dict[str, object],
    manifest_sha256: str,
    scope_sha256: str,
    test_mode: bool = False,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> dict[str, object]:
    """Prompt for a run-scoped approval and persist its one-use evidence.

    ``test_mode`` only produces explicitly synthetic evidence. It is not exposed
    by the CLI and that evidence is ineligible to release a live G1 worker.
    """
    if not test_mode and (stdin is not None or stdout is not None):
        raise G0ConfirmationError("G0_INTERACTIVE_STREAM_OVERRIDE_FORBIDDEN")
    from telegram_courses.s9_real_gate_producers import (
        GateEvidenceError,
        load_approved_manifest,
        persist_gate_receipt,
    )

    selected_stdin = sys.stdin if stdin is None else stdin
    selected_stdout = sys.stdout if stdout is None else stdout
    source = "SYNTHETIC_TEST" if test_mode else "INTERACTIVE_TTY"
    origin = "SYNTHETIC" if test_mode else "HUMAN_INTERACTIVE"
    result_status = "OFFLINE_SYNTHETIC_PASS" if test_mode else "PASS"
    root = Path(run_directory)
    channel_id = manifest.get("channel_id")
    scope = manifest.get("scope")
    initial_snapshot = ledger.snapshot()
    initial_audit = initial_snapshot.get("critical_audit", {})
    initial_events = (
        initial_audit.get("events", []) if type(initial_audit) is dict else []
    )
    if (
        type(channel_id) is not int or type(scope) is not dict
        or initial_snapshot.get("run", {}).get("run_id") != run_id
        or initial_audit.get("quarantined") is not False
    ):
        raise G0ConfirmationError("G0_RUN_OR_AUDIT_INVALID")
    if any(
        type(item) is dict and item.get("event_type") in {
            "G0_CONFIRMATION_REQUESTED", "G0_CONFIRMATION_CONSUMED",
            "G0_CONFIRMATION_BLOCKED",
        }
        for item in initial_events
    ):
        raise G0ConfirmationError("G0_CONFIRMATION_ALREADY_ATTEMPTED")
    channel_ref = _digest(str(channel_id))
    receipt_path = root / G0_RECEIPT_FILE
    try:
        receipt_path.lstat()
    except FileNotFoundError:
        pass
    except OSError:
        raise G0ConfirmationError("G0_RECEIPT_STATE_UNAVAILABLE") from None
    else:
        raise G0ConfirmationError("G0_CONFIRMATION_ALREADY_CONSUMED")

    nonce = secrets.token_hex(16)
    nonce_sha256 = _digest(nonce)
    issued_ns = time.time_ns()
    expires_ns = issued_ns + G0_CONFIRMATION_TIMEOUT_SECONDS * 1_000_000_000
    request_event_id = _event_id(run_id, nonce_sha256, "requested")
    consumed_event_id = _event_id(run_id, nonce_sha256, "consumed")
    common_details = {
        "gate": "G0",
        "channel_ref": channel_ref,
        "manifest_sha256": manifest_sha256,
        "scope_sha256": scope_sha256,
        "nonce_sha256": nonce_sha256,
        "confirmation_source": source,
        "issued_ns": issued_ns,
        "expires_ns": expires_ns,
    }
    try:
        ledger.record_critical_event(
            "G0_CONFIRMATION_REQUESTED", details=common_details,
            event_id=request_event_id,
        )
    except LedgerError as error:
        raise G0ConfirmationError("G0_AUDIT_WRITE_FAILED") from error

    def block(reason: str) -> None:
        try:
            _record_blocked(
                ledger, run_id=run_id, nonce_sha256=nonce_sha256,
                channel_ref=channel_ref, manifest_sha256=manifest_sha256,
                scope_sha256=scope_sha256, confirmation_source=source,
                reason=reason,
            )
        except LedgerError as error:
            raise G0ConfirmationError("G0_AUDIT_WRITE_FAILED") from error
        raise G0ConfirmationError(f"G0_{reason}")

    if not _streams_are_tty(selected_stdin, selected_stdout):
        block("TTY_REQUIRED")

    scope_text = json.dumps(scope, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    prompt = (
        "\nConfirmação G0 — antes da primeira RPC Telegram\n"
        f"Run: {run_id}\n"
        f"Canal alvo: {manifest.get('channel_alias')} (ID {channel_id})\n"
        f"Manifesto SHA-256: {manifest_sha256}\n"
        f"Escopo autorizado: {scope_text}\n"
        "Limites: até 200 mensagens por scan, 3 scans e 600 observações no total; "
        "janela incremental de 50 IDs. G0 cobre autenticação e descoberta; o plano "
        "de downloads terá confirmação própria em G4.\n"
        f"Para aprovar somente este run, digite: APROVAR S9 G0 {nonce}\n> "
    )
    try:
        answer = _read_tty_line(
            prompt, stdin=selected_stdin, stdout=selected_stdout,
            timeout_seconds=G0_CONFIRMATION_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        block("TIMEOUT")
    except (EOFError, KeyboardInterrupt):
        block("DECLINED")
    except (OSError, ValueError):
        block("TTY_READ_FAILED")
    if answer.strip() != f"APROVAR S9 G0 {nonce}":
        block("DECLINED" if answer.strip().upper() in {"N", "NAO", "NÃO", "RECUSAR"} else "MISMATCH")
    consumed_ns = time.time_ns()
    if consumed_ns > expires_ns:
        block("EXPIRED")

    try:
        current_manifest, current_manifest_sha256, current_scope_sha256 = load_approved_manifest(root)
    except GateEvidenceError:
        block("MANIFEST_REVALIDATION_FAILED")
    if (
        current_manifest_sha256 != manifest_sha256
        or current_scope_sha256 != scope_sha256
        or current_manifest.get("channel_id") != channel_id
        or current_manifest.get("scope") != scope
    ):
        block("SCOPE_CHANGED")
    current_snapshot = ledger.snapshot()
    if (
        current_snapshot.get("run", {}).get("run_id") != run_id
        or current_snapshot.get("critical_audit", {}).get("quarantined") is not False
        or any(
            item.get("event_type") == "G0_CONFIRMATION_CONSUMED"
            for item in current_snapshot.get("critical_audit", {}).get("events", [])
        )
    ):
        block("REPLAY_OR_AUDIT_INVALID")

    consumed_details = common_details | {"consumed_ns": consumed_ns}
    try:
        ledger.record_critical_event(
            "G0_CONFIRMATION_CONSUMED", details=consumed_details,
            event_id=consumed_event_id,
        )
    except LedgerError as error:
        raise G0ConfirmationError("G0_AUDIT_WRITE_FAILED") from error
    receipt: dict[str, object] = {
        "schema_version": 1,
        "gate": "G0",
        "status": result_status,
        "evidence_origin": origin,
        "reason": "INTERACTIVE_SCOPE_CONFIRMED" if not test_mode else "SYNTHETIC_CONFIRMATION_SIMULATED",
        "run_id": run_id,
        "manifest_sha256": manifest_sha256,
        "scope_sha256": scope_sha256,
        "channel_id": channel_id,
        "channel_alias": manifest.get("channel_alias"),
        "authorized_scope": scope,
        "authorized_limits": {
            "max_per_scan": 200,
            "max_total_scans": 3,
            "max_total_observations": 600,
            "incremental_window": 50,
        },
        "confirmation_source": source,
        "nonce_sha256": nonce_sha256,
        "issued_ns": issued_ns,
        "expires_ns": expires_ns,
        "consumed_ns": consumed_ns,
        "request_event_id": request_event_id,
        "consumed_event_id": consumed_event_id,
    }
    try:
        persist_gate_receipt(root, ledger, receipt)
    except Exception as error:
        raise G0ConfirmationError("G0_RECEIPT_PERSIST_FAILED") from error
    return receipt

