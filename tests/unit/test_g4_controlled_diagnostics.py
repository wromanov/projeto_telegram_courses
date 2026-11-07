"""Offline reproductions of the G4 boundary; synthetic bytes only."""
import asyncio
import hashlib
import io
from types import SimpleNamespace

import pytest
from rich.console import Console
from telethon.tl.functions.upload import GetFileRequest
from telethon.tl.types import InputDocumentFileLocation, PeerChannel

from telegram_courses.auth import AuthState
from telegram_courses.course_download_planning import (
    CoursePlanReview,
    create_course_plan_review,
)
from telegram_courses.download_repository import DownloadCandidate, DownloadRepository
from telegram_courses.downloads import (
    DownloadError,
    DownloadGatewayError,
    RemoteFileHash,
    SingleMediaDownloadApplication,
)
from telegram_courses.interactive_catalog_cli import _render_course_plan
from telegram_courses.s5_downloads import DownloadPlan, DownloadSelection, PlanItem
from telegram_courses.telethon_gateway import TelethonGateway

SIZE = 8_900_624
CHECKPOINT = 8_650_752
REMAINING = 249_872
CHUNK = 262_144


def test_g4_preview_exposes_sequential_reservation_floor():
    sizes = (5_882_198, 23_183_637, SIZE)
    items = tuple(
        SimpleNamespace(candidate=SimpleNamespace(expected_bytes=size), estimated_payload_bytes=size)
        for size in sizes
    )
    review = SimpleNamespace(plan=SimpleNamespace(pending=items))
    floor = CoursePlanReview.telegram_reservation_floor_bytes.fget(review)
    assert floor == 37_967_467
    assert floor - sum(sizes) == 1_008


def test_g4_preview_exposes_reservation_for_remaining_tail():
    item = SimpleNamespace(candidate=SimpleNamespace(expected_bytes=SIZE), estimated_payload_bytes=REMAINING)
    review = SimpleNamespace(plan=SimpleNamespace(pending=(item,)))
    assert CoursePlanReview.telegram_reservation_floor_bytes.fget(review) == 250_880


def test_g4_preview_warns_without_increasing_budget(tmp_path):
    candidate = DownloadCandidate(1, -1001, 20, 0, "synthetic", SIZE, "synthetic.mp4", (("lesson", "Synthetic"),))
    item = PlanItem((-1001, 20, 0), candidate, "CONDITIONAL_RESUME_CANDIDATE", estimated_payload_bytes=REMAINING, estimated_additional_disk_bytes=REMAINING)
    plan = DownloadPlan("test", DownloadSelection(-1001, "course", 5), "Synthetic", False, 1, (item,))
    review = create_course_plan_review(plan, selection_mode="SELECTED", download_root=tmp_path, max_transfer_bytes=REMAINING, disk_usage=lambda _: SimpleNamespace(free=10**12))
    output = io.StringIO()
    _render_course_plan(SimpleNamespace(channel=SimpleNamespace(title="Synthetic")), SimpleNamespace(title="Synthetic"), (), review, ambiguous_order=False, console=Console(file=output, width=180))
    assert "reserva mínima estimada" in output.getvalue()
    assert review.max_transfer_bytes == REMAINING


