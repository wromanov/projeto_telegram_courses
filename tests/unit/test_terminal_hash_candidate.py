"""Synthetic offline tests. No Telegram requests or media mutations."""
from __future__ import annotations

import hashlib

import pytest

from telegram_courses.terminal_hash_candidate import (
    BLOCK_BYTES,
    compare_terminal_hash_hypotheses,
)


@pytest.mark.parametrize(
    ("digest_mode", "expected_status"),
    (
        ("truncated", "TRUNCATED_TAIL_DIGEST_MATCH_CANDIDATE"),
        ("zero_padded", "ZERO_PADDED_DIGEST_MATCH_CANDIDATE"),
        ("unrelated", "NO_CANDIDATE_DIGEST_MATCH"),
    ),
)
def test_terminal_eof_sha256_hypotheses(tmp_path, digest_mode, expected_status):
    payload = bytes((index % 251 for index in range(BLOCK_BYTES + 37)))
    path = tmp_path / "lesson.part"
    path.write_bytes(payload)
    tail = payload[BLOCK_BYTES:]
    samples = {
        "truncated": hashlib.sha256(tail).digest(),
        "zero_padded": hashlib.sha256(tail + bytes(BLOCK_BYTES - len(tail))).digest(),
        "unrelated": hashlib.sha256(b"not a match").digest(),
    }
    outcome = compare_terminal_hash_hypotheses(
        path, expected_bytes=len(payload), offset=BLOCK_BYTES,
        limit=BLOCK_BYTES, remote_sha256=samples[digest_mode],
    )
    assert outcome == expected_status
    assert path.read_bytes() == payload


@pytest.mark.parametrize(
    "kwargs",
    (
        {"offset": 0},
        {"offset": BLOCK_BYTES, "limit": BLOCK_BYTES - 1},
        {"offset": BLOCK_BYTES, "limit": BLOCK_BYTES + 1},
        {"offset": BLOCK_BYTES, "remote_sha256": b"x"},
        {"offset": BLOCK_BYTES, "expected_bytes": BLOCK_BYTES},
        {"offset": BLOCK_BYTES, "expected_bytes": 3 * BLOCK_BYTES},
        {"offset": BLOCK_BYTES - 1},
    ),
)
def test_rejects_bad_terminal_hash_geometry(tmp_path, kwargs):
    payload = b"a" * (BLOCK_BYTES + 37)
    path = tmp_path / "lesson.part"
    path.write_bytes(payload)
    args = {
        "expected_bytes": len(payload),
        "offset": BLOCK_BYTES,
        "limit": BLOCK_BYTES,
        "remote_sha256": hashlib.sha256(payload[BLOCK_BYTES:]).digest(),
    }
    args.update(kwargs)
    assert compare_terminal_hash_hypotheses(path, **args) == "INVALID_TERMINAL_GEOMETRY"


def test_rejects_missing_and_mismatched_file(tmp_path):
    path = tmp_path / "missing.part"
    params = {
        "expected_bytes": BLOCK_BYTES + 37,
        "offset": BLOCK_BYTES,
        "limit": BLOCK_BYTES,
        "remote_sha256": b"x" * 32,
    }
    assert compare_terminal_hash_hypotheses(path, **params) == "LOCAL_FILE_UNVERIFIED"
    path.write_bytes(b"short")
    assert compare_terminal_hash_hypotheses(path, **params) == "LOCAL_FILE_UNVERIFIED"
