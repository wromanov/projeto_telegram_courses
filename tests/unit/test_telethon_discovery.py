from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from telethon import errors, utils
from telethon.tl import types
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types.messages import DialogsNotModified

from telegram_courses.auth import AuthState
from telegram_courses.channel_discovery import (
    ChannelDiscoveryError,
    ChannelKind,
    DiscoveryErrorCategory,
    DiscoveryLimits,
    DiscoveryRequest,
    DiscoveryStopReason,
)
from telegram_courses.config import TelegramCredentials
from telegram_courses.telethon_gateway import TelethonGateway

_NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


class FakeVault:
    def __init__(self) -> None:
        self.saved: list[str] = []

    def _load(self) -> str:
        return "synthetic-protected-session"

    def _save(self, value: str) -> None:
        self.saved.append(value)


class FakeClient:
    def __init__(self, _session: object, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.calls: list[object] = []
        self.responses: list[object] = []
        self.call_error: Exception | None = None
        self.call_delay = 0.0
        self.disconnect_error: Exception | None = None
        self.closed = 0

    async def connect(self) -> None:
        self.calls.append("connect")

    async def get_me(self) -> object:
        self.calls.append("get_me")
        return object()

    async def disconnect(self) -> None:
        self.closed += 1
        if self.disconnect_error:
            raise self.disconnect_error

    async def __call__(self, request: object) -> object:
        self.calls.append(request)
        if self.call_delay:
            await asyncio.sleep(self.call_delay)
        if self.call_error:
            raise self.call_error
        return self.responses.pop(0)


def channel(
    channel_id: int,
    *,
    broadcast: bool | None = False,
    megagroup: bool | None = True,
    left: bool | None = False,
    restricted: bool | None = False,
    title: str | None = None,
    username: str | None = None,
    forum: bool | None = False,
) -> types.Channel:
    return types.Channel(
        id=channel_id,
        title=title or f"Synthetic {channel_id}",
        photo=types.ChatPhotoEmpty(),
        date=_NOW,
        broadcast=broadcast,
        megagroup=megagroup,
        left=left,
        restricted=restricted,
        forum=forum,
        access_hash=channel_id + 1000,
        username=username,
    )


def dialog(
    peer: object, message_id: int, *, pinned: bool | None = None
) -> types.Dialog:
    return types.Dialog(
        peer=peer,
        top_message=message_id,
        read_inbox_max_id=0,
        read_outbox_max_id=0,
        unread_count=0,
        unread_mentions_count=0,
        unread_reactions_count=0,
        unread_poll_votes_count=0,
        notify_settings=types.PeerNotifySettings(),
        pinned=pinned,
    )


def message(peer: object, message_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=message_id,
        peer_id=peer,
        date=_NOW,
        message="INCIDENTAL_MESSAGE_CANARY",
        media="INCIDENTAL_MEDIA_CANARY",
    )


def dialogs_slice(
    rows: list[types.Dialog],
    entities: list[object],
    *,
    count: int | None = None,
) -> types.messages.DialogsSlice:
    messages = [message(row.peer, row.top_message) for row in rows]
    return types.messages.DialogsSlice(
        count=len(rows) if count is None else count,
        dialogs=rows,
        messages=messages,
        chats=entities,
        users=[],
    )


def terminal_dialogs(
    rows: list[types.Dialog], entities: list[object]
) -> types.messages.Dialogs:
    messages = [message(row.peer, row.top_message) for row in rows]
    return types.messages.Dialogs(
        dialogs=rows,
        messages=messages,
        chats=entities,
        users=[],
    )


def make_gateway(
    responses: list[object], *, limits: DiscoveryLimits | None = None
) -> tuple[TelethonGateway, FakeClient]:
    client = FakeClient(None)
    client.responses = list(responses)

    def factory(_session: object, *_args: object, **kwargs: object) -> FakeClient:
        client.kwargs = kwargs
        return client

    gateway = TelethonGateway(
        TelegramCredentials(7, "synthetic-api-hash"),
        client_factory=factory,
        session_factory=lambda value: value,
        vault=FakeVault(),
        receive_updates=False,
        catch_up=False,
    )
    return gateway, client


def discover(gateway: TelethonGateway, limits: DiscoveryLimits | None = None):
    async def run():
        assert await gateway.restore() is AuthState.AUTHENTICATED
        try:
            return await gateway.discover_channels(
                DiscoveryRequest(limits or DiscoveryLimits())
            )
        finally:
            await gateway.close()

    return asyncio.run(run())


def test_broadcast_megagroup_and_exclusions_are_projected_to_own_dtos() -> None:
    broadcast = channel(101, broadcast=True, megagroup=False, username="news")
    megagroup = channel(102, megagroup=True, forum=True)
    ambiguous = channel(103, broadcast=True, megagroup=True)
    left = channel(104, left=True)
    restricted = channel(105, restricted=True)
    forbidden = types.ChannelForbidden(
        id=106, access_hash=2000, title="Forbidden", broadcast=True, megagroup=False
    )
    basic_group = types.Chat(
        id=107,
        title="Basic",
        photo=types.ChatPhotoEmpty(),
        participants_count=5,
        date=_NOW,
        version=1,
    )
    user = types.User(id=108, first_name="Synthetic", bot=False)
    rows = [
        dialog(types.PeerChannel(item.id), index + 1)
        for index, item in enumerate(
            (broadcast, megagroup, ambiguous, left, restricted, forbidden)
        )
    ]
    rows.extend((dialog(types.PeerChat(107), 7), dialog(types.PeerUser(108), 8)))
    gateway, client = make_gateway([terminal_dialogs(rows, [
        broadcast, megagroup, ambiguous, left, restricted, forbidden, basic_group, user
    ])])

    result = discover(gateway)

    assert result.complete is True
    assert result.stop_reason is None
    assert [(item.telegram_chat_id, item.kind) for item in result.channels] == [
        (utils.get_peer_id(broadcast), ChannelKind.BROADCAST_CHANNEL),
        (utils.get_peer_id(megagroup), ChannelKind.MEGAGROUP),
    ]
    assert result.channels[0].username == "news"
    assert "INCIDENTAL_MESSAGE_CANARY" not in repr(result)
    assert "INCIDENTAL_MEDIA_CANARY" not in repr(result)
    assert result.stats.raw_dialogs_received == 8
    assert result.stats.unique_candidates == 2
    assert client.kwargs["receive_updates"] is False
    assert client.kwargs["catch_up"] is False
    assert client.closed == 1
    requests = [call for call in client.calls if isinstance(call, GetDialogsRequest)]
    assert len(requests) == 1
    assert requests[0].folder_id is None
    assert requests[0].exclude_pinned is False


def test_duplicate_candidates_are_deduplicated_by_stable_telegram_id() -> None:
    broadcast = channel(201, broadcast=True, megagroup=False, title="Before")
    peer = types.PeerChannel(201)
    rows = [dialog(peer, 11), dialog(peer, 12)]
    response = terminal_dialogs(rows, [broadcast])
    response.messages.extend([message(peer, 12)])
    gateway, _client = make_gateway([response])

    result = discover(gateway)

    assert len(result.channels) == 1
    assert result.channels[0].telegram_chat_id == -1_000_000_000_201
    assert result.channels[0].title == "Before"


def test_dialog_folder_counts_as_raw_but_never_becomes_a_candidate() -> None:
    item = channel(251, broadcast=True, megagroup=False)
    peer = types.PeerChannel(251)
    folder = types.Folder(id=1, title="Archived")
    folder_dialog = types.DialogFolder(
        folder=folder,
        peer=peer,
        top_message=11,
        unread_muted_peers_count=0,
        unread_unmuted_peers_count=0,
        unread_muted_messages_count=0,
        unread_unmuted_messages_count=0,
    )
    gateway, _client = make_gateway(
        [terminal_dialogs([dialog(peer, 12), folder_dialog], [item])]
    )

    result = discover(gateway)

    assert result.complete is True
    assert result.stats.raw_dialogs_received == 2
    assert len(result.channels) == 1
    assert result.channels[0].telegram_chat_id == -1_000_000_000_251


def test_pagination_uses_last_raw_dialog_cursor_and_counts_every_dialog() -> None:
    first = channel(301, broadcast=True, megagroup=False)
    second = channel(302, megagroup=True)
    first_peer = types.PeerChannel(301)
    second_peer = types.PeerChannel(302)
    gateway, client = make_gateway(
        [
            dialogs_slice([dialog(first_peer, 41)], [first], count=2),
            terminal_dialogs([dialog(second_peer, 42)], [second]),
        ],
        limits=DiscoveryLimits(page_size=1, max_raw_dialogs=2),
    )

    result = discover(gateway, DiscoveryLimits(page_size=1, max_raw_dialogs=2))

    requests = [call for call in client.calls if isinstance(call, GetDialogsRequest)]
    assert len(requests) == 2
    assert requests[0].offset_id == 0
    assert requests[1].offset_id == 41
    assert requests[1].offset_peer.channel_id == 301
    assert requests[1].offset_date == _NOW
    assert requests[1].exclude_pinned is True
    assert result.complete is True
    assert result.stats.pages_requested == result.stats.pages_received == 2
    assert result.stats.raw_dialogs_received == 2
    assert [item.telegram_chat_id for item in result.channels] == [
        -1_000_000_000_301,
        -1_000_000_000_302,
    ]


def test_pinned_dialog_overflow_is_counted_and_paginated_by_adapter() -> None:
    entities = [
        channel(800 + index, broadcast=True, megagroup=False)
        for index in range(101)
    ]
    rows = [
        dialog(
            types.PeerChannel(entity.id),
            index + 1,
            pinned=True if index == 0 else None,
        )
        for index, entity in enumerate(entities)
    ]
    first_page = dialogs_slice(rows, entities, count=101)
    gateway, client = make_gateway([first_page, terminal_dialogs([], [])])

    result = discover(gateway)

    requests = [call for call in client.calls if isinstance(call, GetDialogsRequest)]
    assert len(requests) == 2
    assert [request.limit for request in requests] == [100, 100]
    assert [request.exclude_pinned for request in requests] == [False, True]
    assert requests[1].offset_id == 101
    assert requests[1].offset_peer.channel_id == entities[-1].id
    assert result.complete is True
    assert result.stats.raw_dialogs_received == 101
    assert len(result.channels) == 101
    assert result.channels[-1].telegram_chat_id == utils.get_peer_id(entities[-1])
    assert result.channels[-1].kind is ChannelKind.BROADCAST_CHANNEL
    assert client.closed == 1


def test_pinned_dialog_overflow_still_obeys_raw_dialog_budget() -> None:
    entities = [
        channel(900 + index, broadcast=True, megagroup=False)
        for index in range(101)
    ]
    rows = [
        dialog(
            types.PeerChannel(entity.id),
            index + 1,
            pinned=True if index == 0 else None,
        )
        for index, entity in enumerate(entities)
    ]
    gateway, client = make_gateway(
        [dialogs_slice(rows, entities, count=101)],
        limits=DiscoveryLimits(max_raw_dialogs=100),
    )

    with pytest.raises(ChannelDiscoveryError) as caught:
        discover(gateway, DiscoveryLimits(max_raw_dialogs=100))

    assert caught.value.category is DiscoveryErrorCategory.ADAPTER_FAILURE
    assert client.closed == 1


@pytest.mark.parametrize(
    ("limits", "expected"),
    [
        (
            DiscoveryLimits(page_size=1, max_raw_dialogs=1),
            DiscoveryStopReason.RAW_DIALOG_LIMIT,
        ),
        (
            DiscoveryLimits(page_size=1, max_raw_dialogs=5, max_pages=1),
            DiscoveryStopReason.PAGE_LIMIT,
        ),
    ],
)
def test_full_slice_at_budget_returns_explicit_partial(limits, expected) -> None:
    item = channel(401, broadcast=True, megagroup=False)
    peer = types.PeerChannel(401)
    gateway, client = make_gateway(
        [dialogs_slice([dialog(peer, 51)], [item], count=100)], limits=limits
    )

    result = discover(gateway, limits)

    assert result.complete is False
    assert result.stop_reason is expected
    assert len(result.channels) == 1
    assert len([call for call in client.calls if isinstance(call, GetDialogsRequest)]) == 1


def test_empty_terminal_dialogs_is_complete_empty() -> None:
    gateway, _client = make_gateway([terminal_dialogs([], [])])

    result = discover(gateway)

    assert result.complete is True
    assert result.stop_reason is None
    assert result.channels == ()
    assert result.stats.raw_dialogs_received == 0


def test_short_slice_is_complete_but_count_contradiction_fails_closed() -> None:
    item = channel(501, broadcast=True, megagroup=False)
    peer = types.PeerChannel(501)
    complete_gateway, _client = make_gateway(
        [dialogs_slice([dialog(peer, 61)], [item], count=1)]
    )
    complete = discover(complete_gateway, DiscoveryLimits(page_size=10))
    assert complete.complete is True

    invalid_gateway, _client = make_gateway(
        [dialogs_slice([dialog(peer, 61)], [item], count=3)]
    )
    with pytest.raises(ChannelDiscoveryError) as caught:
        discover(invalid_gateway, DiscoveryLimits(page_size=10))
    assert caught.value.category is DiscoveryErrorCategory.ADAPTER_FAILURE


def test_deadline_returns_partial_and_cancels_pending_request() -> None:
    item = channel(601, broadcast=True, megagroup=False)
    peer = types.PeerChannel(601)
    gateway, client = make_gateway([terminal_dialogs([dialog(peer, 71)], [item])])
    client.call_delay = 0.1
    limits = DiscoveryLimits(operation_timeout_seconds=0.01)

    result = discover(gateway, limits)

    assert result.complete is False
    assert result.stop_reason is DiscoveryStopReason.TIME_BUDGET
    assert result.channels == ()
    assert client.closed == 1


def test_floodwait_is_translated_without_sleep_or_raw_error() -> None:
    gateway, client = make_gateway([])
    client.call_error = errors.FloodWaitError(request=None, capture=23)

    with pytest.raises(ChannelDiscoveryError) as caught:
        discover(gateway)

    assert caught.value.category is DiscoveryErrorCategory.RATE_LIMITED
    assert caught.value.retry_after_seconds == 23
    assert "FloodWait" not in str(caught.value)
    assert client.closed == 1


def test_inconsistent_response_and_repeated_cursor_fail_controlled() -> None:
    gateway, _client = make_gateway([DialogsNotModified(count=1)])
    with pytest.raises(ChannelDiscoveryError) as not_modified:
        discover(gateway)
    assert not_modified.value.category is DiscoveryErrorCategory.ADAPTER_FAILURE

    item = channel(701, broadcast=True, megagroup=False)
    peer = types.PeerChannel(701)
    repeated = dialogs_slice([dialog(peer, 81)], [item], count=5)
    gateway, _client = make_gateway(
        [repeated, repeated, repeated],
        limits=DiscoveryLimits(page_size=1, max_raw_dialogs=5, max_pages=5),
    )
    with pytest.raises(ChannelDiscoveryError) as cycle:
        discover(gateway, DiscoveryLimits(page_size=1, max_raw_dialogs=5, max_pages=5))
    assert cycle.value.category is DiscoveryErrorCategory.ADAPTER_FAILURE


def test_missing_cursor_and_server_overresponse_fail_closed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    item = channel(702, broadcast=True, megagroup=False)
    peer = types.PeerChannel(702)
    no_cursor = dialog(peer, 0)
    gateway, _client = make_gateway(
        [dialogs_slice([no_cursor], [item], count=2)],
        limits=DiscoveryLimits(page_size=1, max_raw_dialogs=5),
    )
    with pytest.raises(ChannelDiscoveryError) as missing:
        discover(gateway, DiscoveryLimits(page_size=1, max_raw_dialogs=5))
    assert missing.value.category is DiscoveryErrorCategory.ADAPTER_FAILURE

    second = channel(703, megagroup=True)
    gateway, _client = make_gateway(
        [
            terminal_dialogs(
                [dialog(peer, 91), dialog(types.PeerChannel(703), 92)],
                [item, second],
            )
        ],
        limits=DiscoveryLimits(page_size=1, max_raw_dialogs=5),
    )
    with pytest.raises(ChannelDiscoveryError) as overresponse:
        discover(gateway, DiscoveryLimits(page_size=1, max_raw_dialogs=5))
    assert overresponse.value.category is DiscoveryErrorCategory.ADAPTER_FAILURE
    assert "REASON=UNSUPPORTED_PAGE_OVERFLOW" in caplog.text
    assert "REQUESTED_LIMIT=1 RECEIVED=2" in caplog.text


def test_same_peer_with_incompatible_entity_classification_fails_closed() -> None:
    broadcast = channel(704, broadcast=True, megagroup=False)
    megagroup = channel(704, broadcast=False, megagroup=True)
    row = dialog(types.PeerChannel(704), 93)
    gateway, _client = make_gateway(
        [terminal_dialogs([row], [broadcast, megagroup])]
    )

    with pytest.raises(ChannelDiscoveryError) as caught:
        discover(gateway)

    assert caught.value.category is DiscoveryErrorCategory.ADAPTER_FAILURE


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (errors.ChannelPrivateError(request=None), DiscoveryErrorCategory.ACCESS_DENIED),
        (errors.ChannelInvalidError(request=None), DiscoveryErrorCategory.ACCESS_DENIED),
        (errors.AuthKeyUnregisteredError(request=None), DiscoveryErrorCategory.SESSION_INVALID),
        (OSError("synthetic network canary"), DiscoveryErrorCategory.NETWORK),
    ],
)
def test_known_auth_access_and_network_errors_have_project_categories(
    error: Exception, category: DiscoveryErrorCategory
) -> None:
    translated = TelethonGateway._discovery_failure(error)
    assert translated.category is category
    assert "canary" not in str(translated)


def test_unknown_adapter_error_is_sanitized_and_session_is_not_saved(
    caplog: pytest.LogCaptureFixture,
) -> None:
    gateway, client = make_gateway([])
    client.call_error = RuntimeError("INCIDENTAL_MESSAGE_CANARY")

    with caplog.at_level(logging.WARNING, logger="telegram_courses.telethon_gateway"):
        with pytest.raises(ChannelDiscoveryError) as caught:
            discover(gateway)

    assert caught.value.category is DiscoveryErrorCategory.ADAPTER_FAILURE
    assert "INCIDENTAL_MESSAGE_CANARY" not in str(caught.value)
    assert "CATEGORY=ADAPTER_FAILURE" in caplog.text
    assert "SANITIZED_EXCEPTION_CLASS=RuntimeError" in caplog.text
    assert "INCIDENTAL_MESSAGE_CANARY" not in caplog.text
    assert gateway._vault.saved == []
    assert client.closed == 1