@pytest.mark.parametrize("tail,budget,allowed", [
    (REMAINING, REMAINING, False),
    (REMAINING, 250_880, True),
    (249_856, 249_856, True),
])
def test_g4_final_request_respects_aligned_reservation_and_budget(tail, budget, allowed):
    events = []
    end_size = CHECKPOINT + tail
    wire_limit = ((tail + 1023) // 1024) * 1024

    class _DirectDownloadIter:
        def __init__(self):
            location = InputDocumentFileLocation(
                id=99, access_hash=1, file_reference=b"synthetic", thumb_size="",
            )
            self.request = GetFileRequest(location, offset=CHECKPOINT, limit=CHUNK)
            self.done = False

        async def _request(self):
            bytes(self.request)
            events.append(("request", self.request.limit, self.request.precise))
            return b"x" * tail

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.done:
                raise StopAsyncIteration
            self.done = True
            return await self._request()

    class Client:
        _request_retries = 1

        async def get_input_entity(self, _channel):
            return "peer"

        async def get_messages(self, _peer, *, ids):
            return SimpleNamespace(id=ids, peer_id=PeerChannel(123), media=SimpleNamespace(document=SimpleNamespace(id=99, size=end_size)))

        def iter_download(self, _document, **kwargs):
            assert kwargs["request_size"] == CHUNK
            assert kwargs["offset"] == CHECKPOINT
            return _DirectDownloadIter()

    gateway = object.__new__(TelethonGateway)
    gateway._client = Client()
    gateway._state = AuthState.AUTHENTICATED
    gateway._strict_budget_lock = asyncio.Lock()
    gateway._strict_budget_streams = 0
    gateway._strict_budget_previous_retries = None
    gateway._record_failure = lambda *_args: None

    async def reserve(amount):
        events.append(("reserve", amount))
        return None if amount > budget else SimpleNamespace(received=lambda n: events.append(("received", n)))

    async def run():
        if not allowed:
            with pytest.raises(DownloadGatewayError) as caught:
                async for _ in gateway._iterate_media(-1000000000123, 5, 0, telegram_media_id="99", expected_bytes=end_size, chunk_bytes=CHUNK, offset=CHECKPOINT, reserve_chunk=reserve):
                    pass
            assert caught.value.category == "TRANSFER_BUDGET_EXHAUSTED"
        else:
            chunks = [chunk async for chunk in gateway._iterate_media(-1000000000123, 5, 0, telegram_media_id="99", expected_bytes=end_size, chunk_bytes=CHUNK, offset=CHECKPOINT, reserve_chunk=reserve)]
            assert len(chunks[0]) == tail

    asyncio.run(run())
    assert events == ([('reserve', wire_limit), ('request', wire_limit, True), ('received', tail)] if allowed else [('reserve', wire_limit)])


def test_g4_prefix_hash_page_with_terminal_overrun_is_rejected(tmp_path):
    block = 128 * 1024
    ranges = tuple(RemoteFileHash(offset, block, b"x" * 32) for offset in range(0, SIZE, block))

    class Gateway:
        async def get_file_hashes(self, *_args, offset=0, **_kwargs):
            assert offset == 0
            return ranges

    candidate = DownloadCandidate(1, -1001, 20, 0, "synthetic", SIZE, "synthetic.mp4", (("lesson", "Synthetic"),))
    app = SingleMediaDownloadApplication(DownloadRepository(tmp_path / "unused.sqlite3"), Gateway(), tmp_path)
    with pytest.raises(DownloadError) as caught:
        asyncio.run(app._remote_hashes(candidate, CHECKPOINT))
    assert caught.value.category == "REMOTE_HASH_RANGE_INVALID"
    assert CHECKPOINT % CHUNK == 0
    assert ranges[-1].offset + ranges[-1].limit > SIZE


@pytest.mark.parametrize("corrupt", [False, True])
def test_g4_exact_prefix_hash_verification_never_accepts_bad_digest(tmp_path, corrupt):
    block = 128 * 1024
    part = tmp_path / "synthetic.part"
    part.write_bytes(b"x" * CHECKPOINT)
    digest = hashlib.sha256(b"x" * block).digest()
    ranges = [RemoteFileHash(offset, block, digest) for offset in range(0, CHECKPOINT, block)]
    if corrupt:
        ranges[0] = RemoteFileHash(0, block, b"z" * 32)

    class Gateway:
        async def get_file_hashes(self, *_args, offset=0, **_kwargs):
            assert offset == 0
            return ranges

    candidate = DownloadCandidate(1, -1001, 20, 0, "synthetic", SIZE, "synthetic.mp4", (("lesson", "Synthetic"),))
    app = SingleMediaDownloadApplication(DownloadRepository(tmp_path / "unused.sqlite3"), Gateway(), tmp_path)
    if corrupt:
        with pytest.raises(DownloadError) as caught:
            asyncio.run(app._verify_prefix(candidate, part, CHECKPOINT))
        assert caught.value.category == "PARTIAL_INTEGRITY_MISMATCH"
    else:
        _, proof_bytes, _ = asyncio.run(app._verify_prefix(candidate, part, CHECKPOINT))
        assert proof_bytes == 0
    assert part.stat().st_size == CHECKPOINT


@pytest.mark.parametrize("scenario", ["valid", "bad_digest", "missing", "gap", "overlap"])
def test_g4_real_page_geometry_prefix_proof(tmp_path, scenario):
    block = 128 * 1024
    window = 1024 * 1024
    part = tmp_path / "synthetic.part"
    part.write_bytes(b"x" * CHECKPOINT)
    digest = hashlib.sha256(b"x" * block).digest()
    ranges = [RemoteFileHash(offset, block, digest) for offset in range(0, SIZE, block)]
    second = (CHECKPOINT // block) - 1
    if scenario == "bad_digest":
        ranges[second] = RemoteFileHash(ranges[second].offset, block, b"z" * 32)
    elif scenario == "missing":
        ranges.pop(second)
    elif scenario in {"gap", "overlap"}:
        delta = 1 if scenario == "gap" else -1
        ranges[second] = RemoteFileHash(ranges[second].offset + delta, block, digest)

    class Gateway:
        async def get_file_hashes(self, *_args, offset=0, **_kwargs):
            return [item for item in ranges if offset <= item.offset < offset + window]

    candidate = DownloadCandidate(1, -1001, 20, 0, "synthetic", SIZE, "synthetic.mp4", (("lesson", "Synthetic"),))
    app = SingleMediaDownloadApplication(DownloadRepository(tmp_path / "unused.sqlite3"), Gateway(), tmp_path)
    if scenario == "valid":
        _, proof_bytes, proof = asyncio.run(app._verify_prefix(candidate, part, CHECKPOINT))
        assert proof_bytes == 0
        assert proof.remote_ranges[-1].offset + proof.remote_ranges[-1].limit == CHECKPOINT
        assert len(proof.remote_ranges) == CHECKPOINT // block
    else:
        with pytest.raises(DownloadError):
            asyncio.run(app._verify_prefix(candidate, part, CHECKPOINT))
    assert part.stat().st_size == CHECKPOINT
