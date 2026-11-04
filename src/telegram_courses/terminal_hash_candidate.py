"""Offline, read-only EOF-hash hypothesis comparison.

The metadata-only probe showed terminal FileHash ranges overrun declared EOF.
This module does *not* make a claim of remote integrity or authorize finalization.
It compares a supplied remote digest with explicit, distinct candidate byte strings.
"""
from __future__ import annotations

import hashlib
import stat
from pathlib import Path

BLOCK_BYTES = 131072
MAX_EOF_OVERHANG = BLOCK_BYTES - 1


def compare_terminal_hash_hypotheses(
    path: Path,
    *,
    expected_bytes: int,
    offset: int,
    limit: int,
    remote_sha256: bytes,
) -> str:
    """Classify a real remote digest without changing local media or its status.

    Return only the observed candidate relation. Never interpret a match as a
    complete-file remote integrity receipt.
    """
    if (
        type(expected_bytes) is not int or expected_bytes <= 0
        or type(offset) is not int or offset < 0
        or type(limit) is not int or limit != BLOCK_BYTES
        or type(remote_sha256) is not bytes or len(remote_sha256) != 32
        or offset >= expected_bytes
        or offset % BLOCK_BYTES != 0
        or offset + limit <= expected_bytes
        or offset + limit - expected_bytes > MAX_EOF_OVERHANG
    ):
        return "INVALID_TERMINAL_GEOMETRY"
    try:
        info = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or path.is_symlink() or info.st_size != expected_bytes:
            return "LOCAL_FILE_UNVERIFIED"
        remaining = expected_bytes - offset
        with path.open("rb") as stream:
            stream.seek(offset)
            tail = stream.read(remaining)
            if len(tail) != remaining:
                return "LOCAL_FILE_UNVERIFIED"
            if stream.read(1):
                return "LOCAL_FILE_UNVERIFIED"
        if path.stat(follow_symlinks=False).st_size != expected_bytes:
            return "LOCAL_FILE_UNVERIFIED"
    except OSError:
        return "LOCAL_FILE_UNVERIFIED"

    # The server metadata says 131072 bytes, but the local file has less.
    # Test separate *hypotheses*; do not assume the missing bytes are zeros.
    if hashlib.sha256(tail).digest() == remote_sha256:
        return "TRUNCATED_TAIL_DIGEST_MATCH_CANDIDATE"
    if hashlib.sha256(tail + bytes(limit - len(tail))).digest() == remote_sha256:
        return "ZERO_PADDED_DIGEST_MATCH_CANDIDATE"
    return "NO_CANDIDATE_DIGEST_MATCH"
