"""Offline S6 V2 evidence primitives; operational activation remains disabled."""

from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CHUNK_BYTES = 256 * 1024
V2_EFFECTIVE = False
CONTRACT_VERSION = 2
EVIDENCE_VERSION = 1
MODES = frozenset({"REMOTE_HASH_REQUIRED", "OPERATIONAL_ONLY", "TRUSTED_REFERENCE"})
REMOTE_HASH_CLASSES = frozenset({
    "REMOTE_HASH_FULL", "REMOTE_HASH_PARTIAL", "REMOTE_HASH_ABSENT",
    "REMOTE_HASH_UNAVAILABLE", "REMOTE_HASH_UNVERIFIABLE_EOF",
    "REMOTE_HASH_INVALID_RESPONSE", "REMOTE_HASH_DIVERGENT",
})


@dataclass(frozen=True)
class RemoteHashAssessment:
    primary: str
    events: tuple[dict[str, object], ...]
    verified_ranges: tuple[tuple[int, int], ...]
    coverage_complete: bool
    blocking: bool


@dataclass(frozen=True)
class ReferenceEvidence:
    path: Path
    size: int
    sha256: str
    provenance: str
    stat_signature: tuple[int, int, int, int]
    manifest_path: Path
    manifest_sha256: str
    manifest_stat_signature: tuple[int, int, int, int]


def _range_values(item: Any) -> tuple[object, object, object] | None:
    try:
        return item.offset, item.limit, item.sha256
    except AttributeError:
        try:
            offset, limit, digest = item
        except (TypeError, ValueError):
            return None
        return offset, limit, digest


def _digest_bytes(value: object) -> bytes | None:
    if isinstance(value, bytes):
        digest = value
    elif isinstance(value, str):
        if len(value) != 64:
            return None
        try:
            digest = bytes.fromhex(value)
        except ValueError:
            return None
    else:
        return None
    return digest if len(digest) == hashlib.sha256().digest_size else None


def assess_remote_hashes(
    path: Path,
    expected_bytes: int,
    response: object,
    *,
    unavailable: bool = False,
    method_absent: bool = False,
) -> RemoteHashAssessment:
    """Classify returned ranges without clamping, padding, or fabricating coverage."""
    if method_absent or response is None:
        if unavailable:
            return RemoteHashAssessment(
                "REMOTE_HASH_UNAVAILABLE",
                ({"class": "REMOTE_HASH_UNAVAILABLE"},), (), False, True,
            )
        return RemoteHashAssessment(
            "REMOTE_HASH_ABSENT", ({"class": "REMOTE_HASH_ABSENT"},), (), False, False
        )
    if type(expected_bytes) is not int or expected_bytes < 0 or not isinstance(response, (tuple, list)):
        return RemoteHashAssessment(
            "REMOTE_HASH_INVALID_RESPONSE", ({"class": "REMOTE_HASH_INVALID_RESPONSE", "reason": "shape"},), (), False, True
        )
    if not response:
        if unavailable:
            return RemoteHashAssessment(
                "REMOTE_HASH_UNAVAILABLE",
                ({"class": "REMOTE_HASH_UNAVAILABLE"},), (), False, True,
            )
        return RemoteHashAssessment(
            "REMOTE_HASH_ABSENT", ({"class": "REMOTE_HASH_ABSENT"},), (), False, False
        )

    events: list[dict[str, object]] = []
    valid: list[tuple[int, int, bytes]] = []
    invalid = False
    divergent = False
    eof = False
    for item in response:
        values = _range_values(item)
        if values is None:
            invalid = True
            events.append({"class": "REMOTE_HASH_INVALID_RESPONSE", "reason": "range_shape"})
            continue
        offset, limit, raw_digest = values
        digest = _digest_bytes(raw_digest)
        if (
            type(offset) is not int or type(limit) is not int or offset < 0
            or limit <= 0 or offset > (2**63 - 1) - limit or digest is None
        ):
            invalid = True
            events.append({"class": "REMOTE_HASH_INVALID_RESPONSE", "reason": "range_or_digest"})
            continue
        end = offset + limit
        if end > expected_bytes:
            eof = True
            events.append({
                "class": "REMOTE_HASH_UNVERIFIABLE_EOF",
                "offset": offset,
                "limit": limit,
                "expected_bytes": expected_bytes,
                "verifiable_bytes": max(0, expected_bytes - offset),
            })
            continue
        try:
            hasher = hashlib.sha256()
            remaining = limit
            with path.open("rb") as source:
                source.seek(offset)
                while remaining:
                    block = source.read(min(CHUNK_BYTES, remaining))
                    if not block:
                        raise OSError("local file ended inside a remote range")
                    hasher.update(block)
                    remaining -= len(block)
        except OSError:
            invalid = True
            events.append({"class": "REMOTE_HASH_INVALID_RESPONSE", "reason": "local_range_unreadable"})
            continue
        if hasher.digest() != digest:
            divergent = True
            events.append({
                "class": "REMOTE_HASH_DIVERGENT", "offset": offset, "limit": limit,
                "declared_sha256": digest.hex(), "computed_sha256": hasher.hexdigest(),
            })
        else:
            valid.append((offset, end, digest))
            events.append({"class": "REMOTE_HASH_RANGE_MATCH", "offset": offset, "limit": limit})

    ordered = sorted(valid, key=lambda item: (item[0], item[1]))
    coverage: list[tuple[int, int]] = []
    for start, end, _digest in ordered:
        if not coverage or start > coverage[-1][1]:
            coverage.append((start, end))
        elif end > coverage[-1][1]:
            coverage[-1] = (coverage[-1][0], end)
    coverage_complete = expected_bytes == 0 or (
        len(coverage) == 1 and coverage[0] == (0, expected_bytes)
    )
    partial = not coverage_complete and expected_bytes > 0 and (bool(valid) or eof)
    if invalid and divergent:
        primary = "BLOCKED_CONTRADICTORY_REMOTE_EVIDENCE"
        blocking = True
    elif invalid:
        primary, blocking = "REMOTE_HASH_INVALID_RESPONSE", True
    elif divergent:
        primary, blocking = "REMOTE_HASH_DIVERGENT", True
    elif unavailable:
        primary, blocking = "REMOTE_HASH_UNAVAILABLE", True
    elif eof:
        primary, blocking = "REMOTE_HASH_UNVERIFIABLE_EOF", False
    elif not valid:
        primary, blocking = "REMOTE_HASH_ABSENT", False
    elif partial:
        primary, blocking = "REMOTE_HASH_PARTIAL", False
    else:
        primary, blocking = "REMOTE_HASH_FULL", False
    if partial and eof:
        events.append({"class": "REMOTE_HASH_PARTIAL", "verified_ranges": coverage})
    elif partial and primary != "REMOTE_HASH_PARTIAL":
        events.append({"class": "REMOTE_HASH_PARTIAL", "verified_ranges": coverage})
    if unavailable:
        events.append({"class": "REMOTE_HASH_UNAVAILABLE"})
    return RemoteHashAssessment(primary, tuple(events), tuple(coverage), coverage_complete, blocking)


