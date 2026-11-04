from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest


def _event(kind: str, **fields: object) -> None:
    target = os.environ.get("S9_DIAGNOSTIC_EVENTS")
    if target:
        with Path(target).open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {"at_utc": datetime.now(UTC).isoformat(), "event": kind, **fields},
                    sort_keys=True,
                )
                + "\n"
            )
            stream.flush()


def pytest_runtest_logstart(nodeid: str, location: tuple[str, int | None, str]) -> None:
    _event("test_started", nodeid=nodeid)
    print(f"LAST_TEST_STARTED={nodeid}", flush=True)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when == "teardown":
        _event("test_completed", nodeid=report.nodeid, outcome=report.outcome)
        print(f"LAST_TEST_COMPLETED={report.nodeid} outcome={report.outcome}", flush=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef: pytest.FixtureDef[object], request: pytest.FixtureRequest):
    _event(
        "fixture_started",
        fixture=fixturedef.argname,
        test=request.node.nodeid,
    )
    outcome = yield
    _event(
        "fixture_completed",
        fixture=fixturedef.argname,
        test=request.node.nodeid,
        failed=outcome.excinfo is not None,
    )


def pytest_fixture_post_finalizer(
    fixturedef: pytest.FixtureDef[object], request: pytest.FixtureRequest
) -> None:
    _event("fixture_finalized", fixture=fixturedef.argname, test=request.node.nodeid)
