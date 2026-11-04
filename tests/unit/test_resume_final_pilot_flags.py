"""Offline parser guardrails for the opt-in two-wave Telegram product pilot."""
from __future__ import annotations

import pytest

from telegram_courses.cli import _parse_arguments
from telegram_courses.config import ConfigurationError


def base():
    return [
        "download", "queue", "--channel-id", "-1002758699600",
        "--scope", "module", "--required-module-id", "44",
        "--database", "C:/private/db/catalog.sqlite3",
        "--download-dir", "C:/private/downloads",
        "--workers", "1", "--attempts-per-media", "1",
        "--max-media-items", "1",
        "--max-single-media-bytes", "134217728",
        "--max-transfer-bytes", "6199635",
        "--max-runtime-seconds", "1800",
        "--integrity-mode", "REMOTE_HASH_REQUIRED",
        "--private-downloads", "--require-full-remote-hash",
    ]


def test_wave1_parses_single_exact_message():
    args = _parse_arguments(base() + ["--pilot-message-ids", "585"])
    assert args.pilot_message_ids == (585,)
    assert args.pilot_require_already_valid_id is None


def test_wave2_requires_prior_already_valid_message():
    wave = base()
    wave[wave.index("--max-media-items") + 1] = "3"
    args = _parse_arguments(wave + [
        "--pilot-message-ids", "585,586,587",
        "--pilot-require-already-valid-id", "585",
    ])
    assert args.pilot_message_ids == (585, 586, 587)
    assert args.pilot_require_already_valid_id == 585


@pytest.mark.parametrize("raw", (
    "", "0", "585,585", "585,586,587,588", "585,,586",
    " 585", "585,586 ", "-1", "585,a", "585;586",
))
def test_reject_invalid_and_duplicate_pilot_selections(raw):
    with pytest.raises(ConfigurationError):
        _parse_arguments(base() + ["--pilot-message-ids", raw])


def test_reject_media_count_mismatch():
    with pytest.raises(ConfigurationError):
        _parse_arguments(base() + ["--pilot-message-ids", "585,586"])


def test_reject_prior_id_not_in_selection():
    with pytest.raises(ConfigurationError):
        _parse_arguments(base() + [
            "--pilot-message-ids", "585",
            "--pilot-require-already-valid-id", "586",
        ])


def test_no_pilot_selector_without_private_strict_integrity():
    with pytest.raises(ConfigurationError):
        _parse_arguments([
            item for item in base() if item != "--require-full-remote-hash"
        ] + ["--pilot-message-ids", "585"])


def test_no_bypass_confirm_in_pilot():
    with pytest.raises(ConfigurationError):
        _parse_arguments(base() + ["--pilot-message-ids", "585", "--confirm"])


def test_exact_expedited_585_retry_parses_only_hardcoded_scope():
    values = base()
    values[values.index("--max-transfer-bytes") + 1] = "6291456"
    args = _parse_arguments(values + [
        "--pilot-message-ids", "585", "--pilot-resume-585-once",
    ])
    assert args.pilot_resume_585_once is True
    assert args.max_transfer_bytes == 6291456


@pytest.mark.parametrize("item,new", (
    ("--channel-id", "-1002"),
    ("--required-module-id", "45"),
    ("--max-media-items", "2"),
    ("--max-transfer-bytes", "6199635"),
    ("--max-single-media-bytes", "200000000"),
    ("--workers", "2"),
    ("--attempts-per-media", "2"),
))
def test_expedited_retry_never_accepts_relaxed_or_mismatched_scope(item,new):
    values = base()
    values[values.index("--max-transfer-bytes") + 1] = "6291456"
    values[values.index(item) + 1] = new
    with pytest.raises(ConfigurationError):
        _parse_arguments(values + [
            "--pilot-message-ids", "585", "--pilot-resume-585-once",
        ])


def test_expedited_retry_rejects_confirm_bypass():
    values = base()
    values[values.index("--max-transfer-bytes") + 1] = "6291456"
    with pytest.raises(ConfigurationError):
        _parse_arguments(values + [
            "--pilot-message-ids", "585", "--pilot-resume-585-once", "--confirm",
        ])