def _file_signature(path: Path) -> tuple[int, int, int, int]:
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or path.is_symlink():
        raise ValueError("reference must be a regular non-symlink file")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _hash_path(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while block := stream.read(CHUNK_BYTES):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def load_reference(
    manifest_path: str | Path,
    *,
    channel_id: int,
    telegram_message_id: int,
    media_ordinal: int,
    telegram_media_id: str,
    expected_bytes: int,
) -> ReferenceEvidence:
    """Validate a user-selected reference and its identity/size/hash manifest."""
    manifest_path = Path(manifest_path).expanduser().absolute()
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("reference manifest is not a regular file")
    manifest_signature = _file_signature(manifest_path)
    raw = manifest_path.read_bytes()
    try:
        manifest = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("reference manifest is invalid JSON") from None
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("reference manifest version is unsupported")
    expected = {
        "channel_id": channel_id,
        "telegram_message_id": telegram_message_id,
        "media_ordinal": media_ordinal,
        "telegram_media_id": telegram_media_id,
        "expected_bytes": expected_bytes,
    }
    if any(
        type(manifest.get(key)) is not type(value) or manifest.get(key) != value
        for key, value in expected.items()
    ):
        raise ValueError("reference manifest identity mismatch")
    provenance = manifest.get("provenance")
    if (
        not isinstance(provenance, str)
        or not provenance.strip()
        or len(provenance) > 2048
    ):
        raise ValueError("reference provenance is unverified")
    sha256 = manifest.get("sha256")
    if not isinstance(sha256, str) or len(sha256) != 64:
        raise ValueError("reference manifest SHA-256 invalid")
    try:
        bytes.fromhex(sha256)
    except ValueError:
        raise ValueError("reference manifest SHA-256 invalid") from None
    reference_value = manifest.get("reference_path")
    if not isinstance(reference_value, str) or not reference_value:
        raise ValueError("reference path missing")
    reference = Path(reference_value).expanduser().absolute()
    signature = _file_signature(reference)
    size, actual_sha256 = _hash_path(reference)
    if size != expected_bytes or size != signature[2] or actual_sha256 != sha256.casefold():
        raise ValueError("reference size or SHA-256 mismatch")
    if _file_signature(reference) != signature:
        raise ValueError("reference changed during validation")
    if _file_signature(manifest_path) != manifest_signature or hashlib.sha256(
        manifest_path.read_bytes()
    ).digest() != hashlib.sha256(raw).digest():
        raise ValueError("reference manifest changed during validation")
    return ReferenceEvidence(
        reference, size, actual_sha256, provenance.strip(), signature, manifest_path,
        hashlib.sha256(raw).hexdigest(), manifest_signature,
    )


def reference_unchanged(reference: ReferenceEvidence) -> bool:
    try:
        manifest_before = _file_signature(reference.manifest_path)
        if manifest_before != reference.manifest_stat_signature or hashlib.sha256(
            reference.manifest_path.read_bytes()
        ).hexdigest() != reference.manifest_sha256:
            return False
        return _file_signature(reference.path) == reference.stat_signature and (
            _hash_path(reference.path) == (reference.size, reference.sha256)
        ) and _file_signature(reference.path) == reference.stat_signature and (
            _file_signature(reference.manifest_path) == reference.manifest_stat_signature
        )
    except (OSError, ValueError):
        return False


def files_equal(left: Path, right: Path) -> bool:
    try:
        if left.stat().st_size != right.stat().st_size:
            return False
        with left.open("rb") as left_stream, right.open("rb") as right_stream:
            while True:
                left_block = left_stream.read(CHUNK_BYTES)
                right_block = right_stream.read(CHUNK_BYTES)
                if left_block != right_block:
                    return False
                if not left_block:
                    return True
    except OSError:
        return False
