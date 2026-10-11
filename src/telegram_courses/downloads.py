"""Bounded single-media download orchestration and Windows-safe file policy."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Protocol

from telegram_courses.download_repository import (
    DownloadCandidate,
    DownloadInProgress,
    DownloadRepository,
    _process_is_alive,
)

CHUNK_BYTES = 256 * 1024
_RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.IGNORECASE)
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_LOCKS: dict[int, asyncio.Lock] = {}


class DownloadError(Exception):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category.lower().replace("_", " "))


class DownloadGatewayError(Exception):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


class DownloadGateway(Protocol):
    async def stream_media(
        self, channel_id: int, message_id: int, media_ordinal: int,
        *, telegram_media_id: str, expected_bytes: int,
    ) -> AsyncIterator[bytes]: ...


@dataclass(frozen=True)
class DownloadOutcome:
    result: str
    candidate: DownloadCandidate
    final_path: Path
    transferred_bytes: int
    sha256: str | None


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
    ) -> None:
        if type(chunk_bytes) is not int or not 0 < chunk_bytes <= CHUNK_BYTES:
            raise ValueError("chunk_bytes must be between 1 and 256 KiB")
        self.repository = repository
        self.gateway = gateway
        self.download_root = Path(download_root)
        self.chunk_bytes = chunk_bytes
        self.progress_callback = progress_callback

    async def download(self, channel_id: int, message_id: int, media_ordinal: int) -> DownloadOutcome:
        await self.repository.migrate()
        candidate = await self.repository.select_candidate(channel_id, message_id, media_ordinal)
        if candidate is None:
            raise DownloadError("MEDIA_NOT_ELIGIBLE")
        lock = _LOCKS.setdefault(candidate.media_item_id, asyncio.Lock())
        async with lock:
            return await self._download_locked(candidate)

    async def _download_locked(self, candidate: DownloadCandidate) -> DownloadOutcome:
        final, partial = destination_paths(self.download_root, candidate)
        _reject_reparse_path(self.download_root.absolute(), final)
        _reject_reparse_path(self.download_root.absolute(), partial)
        record = await self.repository.get_record(candidate.media_item_id)
        if (
            record is not None
            and record.state in {"DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING"}
            and record.owner_pid != os.getpid()
            and _process_is_alive(record.owner_pid)
        ):
            raise DownloadError("TRANSFER_IN_PROGRESS")
        if record is not None and record.final_path is not None and record.final_path != str(final):
            raise DownloadError("DOWNLOAD_ROOT_CHANGED")
        if record is not None and record.state == "DOWNLOADED":
            if record.final_path == str(final) and _matches(final, candidate.expected_bytes, record.sha256):
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
                await self.repository.transition(candidate.media_item_id, "DOWNLOADED", downloaded_bytes=candidate.expected_bytes)
                return DownloadOutcome("RECOVERED", candidate, final, candidate.expected_bytes, record.sha256)
            if _matches(partial, candidate.expected_bytes, record.sha256):
                _finalize_no_overwrite(partial, final)
                await self.repository.transition(candidate.media_item_id, "DOWNLOADED", downloaded_bytes=candidate.expected_bytes)
                return DownloadOutcome("RECOVERED", candidate, final, candidate.expected_bytes, record.sha256)
            if final.exists():
                raise DownloadError("FINALIZATION_FILE_MISMATCH")
            if partial.exists():
                if partial.is_symlink() or not partial.is_file() or record.partial_path != str(partial):
                    raise DownloadError("UNOWNED_PARTIAL_EXISTS")
                partial.unlink()
            await self.repository.transition(
                candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=0,
                failure_category="PARTIAL_INVALID",
            )
            record = await self.repository.get_record(candidate.media_item_id)
        if final.exists():
            raise DownloadError("DESTINATION_EXISTS")
        try:
            final.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise DownloadError("PATH_CREATE_FAILED") from None
        _reject_reparse_path(self.download_root.absolute(), final)
        _reject_reparse_path(self.download_root.absolute(), partial)
        if partial.exists() and (record is None or record.partial_path != str(partial)):
            raise DownloadError("UNOWNED_PARTIAL_EXISTS")
        try:
            await self.repository.start(candidate, final, partial)
        except DownloadInProgress:
            raise DownloadError("TRANSFER_IN_PROGRESS") from None
        digest = hashlib.sha256()
        total = 0
        try:
            with partial.open("wb") as output:
                async for chunk in self.gateway.stream_media(
                    candidate.channel_id, candidate.telegram_message_id, candidate.media_ordinal,
                    telegram_media_id=candidate.telegram_media_id, expected_bytes=candidate.expected_bytes,
                ):
                    if not isinstance(chunk, bytes) or not chunk or len(chunk) > self.chunk_bytes:
                        raise DownloadError("INVALID_CHUNK")
                    total += len(chunk)
                    if total > candidate.expected_bytes:
                        raise DownloadError("SIZE_EXCEEDED")
                    output.write(chunk)
                    digest.update(chunk)
                    if self.progress_callback is not None and (
                        total == candidate.expected_bytes or total % (1024 * 1024) < len(chunk)
                    ):
                        self.progress_callback(total, candidate.expected_bytes)
                output.flush()
                os.fsync(output.fileno())
            physical = partial.stat().st_size
            if total != candidate.expected_bytes or physical != candidate.expected_bytes:
                raise DownloadError("SIZE_MISMATCH")
            local_hash = digest.hexdigest()
            await self.repository.transition(candidate.media_item_id, "VALIDATED", downloaded_bytes=total, sha256=local_hash)
            await self.repository.transition(candidate.media_item_id, "FINALIZATION_PENDING", downloaded_bytes=total)
            if final.exists():
                raise DownloadError("DESTINATION_EXISTS")
            _finalize_no_overwrite(partial, final)
            if not _matches(final, candidate.expected_bytes, local_hash):
                raise DownloadError("FINAL_FILE_MISMATCH")
            await self.repository.transition(candidate.media_item_id, "DOWNLOADED", downloaded_bytes=total)
            return DownloadOutcome("DOWNLOADED", candidate, final, total, local_hash)
        except asyncio.CancelledError:
            await self.repository.transition(candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=total, failure_category="CANCELLED")
            raise
        except DownloadError as error:
            await self.repository.transition(candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=total, failure_category=error.category)
            raise
        except DownloadGatewayError as error:
            await self.repository.transition(candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=total, failure_category=error.category)
            raise DownloadError(error.category) from None
        except Exception:
            if total == candidate.expected_bytes and 'digest' in locals():
                candidate_hash = digest.hexdigest()
                if _matches(final, candidate.expected_bytes, candidate_hash):
                    raise DownloadError("STATE_COMMIT_PENDING") from None
            await self.repository.transition(candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=total, failure_category="TRANSFER_FAILED")
            raise DownloadError("TRANSFER_FAILED") from None
