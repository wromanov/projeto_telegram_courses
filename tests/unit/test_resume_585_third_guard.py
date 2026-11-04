"""Offline guardrail tests for the one-shot third recovery of message 585."""
from __future__ import annotations

import hashlib

import pytest
from tools.telegram_3_resume_585_third_guard import (
    _validate_state,
    digest_file,
)

EXPECTED = {
    "file_size_bytes": 6199635,
    "expected_bytes": 6199635,
    "kind": "DOCUMENT",
    "remote_observation_state": "OBSERVED",
    "telegram_media_id": "synthetic-media-585",
    "remote_identity_media_id": "synthetic-media-585",
    "remote_identity_kind": "DOCUMENT",
    "remote_identity_size": 6199635,
    "remote_identity_provenance": "CAPTURED_AT_START",
    "owner_pid": None,
    "state": "FAILED_RETRYABLE",
    "attempts": 2,
    "downloaded_bytes": 6029312,
    "failure_category": "GATEWAY_FAILURE",
    "sha256": None,
}


def test_precondition_allows_only_two_prior_attempts() -> None:
    _validate_state(EXPECTED, post=False)


@pytest.mark.parametrize(("field", "value"), (
    ("attempts", 1),
    ("attempts", 3),
    ("state", "DOWNLOADING"),
    ("state", "DOWNLOADED"),
    ("downloaded_bytes", 6029313),
    ("failure_category", "TRANSFER_BUDGET_EXHAUSTED"),
    ("owner_pid", 1111),
    ("remote_identity_media_id", "different"),
    ("remote_identity_size", 6199634),
    ("sha256", "0" * 64),
))
def test_precondition_rejects_unexpected_prior_state(field, value) -> None:
    data = dict(EXPECTED, **{field: value})
    with pytest.raises(ValueError):
        _validate_state(data, post=False)


def test_postcondition_requires_exact_third_downloaded_attempt() -> None:
    data = dict(
        EXPECTED,
        state="DOWNLOADED",
        attempts=3,
        downloaded_bytes=6199635,
        failure_category=None,
        sha256="a" * 64,
    )
    _validate_state(data, post=True)
    for field, wrong in (
        ("attempts", 2),
        ("attempts", 4),
        ("state", "FAILED_RETRYABLE"),
        ("downloaded_bytes", 6029312),
        ("failure_category", "GATEWAY_FAILURE"),
        ("sha256", "bad"),
    ):
        with pytest.raises(ValueError):
            _validate_state(dict(data, **{field: wrong}), post=True)


def test_prefix_digest_measures_prefix_only(tmp_path) -> None:
    p = tmp_path / "synthetic_media.bin"
    p.write_bytes(b"ABCD" * 100 + b"TAIL")
    assert digest_file(p, first_bytes=400) == hashlib.sha256(b"ABCD" * 100).hexdigest()
    assert digest_file(p) == hashlib.sha256(b"ABCD" * 100 + b"TAIL").hexdigest()
    with pytest.raises(ValueError, match="DIGEST_INPUT_TRUNCATED"):
        digest_file(p, first_bytes=999)
