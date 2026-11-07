"""Bounded single-media download orchestration and Windows-safe file policy."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import stat
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Literal, Protocol

from telegram_courses.download_repository import (
    DownloadCandidate,
    DownloadInProgress,
    DownloadMediaNotObserved,
    DownloadRepository,
    _process_is_alive,
)
from telegram_courses.operational_logging import emit_operational_event
from telegram_courses.s6_integrity import (
    V2_EFFECTIVE,
    assess_remote_hashes,
    files_equal,
    load_reference,
    reference_unchanged,
)

CHUNK_BYTES = 256 * 1024
_RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.IGNORECASE)
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_SAFE_ERROR_CATEGORY = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_LOCKS: dict[int, asyncio.Lock] = {}


def _safe_error_category(value: object) -> str:
    if isinstance(value, str) and _SAFE_ERROR_CATEGORY.fullmatch(value):
        return value
    return "UNKNOWN"


class DownloadError(Exception):
    def __init__(
        self, category: str, *, retry_after_seconds: int | None = None,
        failure_phase: str | None = None,
        remote_hash_events: tuple[dict[str, object], ...] | None = None,
    ) -> None:
        self.category = _safe_error_category(category)
        self.retry_after_seconds = (
            retry_after_seconds
            if self.category == "RATE_LIMITED"
            and type(retry_after_seconds) is int
            and retry_after_seconds >= 0
            else None
        )
        self.failure_phase = failure_phase
        self.remote_hash_events = remote_hash_events or ()
        super().__init__(self.category.lower().replace("_", " "))


class DownloadGatewayError(Exception):
    def __init__(self, category: str, *, retry_after_seconds: int | None = None) -> None:
        self.category = _safe_error_category(category)
        self.retry_after_seconds = (
            retry_after_seconds
            if self.category == "RATE_LIMITED"
            and type(retry_after_seconds) is int
            and retry_after_seconds >= 0
            else None
        )
        super().__init__(self.category)


def _assert_disk_capacity(
    download_root: Path,
    remaining_bytes: int,
    free_space: Callable[[Path], int],
) -> None:
    """Fail closed before a standalone transfer when its size is known."""
    if type(remaining_bytes) is not int or remaining_bytes < 0:
        raise DownloadError("UNKNOWN_SIZE")
    if remaining_bytes == 0:
        return

    probe = download_root.expanduser().absolute()
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        available_bytes = free_space(probe)
    except Exception:
        raise DownloadError("STORAGE_UNAVAILABLE") from None
    if type(available_bytes) is not int or available_bytes < 0:
        raise DownloadError("STORAGE_UNAVAILABLE")

    safety_margin = max(1024**3, int(remaining_bytes * 0.10))
    if available_bytes < remaining_bytes + safety_margin:
        raise DownloadError("INSUFFICIENT_DISK_SPACE")


class DownloadGateway(Protocol):
    async def stream_media(
        self, channel_id: int, message_id: int, media_ordinal: int,
        *, telegram_media_id: str, expected_bytes: int,
        reserve_chunk: Callable[[int], Awaitable["ChunkReservation | None"]] | None = None,
        offset: int = 0,
    ) -> AsyncIterator[bytes]: ...

    async def get_file_hashes(
        self, channel_id: int, message_id: int, media_ordinal: int,
        *, telegram_media_id: str, expected_bytes: int, offset: int = 0,
    ) -> tuple["RemoteFileHash", ...]: ...


@dataclass(frozen=True)
class RemoteFileHash:
    offset: int
    limit: int
    sha256: bytes | str


@dataclass(frozen=True)
class S6PrefixProofObservation:
    """Remote-hash ranges that were checked against an owned partial file.

    The application creates this value only after S6 V1 has verified complete
    remote range coverage and matching local bytes. A caller cannot use a
    boolean flag in place of those range observations.
    """

    candidate_identity: tuple[int, int, int]
    expected_bytes: int
    physical_prefix_bytes: int
    local_prefix_sha256: str
    remote_ranges: tuple[RemoteFileHash, ...]
    verification_payload_bytes: int
    integrity_mode: Literal["REMOTE_HASH_REQUIRED"] = "REMOTE_HASH_REQUIRED"


class ChunkReservation(Protocol):
    def received(self, byte_count: int) -> None: ...

    def release(self) -> None: ...

    def charge_uncertain(self) -> None: ...


class _UnboundedChunkReservation:
    """Explicit per-request lease when the user configured no aggregate cap."""

    def __init__(self, amount: int) -> None:
        self.amount = amount
        self.settled = False

    def received(self, byte_count: int) -> None:
        if self.settled or type(byte_count) is not int or not 0 <= byte_count <= self.amount:
            raise DownloadError("TRANSFER_BUDGET_STATE_INVALID")
        self.settled = True

    def release(self) -> None:
        self.settled = True

    def charge_uncertain(self) -> None:
        self.settled = True


async def _reserve_unbounded_chunk(amount: int) -> ChunkReservation | None:
    if type(amount) is not int or amount <= 0:
        return None
    return _UnboundedChunkReservation(amount)


@dataclass(frozen=True)
class DownloadOutcome:
    result: str
    candidate: DownloadCandidate
    final_path: Path
    transferred_bytes: int
    sha256: str | None
    integrity_mode: str = "REMOTE_HASH_REQUIRED"
    evidence_class: str | None = None
    remote_hash_class: str | None = None
    guarantee: str | None = None


def sanitize_component(value: str | None, fallback: str) -> str:
    cleaned = _INVALID.sub("_", value or "").strip().rstrip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)[:100].rstrip(" .")
    if not cleaned:
        cleaned = fallback
    if _RESERVED.match(cleaned):
        cleaned = f"_{cleaned}"
    return cleaned


def destination_paths(root: Path, candidate: DownloadCandidate) -> tuple[Path, Path]:
    root = root.expanduser().absolute()
    parts = [sanitize_component(title, kind.title()) for kind, title in candidate.lineage]
    lesson_file = candidate.lineage[-1][1] if candidate.lineage else None
    filename = sanitize_component(
        candidate.original_filename,
        f"media-{candidate.media_item_id}.bin",
    )
    path = Path(filename)
    suffix = path.suffix[:20]
    stem = path.stem or f"media-{candidate.media_item_id}"
    identity = (
        f" [c{candidate.channel_id}-m{candidate.telegram_message_id}"
        f"-o{candidate.media_ordinal}]"
    )
    filename = f"{sanitize_component(lesson_file, 'Lesson')} - {stem[:60]}{identity}{suffix}"
    final_path = root.joinpath(*parts, filename)
    if len(str(final_path)) > 240:
        raise DownloadError("PATH_TOO_LONG")
    try:
        final_path.relative_to(root)
    except ValueError:
        raise DownloadError("UNSAFE_PATH") from None
    return final_path, final_path.with_name(final_path.name + ".part")


def _reject_reparse_path(root: Path, target: Path) -> None:
    try:
        relative = target.relative_to(root)
    except ValueError:
        raise DownloadError("UNSAFE_PATH") from None
    root = root.absolute()
    current = Path(root.anchor)
    components = (*root.parts[1:], *relative.parts)
    for index, component in enumerate(components):
        current = current / component
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise DownloadError("PATH_ACCESS_FAILED") from None
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise DownloadError("UNSAFE_PATH")
        is_target = index == len(components) - 1
        if not is_target and not stat.S_ISDIR(info.st_mode):
            raise DownloadError("PATH_COLLISION")
        if is_target and not stat.S_ISREG(info.st_mode):
            raise DownloadError("PATH_COLLISION")


def _hash_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            total += len(chunk)
            digest.update(chunk)
    return total, digest.hexdigest()


def _matches(path: Path, size: int, digest: str | None) -> bool:
    if not digest or not path.is_file():
        return False
    try:
        actual_size, actual_hash = _hash_file(path)
    except OSError:
        return False
    return actual_size == size and actual_hash == digest


def _validate_remote_ranges(
    path: Path, length: int, ranges: object, *, allow_terminal_eof: bool = False,
) -> bool:
    """Prove complete SHA-256 coverage; opt-in for Telegram's terminal EOF shape.

    For a terminal 128 KiB range advertised beyond EOF, the *remote* digest
    must match SHA-256 of the actual remaining file bytes, not zero padding.
    This behavior is restricted to the explicit product pilot, not S9.
    """
    if (type(length) is not int or length < 0
            or not isinstance(ranges, (tuple, list))
            or type(allow_terminal_eof) is not bool):
        return False
    if length == 0:
        return len(ranges) == 0
    normalized: list[tuple[int, int, bytes]] = []
    for index, item in enumerate(ranges):
        try:
            start, size, raw_digest = item.offset, item.limit, item.sha256
        except AttributeError:
            try:
                start, size, raw_digest = item
            except (TypeError, ValueError):
                return False
        if type(start) is not int or type(size) is not int or start < 0 or size <= 0:
            return False
        end = start + size
        if end <= start:
            return False
        if end > length and not (
            allow_terminal_eof and index == len(ranges) - 1
            and start < length and size == 128 * 1024
            and start % (128 * 1024) == 0 and end - length < 128 * 1024
        ):
            return False
        if isinstance(raw_digest, str):
            try:
                digest_bytes = bytes.fromhex(raw_digest)
            except ValueError:
                return False
        elif isinstance(raw_digest, bytes):
            digest_bytes = raw_digest
        else:
            return False
        if len(digest_bytes) != hashlib.sha256().digest_size:
            return False
        normalized.append((start, min(end, length), digest_bytes))
    normalized.sort(key=lambda item: (item[0], item[1]))
    cursor = 0
    try:
        if allow_terminal_eof and (path.is_symlink() or path.stat().st_size != length):
            return False
        with path.open("rb") as source:
            for start, end, expected_hash in normalized:
                if start != cursor:
                    return False
                source.seek(start)
                digest = hashlib.sha256()
                remaining = end - start
                while remaining:
                    block = source.read(min(CHUNK_BYTES, remaining))
                    if not block:
                        return False
                    digest.update(block)
                    remaining -= len(block)
                if digest.digest() != expected_hash:
                    return False
                cursor = end
        if allow_terminal_eof and path.stat().st_size != length:
            return False
    except OSError:
        return False
    return cursor == length


def _remote_digest(raw_digest: object) -> bytes | None:
    if isinstance(raw_digest, str):
        try:
            digest = bytes.fromhex(raw_digest)
        except ValueError:
            return None
    elif isinstance(raw_digest, bytes):
        digest = raw_digest
    else:
        return None
    return digest if len(digest) == hashlib.sha256().digest_size else None


def _finalize_no_overwrite(partial: Path, final: Path) -> None:
    try:
        if os.name == "nt":
            # Windows MoveFile semantics are same-volume atomic and fail if
            # the destination already exists; os.replace would overwrite it.
            os.rename(partial, final)
        else:
            os.link(partial, final)
            partial.unlink()
    except FileExistsError:
        raise DownloadError("DESTINATION_EXISTS") from None
    except OSError:
        raise DownloadError("ATOMIC_FINALIZATION_FAILED") from None


class SingleMediaDownloadApplication:
    def __init__(
        self, repository: DownloadRepository, gateway: DownloadGateway,
        download_root: str | Path, *, chunk_bytes: int = CHUNK_BYTES,
        progress_callback: Callable[[int, int], None] | None = None,
        chunk_callback: Callable[[int], None] | None = None,
        free_space: Callable[[Path], int] | None = None,
        prefix_proof_observer: Callable[[S6PrefixProofObservation], None] | None = None,
        traffic_observer: Callable[[str, int], None] | None = None,
        require_full_remote_hash: bool = False,
        allow_prefix_terminal_eof: bool = False,
    ) -> None:
        if type(chunk_bytes) is not int or not 0 < chunk_bytes <= CHUNK_BYTES:
            raise ValueError("chunk_bytes must be between 1 and 256 KiB")
        self.repository = repository
        self.gateway = gateway
        self.download_root = Path(download_root)
        self.chunk_bytes = chunk_bytes
        self.progress_callback = progress_callback
        self.chunk_callback = chunk_callback
        self.free_space = free_space or (lambda path: shutil.disk_usage(path).free)
        self.prefix_proof_observer = prefix_proof_observer
        self.traffic_observer = traffic_observer
        if type(require_full_remote_hash) is not bool:
            raise ValueError("require_full_remote_hash must be boolean")
        if type(allow_prefix_terminal_eof) is not bool or (
            allow_prefix_terminal_eof and not require_full_remote_hash
        ):
            raise ValueError("allow_prefix_terminal_eof requires strict remote hashes")
        self.require_full_remote_hash = require_full_remote_hash
        self.allow_prefix_terminal_eof = allow_prefix_terminal_eof
        self.chunk_reserver: Callable[[int], Awaitable[ChunkReservation | None]] | None = None
        self.operation_reserver: Callable[[int], Awaitable[object | None]] | None = None
        self.pre_append_check: Callable[[int], Awaitable[bool]] | None = None

    def _observe_traffic(self, kind: str, byte_count: int) -> None:
        if self.traffic_observer is not None:
            try:
                self.traffic_observer(kind, byte_count)
            except Exception:
                pass

    async def download(
        self, channel_id: int, message_id: int, media_ordinal: int, *,
        integrity_mode: str = "REMOTE_HASH_REQUIRED", plan_id: str | None = None,
        invocation_id: str | None = None, reference_manifest_path: str | Path | None = None,
    ) -> DownloadOutcome:
        if integrity_mode not in {"REMOTE_HASH_REQUIRED", "OPERATIONAL_ONLY", "TRUSTED_REFERENCE"}:
            raise DownloadError("INVALID_INTEGRITY_MODE")
        if integrity_mode != "REMOTE_HASH_REQUIRED" and not V2_EFFECTIVE:
            # Keep the feature dark even when a user or inherited config selects it.
            raise DownloadError("V2_INACTIVE")
        await self.repository.migrate()
        candidate = await self.repository.select_candidate(channel_id, message_id, media_ordinal)
        if candidate is None:
            raise DownloadError("MEDIA_NOT_ELIGIBLE")
        lock = _LOCKS.setdefault(candidate.media_item_id, asyncio.Lock())
        async with lock:
            if integrity_mode != "REMOTE_HASH_REQUIRED":
                invocation_id = invocation_id or uuid.uuid4().hex
                try:
                    attempt_id = await self.repository.record_v2_selection(
                        candidate,
                        selected_mode=integrity_mode,
                        invocation_id=invocation_id,
                        plan_id=plan_id,
                        reference_manifest_path=(
                            str(Path(reference_manifest_path).expanduser().absolute())
                            if reference_manifest_path is not None else None
                        ),
                    )
                except DownloadMediaNotObserved:
                    raise DownloadError("MEDIA_NOT_OBSERVED") from None
                except ValueError:
                    raise DownloadError("RESUME_IDENTITY_MISMATCH") from None
                return await self._download_v2_locked(
                    candidate,
                    integrity_mode=integrity_mode,
                    attempt_id=attempt_id,
                    plan_id=plan_id,
                    invocation_id=invocation_id,
                    reference_manifest_path=reference_manifest_path,
                )
            return await self._download_locked(candidate)

    async def _download_locked(self, candidate: DownloadCandidate) -> DownloadOutcome:
        try:
            await self.repository.assert_candidate_identity(candidate)
        except DownloadMediaNotObserved:
            raise DownloadError("MEDIA_NOT_OBSERVED") from None
        except ValueError:
            raise DownloadError("RESUME_IDENTITY_MISMATCH") from None
        final, partial = destination_paths(self.download_root, candidate)
        _reject_reparse_path(self.download_root.absolute(), final)
        _reject_reparse_path(self.download_root.absolute(), partial)

        async def assert_persisted_identity() -> None:
            try:
                await self.repository.assert_download_identity(candidate)
            except DownloadMediaNotObserved:
                raise DownloadError("MEDIA_NOT_OBSERVED") from None
            except ValueError:
                raise DownloadError("RESUME_IDENTITY_MISMATCH") from None

        record = await self.repository.get_record(candidate.media_item_id)
        if record is not None and record.state == "COMPLETED_V2":
            raise DownloadError("UNKNOWN_LEGACY")
        if (
            record is not None
            and record.state in {"DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING"}
            and record.owner_pid != os.getpid()
            and _process_is_alive(record.owner_pid) is not False
        ):
            raise DownloadError("TRANSFER_IN_PROGRESS")
        if (
            record is not None
            and record.state == "FAILED_RETRYABLE"
            and record.owner_pid is not None
            and _process_is_alive(record.owner_pid) is not False
        ):
            raise DownloadError("TRANSFER_IN_PROGRESS")
        if record is not None and record.final_path is not None and record.final_path != str(final):
            raise DownloadError("DOWNLOAD_ROOT_CHANGED")
        if record is not None and record.state in {"DOWNLOADED", "VALIDATED", "FINALIZATION_PENDING"}:
            await assert_persisted_identity()
        if record is not None and record.state == "DOWNLOADED":
            if record.final_path == str(final) and _matches(final, candidate.expected_bytes, record.sha256):
                await assert_persisted_identity()
                return DownloadOutcome("ALREADY_DOWNLOADED", candidate, final, candidate.expected_bytes, record.sha256)
            if final.exists():
                raise DownloadError("DOWNLOADED_FILE_MISMATCH")
            await self.repository.transition(
                candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=0,
                failure_category="FINAL_FILE_MISSING",
            )
            record = await self.repository.get_record(candidate.media_item_id)
        if record is not None and record.state in {"VALIDATED", "FINALIZATION_PENDING"} and record.final_path == str(final):
            if _matches(final, candidate.expected_bytes, record.sha256):
                await assert_persisted_identity()
                await self.repository.transition(candidate.media_item_id, "DOWNLOADED", downloaded_bytes=candidate.expected_bytes)
                return DownloadOutcome("RECOVERED", candidate, final, candidate.expected_bytes, record.sha256)
            if final.exists():
                raise DownloadError("FINALIZATION_FILE_MISMATCH")
        if final.exists():
            raise DownloadError("DESTINATION_EXISTS")
        part_exists = partial.exists()
        if part_exists:
            if (
                record is None or record.partial_path != str(partial)
                or record.final_path != str(final) or partial.is_symlink()
                or not partial.is_file()
            ):
                raise DownloadError("UNOWNED_PARTIAL_EXISTS")
        physical = partial.stat().st_size if part_exists else 0
        if type(candidate.expected_bytes) is not int:
            raise DownloadError("UNKNOWN_SIZE")
        if physical > candidate.expected_bytes:
            raise DownloadError("PARTIAL_SIZE_EXCEEDED")
        if self.pre_append_check is None:
            # S5 queue runs install a batch reservation-aware pre-append gate.
            # A direct S4 invocation must still check capacity before claiming
            # state, creating a partial, or requesting transfer payload.
            _assert_disk_capacity(
                self.download_root,
                candidate.expected_bytes - physical,
                self.free_space,
            )
        resuming = part_exists and record is not None
        try:
            final.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise DownloadError("PATH_CREATE_FAILED") from None
        _reject_reparse_path(self.download_root.absolute(), final)
        _reject_reparse_path(self.download_root.absolute(), partial)
        try:
            if resuming:
                await self.repository.start_resume(candidate, final, partial)
            else:
                await self.repository.start(candidate, final, partial)
        except DownloadInProgress:
            raise DownloadError("TRANSFER_IN_PROGRESS") from None
        except DownloadMediaNotObserved:
            raise DownloadError("MEDIA_NOT_OBSERVED") from None
        except ValueError:
            raise DownloadError("RESUME_IDENTITY_MISMATCH") from None

        total = physical
        received = 0
        continuation_received = 0
        try:
            if physical:
                prefix_digest, verification_bytes, proof = await self._verify_prefix(
                    candidate, partial, physical
                )
                received += verification_bytes
            if self.pre_append_check is not None:
                if not await self.pre_append_check(candidate.expected_bytes - physical):
                    raise DownloadError("INSUFFICIENT_DISK_SPACE")
            if physical:
                claimed = await self.repository.get_record(candidate.media_item_id)
                if (
                    partial.is_symlink() or not partial.is_file()
                    or claimed is None or claimed.state != "DOWNLOADING"
                    or claimed.owner_pid != os.getpid()
                    or claimed.partial_path != str(partial)
                    or claimed.final_path != str(final)
                    or claimed.expected_bytes != candidate.expected_bytes
                ):
                    raise DownloadError("PARTIAL_CHANGED")
                current_size, current_digest = _hash_file(partial)
                if current_size != physical or current_digest != prefix_digest:
                    raise DownloadError("PARTIAL_CHANGED")
                if self.prefix_proof_observer is not None:
                    try:
                        self.prefix_proof_observer(proof)
                    except Exception:
                        raise DownloadError("PREFIX_PROOF_PERSISTENCE_FAILED") from None

            complete_local_file = (
                self.require_full_remote_hash
                and physical == candidate.expected_bytes
            )
            wire_offset = (
                physical if complete_local_file
                else (physical // CHUNK_BYTES) * CHUNK_BYTES
            )
            overlap_size = 0 if complete_local_file else physical - wire_offset
            overlap = b""
            if overlap_size:
                with partial.open("rb") as source:
                    source.seek(wire_offset)
                    overlap = source.read(overlap_size)
                if len(overlap) != overlap_size:
                    raise DownloadError("PARTIAL_CHANGED")
            overlap_seen = 0
            append_buffer = bytearray()
            if complete_local_file:
                if partial.stat().st_size != candidate.expected_bytes:
                    raise DownloadError("PARTIAL_CHANGED")
            else:
                open_mode = "r+b" if physical else "wb"
                with partial.open(open_mode) as output:
                    if physical:
                        output.seek(0, os.SEEK_END)
                        if output.tell() != physical:
                            raise DownloadError("PARTIAL_CHANGED")
                    stream_kwargs = {
                        "telegram_media_id": candidate.telegram_media_id,
                        "expected_bytes": candidate.expected_bytes,
                    }
                    if wire_offset:
                        stream_kwargs["offset"] = wire_offset
                    stream_kwargs["reserve_chunk"] = self.chunk_reserver or _reserve_unbounded_chunk
                    async for chunk in self.gateway.stream_media(
                        candidate.channel_id, candidate.telegram_message_id, candidate.media_ordinal,
                        **stream_kwargs,
                    ):
                        if not isinstance(chunk, bytes) or not chunk or len(chunk) > self.chunk_bytes:
                            raise DownloadError("INVALID_CHUNK")
                        received += len(chunk)
                        continuation_received += len(chunk)
                        if self.chunk_callback is not None:
                            self.chunk_callback(len(chunk))
                        if wire_offset + continuation_received > candidate.expected_bytes:
                            raise DownloadError("SIZE_EXCEEDED")
                        data = chunk
                        if overlap_seen < overlap_size:
                            compare_count = min(len(data), overlap_size - overlap_seen)
                            self._observe_traffic("overlap", compare_count)
                            append_buffer.extend(data[:compare_count])
                            overlap_seen += compare_count
                            data = data[compare_count:]
                            if overlap_seen == overlap_size:
                                if bytes(append_buffer) != overlap:
                                    raise DownloadError("OVERLAP_MISMATCH")
                                append_buffer.clear()
                        if data:
                            if overlap_seen != overlap_size:
                                raise DownloadError("OVERLAP_INCOMPLETE")
                            output.write(data)
                            output.flush()
                            os.fsync(output.fileno())
                            total += len(data)
                            await self.repository.checkpoint(candidate.media_item_id, total)
                        if self.progress_callback is not None and (
                            total == candidate.expected_bytes or total % (1024 * 1024) < len(chunk)
                        ):
                            self.progress_callback(total, candidate.expected_bytes)
                    if overlap_seen != overlap_size:
                        raise DownloadError("OVERLAP_INCOMPLETE")
                    output.flush()
                    os.fsync(output.fileno())
            physical = partial.stat().st_size
            if physical != candidate.expected_bytes:
                raise DownloadError("SIZE_MISMATCH")
            local_size, local_hash = _hash_file(partial)
            if local_size != candidate.expected_bytes:
                raise DownloadError("SIZE_MISMATCH")
            if (resuming or self.require_full_remote_hash) and not _validate_remote_ranges(
                partial, candidate.expected_bytes,
                await self._remote_hashes(
                    candidate, candidate.expected_bytes,
                    allow_terminal_eof=self.require_full_remote_hash,
                ),
                allow_terminal_eof=self.require_full_remote_hash,
            ):
                raise DownloadError(
                    "CONTINUATION_INTEGRITY_MISMATCH" if resuming
                    else "REMOTE_HASH_FULL_REQUIRED"
                )
            await self.repository.transition(candidate.media_item_id, "VALIDATED", downloaded_bytes=total, sha256=local_hash)
            await self.repository.transition(candidate.media_item_id, "FINALIZATION_PENDING", downloaded_bytes=total)
            if final.exists():
                raise DownloadError("DESTINATION_EXISTS")
            _finalize_no_overwrite(partial, final)
            if not _matches(final, candidate.expected_bytes, local_hash):
                raise DownloadError("FINAL_FILE_MISMATCH")
            await self.repository.transition(candidate.media_item_id, "DOWNLOADED", downloaded_bytes=total)
            return DownloadOutcome(
                "DOWNLOADED", candidate, final, received, local_hash,
                remote_hash_class="REMOTE_HASH_FULL" if self.require_full_remote_hash else None,
                guarantee="REMOTE_HASH_FULL" if self.require_full_remote_hash else None,
            )
        except asyncio.CancelledError:
            await self._record_failure_state(candidate, partial, total, "CANCELLED")
            raise
        except DownloadError as error:
            await self._record_failure_state(
                candidate, partial, total, error.category
            )
            raise
        except DownloadGatewayError as error:
            await self._record_failure_state(
                candidate, partial, total, error.category
            )
            error_out = DownloadError(
                error.category, retry_after_seconds=error.retry_after_seconds
            )
            raise error_out from None
        except Exception:
            if total == candidate.expected_bytes:
                candidate_path = final if final.exists() else partial
                try:
                    _candidate_size, candidate_hash = _hash_file(candidate_path)
                except OSError:
                    candidate_hash = None
                if candidate_hash and _matches(final, candidate.expected_bytes, candidate_hash):
                    raise DownloadError("STATE_COMMIT_PENDING") from None
            await self._record_failure_state(
                candidate, partial, total, "TRANSFER_FAILED"
            )
            raise DownloadError("TRANSFER_FAILED") from None

    async def _record_failure_state(
        self,
        candidate: DownloadCandidate,
        partial: Path,
        total: int,
        category: str,
    ) -> None:
        safe_category = _safe_error_category(category)
        try:
            checkpoint_saved = await self._preserve_checkpoint(
                candidate, partial, total
            )
            if not checkpoint_saved:
                emit_operational_event(
                    "download_cleanup_failed",
                    component="download",
                    level=logging.WARNING,
                    category=safe_category,
                    state="CHECKPOINT",
                )
        except asyncio.CancelledError:
            emit_operational_event(
                "download_cleanup_cancelled",
                component="download",
                level=logging.WARNING,
                category=safe_category,
                state="CHECKPOINT",
            )
        except Exception:
            emit_operational_event(
                "download_cleanup_failed",
                component="download",
                level=logging.WARNING,
                category=safe_category,
                state="CHECKPOINT",
            )
        try:
            await self.repository.transition(
                candidate.media_item_id,
                "FAILED_RETRYABLE",
                downloaded_bytes=total,
                failure_category=safe_category,
            )
        except asyncio.CancelledError:
            emit_operational_event(
                "download_cleanup_cancelled",
                component="download",
                level=logging.WARNING,
                category=safe_category,
                state="FAILED_RETRYABLE",
            )
        except Exception:
            emit_operational_event(
                "download_cleanup_failed",
                component="download",
                level=logging.WARNING,
                category=safe_category,
                state="FAILED_RETRYABLE",
            )

    async def _download_v2_locked(
        self,
        candidate: DownloadCandidate,
        *,
        integrity_mode: str,
        attempt_id: str,
        plan_id: str | None,
        invocation_id: str,
        reference_manifest_path: str | Path | None,
    ) -> DownloadOutcome:
        """Execute an explicitly selected V2 mode; callers cannot enable V2 via config."""
        final, partial = destination_paths(self.download_root, candidate)
        _reject_reparse_path(self.download_root.absolute(), final)
        _reject_reparse_path(self.download_root.absolute(), partial)
        record = await self.repository.get_record(candidate.media_item_id)
        if record is not None and record.state == "COMPLETED_V2":
            try:
                await self.repository.assert_download_identity(candidate)
            except DownloadMediaNotObserved:
                raise DownloadError("MEDIA_NOT_OBSERVED") from None
            except ValueError:
                raise DownloadError("RESUME_IDENTITY_MISMATCH") from None
            try:
                evidence = await self.repository.get_v2_evidence(candidate.media_item_id)
            except (KeyError, ValueError):
                raise DownloadError("UNKNOWN_LEGACY") from None
            if not evidence or not self._v2_evidence_matches(evidence, candidate, final):
                raise DownloadError("UNKNOWN_LEGACY")
            if evidence["selected_mode"] != integrity_mode:
                raise DownloadError("MODE_SELECTION_MISMATCH")
            if not _matches(final, candidate.expected_bytes, str(evidence["final_sha256"])):
                raise DownloadError("COMPLETED_V2_FILE_MISMATCH")
            return DownloadOutcome(
                "ALREADY_COMPLETED_V2", candidate, final, 0,
                str(evidence["final_sha256"]), integrity_mode,
                str(evidence["evidence_class"]), str(evidence["remote_hash_class"]),
                "UNVERIFIED_ORIGIN" if integrity_mode == "OPERATIONAL_ONLY" else "REFERENCE_MATCH",
            )
        if record is not None and record.state == "DOWNLOADED":
            raise DownloadError("UNKNOWN_LEGACY")
        if record is not None and record.state in {
            "DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING"
        } and record.owner_pid != os.getpid() and _process_is_alive(record.owner_pid) is not False:
            raise DownloadError("TRANSFER_IN_PROGRESS")
        if record is not None and record.final_path is not None and record.final_path != str(final):
            raise DownloadError("DOWNLOAD_ROOT_CHANGED")
        reference = None
        pool = None
        requests = 0
        received = 0
        total_reserve = 0
        remote_class: str | None = None

        async def close_pool() -> None:
            nonlocal pool
            if pool is not None:
                current_pool = pool
                pool = None
                await current_pool.close()

        def warn_v2_cleanup(category: str, state: str) -> None:
            try:
                emit_operational_event(
                    "download_cleanup_failed",
                    component="download",
                    level=logging.WARNING,
                    category=_safe_error_category(category),
                    state=state,
                )
            except Exception:
                # Cleanup diagnostics must never replace the primary outcome.
                pass

        async def best_effort_v2_cleanup(
            action: Callable[[], Awaitable[object]],
            *,
            category: str,
            state: str,
        ) -> None:
            try:
                outcome = await action()
                if outcome is False:
                    warn_v2_cleanup(category, state)
            except asyncio.CancelledError:
                warn_v2_cleanup(category, f"{state}_CANCELLED")
            except Exception:
                warn_v2_cleanup(category, state)

        try:
            if integrity_mode == "TRUSTED_REFERENCE":
                if reference_manifest_path is None:
                    raise DownloadError("REFERENCE_ABSENT")
                try:
                    reference = load_reference(
                        reference_manifest_path,
                        channel_id=candidate.channel_id,
                        telegram_message_id=candidate.telegram_message_id,
                        media_ordinal=candidate.media_ordinal,
                        telegram_media_id=candidate.telegram_media_id,
                        expected_bytes=candidate.expected_bytes,
                    )
                except (OSError, ValueError) as error:
                    category = (
                        "REFERENCE_PROVENANCE_UNVERIFIED"
                        if "provenance" in str(error).casefold()
                        else "REFERENCE_INVALID"
                    )
                    raise DownloadError(category) from None

            current = await self.repository.select_candidate(
                candidate.channel_id, candidate.telegram_message_id, candidate.media_ordinal
            )
            if current is None or (
                current.media_item_id != candidate.media_item_id
                or current.telegram_media_id != candidate.telegram_media_id
                or current.expected_bytes != candidate.expected_bytes
            ):
                raise DownloadError("REMOTE_IDENTITY_CONFLICT")
            if final.exists():
                prior = await self.repository.get_latest_v2_attempt(
                    candidate.media_item_id, exclude_attempt_id=attempt_id
                )
                try:
                    prior_details = json.loads(prior["details_json"]) if prior else {}
                except (TypeError, json.JSONDecodeError):
                    prior_details = {}
                identity = prior_details.get("identity", {}) if isinstance(prior_details, dict) else {}
                prior_sha = prior_details.get("final_sha256") if isinstance(prior_details, dict) else None
                if (
                    prior is None or prior["status"] != "EVIDENCE_READY"
                    or prior["selected_mode"] != integrity_mode
                    or identity != {
                        "channel_id": candidate.channel_id,
                        "telegram_message_id": candidate.telegram_message_id,
                        "media_ordinal": candidate.media_ordinal,
                        "telegram_media_id": candidate.telegram_media_id,
                    }
                    or prior_details.get("expected_bytes") != candidate.expected_bytes
                    or not isinstance(prior_sha, str)
                    or not _matches(final, candidate.expected_bytes, prior_sha)
                ):
                    raise DownloadError("FINALIZATION_RECOVERY_REQUIRES_EVIDENCE")
                if reference is not None and (
                    prior_details.get("reference_manifest_sha256") != reference.manifest_sha256
                    or not files_equal(final, reference.path)
                    or not reference_unchanged(reference)
                ):
                    raise DownloadError("REFERENCE_INVALID")
                evidence_class = str(prior["evidence_class"] or "")
                remote_class = str(prior["remote_hash_class"] or "REMOTE_HASH_ABSENT")
                await self.repository.complete_v2(
                    candidate, attempt_id=str(prior["id"]), final_path=final,
                    sha256=prior_sha, evidence_class=evidence_class,
                    remote_hash_class=remote_class, details=prior_details,
                )
                await self.repository.update_v2_attempt(
                    attempt_id, status="RECOVERED",
                    details={"recovered_from_attempt": str(prior["id"]), "mode": integrity_mode},
                    remote_hash_class=remote_class, evidence_class=evidence_class,
                )
                return DownloadOutcome(
                    "RECOVERED_V2", candidate, final, 0, prior_sha, integrity_mode,
                    evidence_class, remote_class,
                    "UNVERIFIED_ORIGIN" if integrity_mode == "OPERATIONAL_ONLY" else "REFERENCE_MATCH",
                )

            part_exists = partial.exists()
            if part_exists and (
                record is None or record.partial_path != str(partial)
                or record.final_path != str(final) or partial.is_symlink()
                or not partial.is_file()
            ):
                raise DownloadError("UNOWNED_PARTIAL_EXISTS")
            physical = partial.stat().st_size if part_exists else 0
            if physical > candidate.expected_bytes:
                raise DownloadError("PREFIX_CONFLICT")
            resuming = part_exists and record is not None
            wire_offset = (physical // CHUNK_BYTES) * CHUNK_BYTES
            overlap_bytes = physical - wire_offset
            reuse_boundary_response = (
                integrity_mode == "OPERATIONAL_ONLY"
                and overlap_bytes > 0
                and physical < candidate.expected_bytes
            )
            transfer_offset = (
                min(candidate.expected_bytes, wire_offset + CHUNK_BYTES)
                if reuse_boundary_response else wire_offset
            )
            prefix_reserve = (
                ((physical + CHUNK_BYTES - 1) // CHUNK_BYTES) * CHUNK_BYTES
                if integrity_mode == "OPERATIONAL_ONLY" and physical else 0
            )
            transfer_bytes = (
                candidate.expected_bytes - transfer_offset
                if physical < candidate.expected_bytes else 0
            )
            transfer_reserve = (
                ((transfer_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES) * CHUNK_BYTES
                if transfer_bytes else 0
            )
            total_reserve = prefix_reserve + transfer_reserve
            if self.operation_reserver is not None and total_reserve:
                pool = await self.operation_reserver(total_reserve)
                if pool is None:
                    raise DownloadError("BUDGET_BLOCK")
            reserve_chunk = (
                getattr(pool, "reserve_chunk") if pool is not None
                else self.chunk_reserver or _reserve_unbounded_chunk
            )

            validator = getattr(self.gateway, "validate_media_identity", None)
            if not callable(validator):
                raise DownloadError("IDENTITY_REVALIDATION_UNAVAILABLE")
            if await validator(
                candidate.channel_id, candidate.telegram_message_id, candidate.media_ordinal,
                telegram_media_id=candidate.telegram_media_id,
                expected_bytes=candidate.expected_bytes,
            ) is not True:
                raise DownloadError("REMOTE_IDENTITY_CONFLICT")
            requests += 1

            if self.pre_append_check is not None and not await self.pre_append_check(
                candidate.expected_bytes - physical
            ):
                raise DownloadError("INSUFFICIENT_DISK_SPACE")
            final.parent.mkdir(parents=True, exist_ok=True)
            _reject_reparse_path(self.download_root.absolute(), final)
            _reject_reparse_path(self.download_root.absolute(), partial)
            try:
                if resuming:
                    await self.repository.start_resume(candidate, final, partial)
                else:
                    await self.repository.start(candidate, final, partial)
            except DownloadInProgress:
                raise DownloadError("TRANSFER_IN_PROGRESS") from None
            except ValueError:
                raise DownloadError("RESUME_IDENTITY_MISMATCH") from None

            total = physical
            remote_class = "REMOTE_HASH_ABSENT"
            try:
                reused_suffix = b""
                if integrity_mode == "OPERATIONAL_ONLY" and physical:
                    compared = 0
                    prefix_stream = self.gateway.stream_media(
                        candidate.channel_id, candidate.telegram_message_id,
                        candidate.media_ordinal, telegram_media_id=candidate.telegram_media_id,
                        expected_bytes=candidate.expected_bytes, offset=0,
                        reserve_chunk=reserve_chunk,
                    )
                    try:
                        with partial.open("rb") as local:
                            async for chunk in prefix_stream:
                                requests += 1
                                if not isinstance(chunk, bytes) or not chunk or len(chunk) > CHUNK_BYTES:
                                    raise DownloadError("REMOTE_PREFIX_INCOMPLETE")
                                received += len(chunk)
                                if self.chunk_callback is not None:
                                    self.chunk_callback(len(chunk))
                                chunk_offset = compared
                                count = min(len(chunk), physical - compared)
                                expected = local.read(count)
                                if len(expected) != count or expected != chunk[:count]:
                                    raise DownloadError("PREFIX_CONFLICT")
                                compared += count
                                if compared == physical:
                                    if reuse_boundary_response:
                                        expected_response_bytes = min(
                                            CHUNK_BYTES,
                                            candidate.expected_bytes - wire_offset,
                                        )
                                        if (
                                            chunk_offset != wire_offset
                                            or len(chunk) != expected_response_bytes
                                            or count >= len(chunk)
                                        ):
                                            raise DownloadError("REMOTE_PREFIX_INCOMPLETE")
                                        reused_suffix = chunk[count:]
                                    break
                    finally:
                        close = getattr(prefix_stream, "aclose", None)
                        if callable(close):
                            await close()
                    if compared != physical:
                        raise DownloadError("REMOTE_PREFIX_INCOMPLETE")
                    if reuse_boundary_response and not reused_suffix:
                        raise DownloadError("REMOTE_PREFIX_INCOMPLETE")
                    prefix_size, prefix_sha256 = _hash_file(partial)
                    if prefix_size != physical or partial.stat().st_size != physical:
                        raise DownloadError("CHECKPOINT_INCONSISTENT")
                    claimed = await self.repository.get_record(candidate.media_item_id)
                    if (
                        partial.is_symlink() or not partial.is_file() or claimed is None
                        or claimed.state != "DOWNLOADING" or claimed.owner_pid != os.getpid()
                        or claimed.partial_path != str(partial) or claimed.final_path != str(final)
                        or claimed.expected_bytes != candidate.expected_bytes
                    ):
                        raise DownloadError("CHECKPOINT_INCONSISTENT")

                stream_offset = wire_offset
                stream_overlap_bytes = overlap_bytes
                if reused_suffix:
                    if physical + len(reused_suffix) != transfer_offset:
                        raise DownloadError("REMOTE_PREFIX_INCOMPLETE")
                    with partial.open("r+b") as output:
                        output.seek(0, os.SEEK_END)
                        if output.tell() != physical:
                            raise DownloadError("CHECKPOINT_INCONSISTENT")
                        output.write(reused_suffix)
                        output.flush()
                        os.fsync(output.fileno())
                    total += len(reused_suffix)
                    await self.repository.checkpoint(candidate.media_item_id, total)
                    stream_offset = transfer_offset
                    stream_overlap_bytes = 0

                overlap = b""
                if stream_overlap_bytes:
                    with partial.open("rb") as source:
                        source.seek(stream_offset)
                        overlap = source.read(stream_overlap_bytes)
                    if len(overlap) != stream_overlap_bytes:
                        raise DownloadError("CHECKPOINT_INCONSISTENT")
                overlap_seen = 0
                overlap_buffer = bytearray()
                continuation_received = 0
                if physical < candidate.expected_bytes and stream_offset < candidate.expected_bytes:
                    with partial.open("r+b" if physical else "wb") as output:
                        output.seek(0, os.SEEK_END)
                        # Reusing the aligned response suffix may already have
                        # advanced the durable checkpoint beyond the original
                        # physical prefix. Keep `physical` unchanged for prefix
                        # evidence, and validate the append cursor against the
                        # current tracked total.
                        if output.tell() != total:
                            raise DownloadError("CHECKPOINT_INCONSISTENT")
                        stream = self.gateway.stream_media(
                            candidate.channel_id, candidate.telegram_message_id,
                            candidate.media_ordinal, telegram_media_id=candidate.telegram_media_id,
                            expected_bytes=candidate.expected_bytes, offset=stream_offset,
                            reserve_chunk=reserve_chunk,
                        )
                        try:
                            async for chunk in stream:
                                requests += 1
                                if not isinstance(chunk, bytes) or not chunk or len(chunk) > CHUNK_BYTES:
                                    raise DownloadError("INVALID_CHUNK")
                                received += len(chunk)
                                continuation_received += len(chunk)
                                if self.chunk_callback is not None:
                                    self.chunk_callback(len(chunk))
                                if stream_offset + continuation_received > candidate.expected_bytes:
                                    raise DownloadError("SIZE_EXCEEDED")
                                data = chunk
                                if overlap_seen < stream_overlap_bytes:
                                    count = min(len(data), stream_overlap_bytes - overlap_seen)
                                    self._observe_traffic("overlap", count)
                                    overlap_buffer.extend(data[:count])
                                    overlap_seen += count
                                    data = data[count:]
                                    if overlap_seen == stream_overlap_bytes:
                                        if bytes(overlap_buffer) != overlap:
                                            raise DownloadError("PREFIX_CONFLICT")
                                        overlap_buffer.clear()
                                if data:
                                    if overlap_seen != stream_overlap_bytes:
                                        raise DownloadError("OVERLAP_INCOMPLETE")
                                    output.write(data)
                                    output.flush()
                                    os.fsync(output.fileno())
                                    total += len(data)
                                    await self.repository.checkpoint(candidate.media_item_id, total)
                        finally:
                            close = getattr(stream, "aclose", None)
                            if callable(close):
                                await close()
                        if overlap_seen != stream_overlap_bytes:
                            raise DownloadError("OVERLAP_INCOMPLETE")
                        output.flush()
                        os.fsync(output.fileno())
                total = partial.stat().st_size
                if total != candidate.expected_bytes:
                    raise DownloadError("SIZE_MISMATCH")
                local_size, local_hash = _hash_file(partial)
                if local_size != candidate.expected_bytes:
                    raise DownloadError("SIZE_MISMATCH")

                if integrity_mode == "TRUSTED_REFERENCE":
                    if reference is None or not reference_unchanged(reference):
                        raise DownloadError("REFERENCE_INVALID")
                    if not files_equal(partial, reference.path):
                        raise DownloadError("REFERENCE_MISMATCH")
                    if local_size != reference.size or local_hash != reference.sha256:
                        raise DownloadError("REFERENCE_MISMATCH")
                    if not reference_unchanged(reference):
                        raise DownloadError("REFERENCE_INVALID")

                # Revalidate metadata before finalization; the Telethon adapter also
                # validates it before every GetFile/GetFileHashes request.
                if await validator(
                    candidate.channel_id, candidate.telegram_message_id, candidate.media_ordinal,
                    telegram_media_id=candidate.telegram_media_id,
                    expected_bytes=candidate.expected_bytes,
                ) is not True:
                    raise DownloadError("REMOTE_IDENTITY_CONFLICT")
                requests += 1
                if reference is not None and not reference_unchanged(reference):
                    raise DownloadError("REFERENCE_INVALID")

                remote_class = "REMOTE_HASH_ABSENT"
                remote_events: tuple[dict[str, object], ...] = ()
                getter = getattr(self.gateway, "get_file_hashes", None)
                if not callable(getter):
                    assessment = assess_remote_hashes(
                        partial, candidate.expected_bytes, None, method_absent=True
                    )
                else:
                    collected: list[RemoteFileHash] = []
                    cursor = 0
                    call_limit = max(1, (candidate.expected_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES + 1)
                    unavailable = False
                    invalid_gateway_response = False
                    hash_failure: DownloadError | None = None
                    for _ in range(call_limit):
                        try:
                            page = await getter(
                                candidate.channel_id, candidate.telegram_message_id,
                                candidate.media_ordinal, telegram_media_id=candidate.telegram_media_id,
                                expected_bytes=candidate.expected_bytes, offset=cursor,
                            )
                            requests += 1
                        except DownloadGatewayError as error:
                            if error.category in {
                                "RATE_LIMITED", "NETWORK", "GATEWAY_FAILURE", "TRANSFER_FAILED"
                            }:
                                unavailable = True
                                category = (
                                    "REMOTE_HASH_UNAVAILABLE"
                                    if error.category in {"NETWORK", "GATEWAY_FAILURE", "TRANSFER_FAILED"}
                                    else error.category
                                )
                                hash_failure = DownloadError(
                                    category,
                                    retry_after_seconds=error.retry_after_seconds,
                                    failure_phase="REMOTE_HASH",
                                )
                                break
                            if error.category in {"INVALID_HASH_RESPONSE", "REMOTE_HASH_RESPONSE_INVALID"}:
                                invalid_gateway_response = True
                            else:
                                unavailable = True
                            break
                        except Exception:
                            unavailable = True
                            hash_failure = DownloadError(
                                "REMOTE_HASH_UNAVAILABLE", failure_phase="REMOTE_HASH"
                            )
                            break
                        if not isinstance(page, (tuple, list)):
                            invalid_gateway_response = True
                            break
                        if not page:
                            break
                        max_end = cursor
                        for item in page:
                            try:
                                start, limit, raw = item.offset, item.limit, item.sha256
                            except AttributeError:
                                try:
                                    start, limit, raw = item
                                except (TypeError, ValueError):
                                    collected.append(("invalid", 0, b""))
                                    continue
                            collected.append(RemoteFileHash(start, limit, raw))
                            if type(start) is int and type(limit) is int and start >= 0 and limit > 0:
                                max_end = max(max_end, start + limit)
                        if max_end <= cursor:
                            break
                        cursor = max_end
                        if cursor >= candidate.expected_bytes:
                            break
                    hash_responses: list[object] = list(collected)
                    if invalid_gateway_response:
                        hash_responses.append(("invalid", 0, b""))
                    assessment = assess_remote_hashes(
                        partial, candidate.expected_bytes, tuple(hash_responses),
                        unavailable=unavailable,
                    )
                remote_class = assessment.primary
                remote_events = assessment.events
                if assessment.blocking:
                    if hash_failure is not None and remote_class == "REMOTE_HASH_UNAVAILABLE":
                        raise DownloadError(
                            hash_failure.category,
                            retry_after_seconds=hash_failure.retry_after_seconds,
                            failure_phase="REMOTE_HASH",
                            remote_hash_events=remote_events,
                        )
                    raise DownloadError(
                        remote_class, failure_phase="REMOTE_HASH",
                        remote_hash_events=remote_events,
                    )

                evidence_class = (
                    "REFERENCE_MATCH" if integrity_mode == "TRUSTED_REFERENCE"
                    else "OPERATIONAL_ONLY"
                )
                if integrity_mode == "OPERATIONAL_ONLY" and physical and prefix_size != physical:
                    raise DownloadError("CHECKPOINT_INCONSISTENT")
                details: dict[str, object] = {
                    "schema_version": 1,
                    "contract_version": 2,
                    "evidence_version": 1,
                    "selected_mode": integrity_mode,
                    "evidence_classes": [evidence_class],
                    "remote_hash_class": remote_class,
                    "remote_hash_events": list(remote_events),
                    "identity": {
                        "channel_id": candidate.channel_id,
                        "telegram_message_id": candidate.telegram_message_id,
                        "media_ordinal": candidate.media_ordinal,
                        "telegram_media_id": candidate.telegram_media_id,
                    },
                    "expected_bytes": candidate.expected_bytes,
                    "final_sha256": local_hash,
                    "plan_id": plan_id,
                    "invocation_id": invocation_id,
                    "prefix_bytes": physical,
                    "prefix_reread_reserved": prefix_reserve,
                    "transfer_reserved": transfer_reserve,
                    "bytes_received": received,
                    "requests": requests,
                    "guarantee": "UNVERIFIED_ORIGIN" if evidence_class == "OPERATIONAL_ONLY" else "REFERENCE_MATCH",
                    "reference_manifest_sha256": reference.manifest_sha256 if reference else None,
                    "reference_provenance": reference.provenance if reference else None,
                    "reference_provenance_state": (
                        "DOCUMENTED_UNATTESTED" if reference else None
                    ),
                }
                await self.repository.update_v2_attempt(
                    attempt_id, status="EVIDENCE_READY", details=details,
                    remote_hash_class=remote_class, evidence_class=evidence_class,
                    requests=requests, bytes_reserved=total_reserve, bytes_received=received,
                )
                await self.repository.transition(
                    candidate.media_item_id, "VALIDATED", downloaded_bytes=total,
                    sha256=local_hash,
                )
                await self.repository.transition(
                    candidate.media_item_id, "FINALIZATION_PENDING", downloaded_bytes=total,
                )
                if final.exists():
                    raise DownloadError("DESTINATION_EXISTS")
                _finalize_no_overwrite(partial, final)
                if not _matches(final, candidate.expected_bytes, local_hash):
                    raise DownloadError("FINAL_FILE_MISMATCH")
                if reference is not None and (
                    not files_equal(final, reference.path) or not reference_unchanged(reference)
                ):
                    raise DownloadError("REFERENCE_INVALID")
                await self.repository.complete_v2(
                    candidate, attempt_id=attempt_id, final_path=final, sha256=local_hash,
                    evidence_class=evidence_class, remote_hash_class=remote_class,
                    details=details,
                )
                return DownloadOutcome(
                    "COMPLETED_V2", candidate, final, received, local_hash,
                    integrity_mode, evidence_class, remote_class,
                    "UNVERIFIED_ORIGIN" if evidence_class == "OPERATIONAL_ONLY" else "REFERENCE_MATCH",
                )
            except asyncio.CancelledError:
                await best_effort_v2_cleanup(
                    lambda: self._preserve_checkpoint(candidate, partial, total),
                    category="CANCELLED",
                    state="CHECKPOINT",
                )
                await best_effort_v2_cleanup(
                    lambda: self.repository.transition(
                        candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=total,
                        failure_category="CANCELLED",
                    ),
                    category="CANCELLED",
                    state="FAILED_RETRYABLE",
                )
                await best_effort_v2_cleanup(
                    lambda: self.repository.update_v2_attempt(
                        attempt_id, status="FAILED_RETRYABLE", details={"reason": "CANCELLED"},
                        requests=requests, bytes_reserved=total_reserve, bytes_received=received,
                    ),
                    category="CANCELLED",
                    state="V2_ATTEMPT",
                )
                raise
            except (DownloadError, DownloadGatewayError) as error:
                category = error.category
                remote_hash_events = tuple(
                    getattr(error, "remote_hash_events", ())
                )
                if category in {"RATE_LIMITED", "NETWORK", "GATEWAY_FAILURE", "TRANSFER_FAILED"}:
                    remote_class = "REMOTE_HASH_UNAVAILABLE"
                await best_effort_v2_cleanup(
                    lambda: self._preserve_checkpoint(candidate, partial, total),
                    category=category,
                    state="CHECKPOINT",
                )
                await best_effort_v2_cleanup(
                    lambda: self.repository.transition(
                        candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=total,
                        failure_category=category,
                    ),
                    category=category,
                    state="FAILED_RETRYABLE",
                )
                await best_effort_v2_cleanup(
                    lambda: self.repository.update_v2_attempt(
                        attempt_id, status="BLOCKED" if category in {
                            "BUDGET_BLOCK", "REMOTE_HASH_DIVERGENT", "REMOTE_HASH_INVALID_RESPONSE",
                            "BLOCKED_CONTRADICTORY_REMOTE_EVIDENCE", "PREFIX_CONFLICT", "REFERENCE_MISMATCH",
                        } else "FAILED_RETRYABLE",
                        details={
                            "reason": category,
                            "remote_hash_class": remote_class,
                            "remote_hash_events": list(remote_hash_events),
                        },
                        remote_hash_class=remote_class if remote_class != "REMOTE_HASH_ABSENT" else None,
                        requests=requests, bytes_reserved=total_reserve, bytes_received=received,
                    ),
                    category=category,
                    state="V2_ATTEMPT",
                )
                if isinstance(error, DownloadGatewayError):
                    raise DownloadError(category, retry_after_seconds=error.retry_after_seconds) from None
                raise
            finally:
                await best_effort_v2_cleanup(
                    close_pool, category="TRANSFER_FAILED", state="POOL_CLOSE"
                )
        except (DownloadError, DownloadGatewayError) as error:
            failure_details: dict[str, object] = {"reason": error.category}
            remote_hash_events = getattr(error, "remote_hash_events", ())
            if remote_hash_events:
                failure_details["remote_hash_events"] = list(remote_hash_events)
                failure_details["remote_hash_class"] = remote_class
            if remote_class is not None and remote_class != "REMOTE_HASH_ABSENT":
                failure_details["remote_hash_class"] = remote_class
            await best_effort_v2_cleanup(
                lambda: self.repository.update_v2_attempt(
                    attempt_id, status="BLOCKED", details=failure_details,
                    remote_hash_class=(
                        remote_class if remote_class != "REMOTE_HASH_ABSENT" else None
                    ),
                    requests=requests, bytes_reserved=total_reserve, bytes_received=received,
                ),
                category=error.category,
                state="V2_ATTEMPT",
            )
            if isinstance(error, DownloadGatewayError):
                raise DownloadError(
                    error.category, retry_after_seconds=error.retry_after_seconds
                ) from None
            raise
        finally:
            await best_effort_v2_cleanup(
                close_pool, category="TRANSFER_FAILED", state="POOL_CLOSE"
            )

    @staticmethod
    def _v2_evidence_matches(
        evidence: dict[str, object], candidate: DownloadCandidate, final: Path
    ) -> bool:
        return (
            evidence.get("channel_id") == candidate.channel_id
            and evidence.get("telegram_message_id") == candidate.telegram_message_id
            and evidence.get("media_ordinal") == candidate.media_ordinal
            and evidence.get("telegram_media_id") == candidate.telegram_media_id
            and evidence.get("expected_bytes") == candidate.expected_bytes
            and evidence.get("final_path") == str(final)
            and evidence.get("schema_version") == 1
            and evidence.get("contract_version") == 2
            and evidence.get("evidence_version") == 1
            and evidence.get("selected_mode") in {"OPERATIONAL_ONLY", "TRUSTED_REFERENCE"}
            and evidence.get("evidence_class") == (
                "OPERATIONAL_ONLY"
                if evidence.get("selected_mode") == "OPERATIONAL_ONLY"
                else "REFERENCE_MATCH"
            )
            and evidence.get("remote_hash_class") in {
                "REMOTE_HASH_FULL", "REMOTE_HASH_PARTIAL", "REMOTE_HASH_ABSENT",
                "REMOTE_HASH_UNVERIFIABLE_EOF",
            }
            and isinstance(evidence.get("final_sha256"), str)
            and len(str(evidence.get("final_sha256"))) == 64
            and all(char in "0123456789abcdef" for char in str(evidence.get("final_sha256")))
        )

    async def _remote_hashes(
        self, candidate: DownloadCandidate, required_bytes: int, *,
        allow_terminal_eof: bool = False,
        allow_prefix_terminal_eof: bool = False,
        prefix_proof: bool = False,
    ) -> tuple[RemoteFileHash, ...]:
        getter = getattr(self.gateway, "get_file_hashes", None)
        if not callable(getter):
            raise DownloadError("REMOTE_HASHES_UNAVAILABLE")
        if required_bytes == 0:
            return ()
        collected: list[RemoteFileHash] = []
        cursor = 0
        while cursor < required_bytes:
            try:
                ranges = await getter(
                    candidate.channel_id, candidate.telegram_message_id,
                    candidate.media_ordinal,
                    telegram_media_id=candidate.telegram_media_id,
                    expected_bytes=candidate.expected_bytes,
                    offset=cursor,
                )
            except DownloadGatewayError as error:
                raise DownloadError(error.category, retry_after_seconds=error.retry_after_seconds) from None
            except Exception:
                raise DownloadError("REMOTE_HASHES_UNAVAILABLE") from None
            if not isinstance(ranges, (tuple, list)) or not ranges:
                raise DownloadError("REMOTE_HASHES_INCOMPLETE")
            end = cursor
            for index, item in enumerate(ranges):
                try:
                    start, size, raw_digest = item.offset, item.limit, item.sha256
                except AttributeError:
                    try:
                        start, size, raw_digest = item
                    except (TypeError, ValueError):
                        raise DownloadError("REMOTE_HASH_RESPONSE_INVALID") from None
                if type(start) is not int or type(size) is not int or start < 0 or size <= 0:
                    raise DownloadError("REMOTE_HASH_RESPONSE_INVALID")
                if allow_prefix_terminal_eof and (
                    start % (128 * 1024) != 0 or size != 128 * 1024
                ):
                    raise DownloadError("REMOTE_HASH_RANGE_INVALID")
                if start != end:
                    raise DownloadError("REMOTE_HASH_COVERAGE_GAP")
                reported_end = start + size
                if reported_end > candidate.expected_bytes:
                    if not (
                        ((allow_terminal_eof and required_bytes == candidate.expected_bytes)
                         or (allow_prefix_terminal_eof and self.allow_prefix_terminal_eof
                             and 0 < required_bytes < candidate.expected_bytes
                             and required_bytes % (128 * 1024) == 0
                             and start >= required_bytes))
                        and index == len(ranges) - 1 and start < candidate.expected_bytes
                        and size == 128 * 1024 and start % (128 * 1024) == 0
                        and reported_end - candidate.expected_bytes < 128 * 1024
                    ):
                        raise DownloadError("REMOTE_HASH_RANGE_INVALID")
                    end = candidate.expected_bytes
                else:
                    end = reported_end
                digest = _remote_digest(raw_digest)
                if digest is None:
                    raise DownloadError("REMOTE_HASH_RESPONSE_INVALID")
                collected.append(RemoteFileHash(start, size, digest))
                if prefix_proof and end >= required_bytes:
                    break
            if end <= cursor:
                raise DownloadError("REMOTE_HASHES_INCOMPLETE")
            cursor = end
        return tuple(collected)

    async def _verify_prefix(
        self, candidate: DownloadCandidate, partial: Path, physical: int
    ) -> tuple[str, int, S6PrefixProofObservation]:
        block_size = 128 * 1024
        complete_file_proof = (
            self.require_full_remote_hash
            and physical == candidate.expected_bytes
        )
        if (self.allow_prefix_terminal_eof and self.require_full_remote_hash
                and physical < candidate.expected_bytes
                and candidate.expected_bytes % block_size
                and physical > candidate.expected_bytes // block_size * block_size):
            raise DownloadError("REMOTE_HASH_RANGE_INVALID")
        aligned_pilot = (
            self.allow_prefix_terminal_eof and self.require_full_remote_hash
            and 0 < physical < candidate.expected_bytes
            and physical % block_size == 0
        )
        ranges = await self._remote_hashes(
            candidate, physical,
            allow_terminal_eof=complete_file_proof,
            allow_prefix_terminal_eof=aligned_pilot,
            prefix_proof=physical < candidate.expected_bytes,
        )
        verified_ranges: list[RemoteFileHash] = []
        cursor = 0
        full_digest = hashlib.sha256()
        verification_bytes = 0
        try:
            with partial.open("rb") as source:
                for item in ranges:
                    start, end = item.offset, item.offset + item.limit
                    if start != cursor:
                        raise DownloadError("REMOTE_HASH_COVERAGE_GAP")
                    if start >= physical:
                        break
                    if aligned_pilot and end > physical:
                        raise DownloadError("REMOTE_HASH_RANGE_INVALID")
                    digest = hashlib.sha256()
                    local_end = min(end, physical)
                    remaining = local_end - start
                    while remaining:
                        block = source.read(min(CHUNK_BYTES, remaining))
                        if not block:
                            raise DownloadError("PARTIAL_CHANGED")
                        digest.update(block)
                        full_digest.update(block)
                        remaining -= len(block)
                    if end > physical and not complete_file_proof:
                        verification_bytes += await self._hash_remote_complement(
                            candidate, physical, end, digest
                        )
                    if digest.digest() != item.sha256:
                        raise DownloadError("PARTIAL_INTEGRITY_MISMATCH")
                    verified_ranges.append(item)
                    cursor = end
        except OSError:
            raise DownloadError("PARTIAL_CHANGED") from None
        if cursor < physical:
            raise DownloadError("REMOTE_HASHES_INCOMPLETE")
        prefix_digest = full_digest.hexdigest()
        observation = S6PrefixProofObservation(
            candidate_identity=(
                candidate.channel_id,
                candidate.telegram_message_id,
                candidate.media_ordinal,
            ),
            expected_bytes=candidate.expected_bytes,
            physical_prefix_bytes=physical,
            local_prefix_sha256=prefix_digest,
            remote_ranges=(
                tuple(verified_ranges) if self.allow_prefix_terminal_eof else ranges
            ),
            verification_payload_bytes=verification_bytes,
        )
        return prefix_digest, verification_bytes, observation

    async def _hash_remote_complement(
        self, candidate: DownloadCandidate, physical: int, end: int,
        digest: object,
    ) -> int:
        wire_offset = (physical // CHUNK_BYTES) * CHUNK_BYTES
        position = wire_offset
        received = 0
        stream = self.gateway.stream_media(
            candidate.channel_id, candidate.telegram_message_id,
            candidate.media_ordinal, telegram_media_id=candidate.telegram_media_id,
            expected_bytes=candidate.expected_bytes, offset=wire_offset,
            reserve_chunk=self.chunk_reserver or _reserve_unbounded_chunk,
        )
        try:
            async for chunk in stream:
                if not isinstance(chunk, bytes) or not chunk or len(chunk) > self.chunk_bytes:
                    raise DownloadError("INVALID_CHUNK")
                if position + len(chunk) > candidate.expected_bytes:
                    raise DownloadError("SIZE_EXCEEDED")
                if self.chunk_callback is not None:
                    self.chunk_callback(len(chunk))
                self._observe_traffic("proof", len(chunk))
                received += len(chunk)
                segment_start = max(physical - position, 0)
                segment_end = min(end - position, len(chunk))
                if segment_end > segment_start:
                    digest.update(chunk[segment_start:segment_end])
                position += len(chunk)
                if position >= end:
                    break
        finally:
            close = getattr(stream, "aclose", None)
            if callable(close):
                await close()
        if position < end:
            raise DownloadError("REMOTE_HASHES_INCOMPLETE")
        return received

    async def _preserve_checkpoint(
        self, candidate: DownloadCandidate, partial: Path, fallback_size: int
    ) -> bool:
        try:
            if partial.is_file() and not partial.is_symlink():
                with partial.open("r+b") as output:
                    output.flush()
                    os.fsync(output.fileno())
                fallback_size = partial.stat().st_size
                await self.repository.checkpoint(candidate.media_item_id, fallback_size)
            return True
        except (OSError, DownloadInProgress, ValueError):
            return False
