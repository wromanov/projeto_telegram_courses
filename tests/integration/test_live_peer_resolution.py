from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from telethon import utils
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import (
    Channel,
    ChannelForbidden,
    ChatPhotoEmpty,
    InputPeerChannel,
    PeerChannel,
)
from telethon.tl.types.messages import DialogsNotModified

from telegram_courses.auth import AuthState
from telegram_courses.channel_discovery import (
    ChannelDiscoveryError,
    DiscoveryErrorCategory,
    DiscoveryRequest,
)
from telegram_courses.message_scanner import ScanGatewayError
from telegram_courses.telethon_gateway import TelethonGateway

RAW_ID = 424242
CHANNEL_ID = utils.get_peer_id(PeerChannel(RAW_ID))
CANARY = "PRIVATE_EXCEPTION_CONTENT_CANARY"


class Dialogs:
    def __init__(self, dialogs, chats):
        self.dialogs = dialogs
        self.chats = chats


class FakeClient:
    _request_retries = 0
    _connection_retries = 0
    _auto_reconnect = False
    _flood_sleep_threshold = 0

    def __init__(self, response):
        self.response = response
        self.requests = []
        self.iterated_peer = None

    async def get_input_entity(self, _channel_id):
        raise ValueError(CANARY)

    async def __call__(self, request):
        self.requests.append(request)
        return self.response

    async def iter_messages(self, entity, **_options):
        self.iterated_peer = entity
        yield SimpleNamespace(
            id=7, date=datetime(2026, 1, 1, tzinfo=UTC), edit_date=None,
            message="Aula sintética", grouped_id=None, media=None,
        )


def gateway(client, configured_id=CHANNEL_ID):
    result = object.__new__(TelethonGateway)
    result._client = client
    result._state = AuthState.AUTHENTICATED
    result._bounded_metadata_channel_id = configured_id
    result._strict_budget_lock = asyncio.Lock()
    result._strict_budget_streams = 0
    result._strict_budget_previous_retries = None
    result._metadata_rpc_lock = asyncio.Lock()
    result._selected_metadata_peer = None
    result._metadata_peer_recovery_reason = None
    result._metadata_dialog_rpcs = 0
    result._metadata_dialogs_inspected = 0
    result._metadata_message_rpcs = 0
    result._metadata_messages_inspected = 0
    return result


def channel():
    return Channel(
        id=RAW_ID, title="Canal sintético", photo=ChatPhotoEmpty(),
        date=datetime(2026, 1, 1, tzinfo=UTC), access_hash=456,
        broadcast=True, megagroup=False,
    )


def test_scanner_recovers_only_confirmed_peer_and_keeps_message_text():
    async def run():
        client = FakeClient(Dialogs([SimpleNamespace(peer=PeerChannel(RAW_ID))], [channel()]))
        adapter = gateway(client)
        messages = [
            message async for message in adapter.iter_channel_messages(
                CHANNEL_ID, through_message_id=None, before_message_id=None, limit=2,
            )
        ]
        assert [message.text for message in messages] == ["Aula sintética"]
        assert isinstance(client.iterated_peer, InputPeerChannel)
        assert client.iterated_peer.channel_id == RAW_ID
        assert len(client.requests) == 1
        assert isinstance(client.requests[0], GetDialogsRequest)
        assert client.requests[0].limit == 100
        assert client.requests[0].exclude_pinned is True
        assert adapter._metadata_dialog_rpcs == 1

    asyncio.run(run())


@pytest.mark.parametrize("configured", [None, CHANNEL_ID - 1])
def test_different_or_absent_scope_never_calls_recovery(configured):
    async def run():
        client = FakeClient(Dialogs([], []))
        adapter = gateway(client, configured)
        with pytest.raises(ScanGatewayError) as caught:
            await adapter._input_entity_for_selected_channel(
                CHANNEL_ID, allow_bounded_recovery=True,
            )
        assert caught.value.category == "CHANNEL_UNRESOLVED"
        assert client.requests == []

    asyncio.run(run())


def test_target_absent_does_not_select_other_channel_or_retry():
    async def run():
        client = FakeClient(Dialogs([SimpleNamespace(peer=PeerChannel(RAW_ID + 1))], [channel()]))
        adapter = gateway(client)
        with pytest.raises(ScanGatewayError) as caught:
            await adapter._input_entity_for_selected_channel(
                CHANNEL_ID, allow_bounded_recovery=True,
            )
        assert caught.value.category == "CHANNEL_UNRESOLVED"
        assert len(client.requests) == 1
        assert adapter._selected_metadata_peer is None

    asyncio.run(run())


def test_access_denied_propagates_and_download_path_does_not_recover(caplog):
    async def run():
        forbidden = ChannelForbidden(
            id=RAW_ID, access_hash=456, title="synthetic", broadcast=True,
        )
        client = FakeClient(Dialogs([SimpleNamespace(peer=PeerChannel(RAW_ID))], [forbidden]))
        adapter = gateway(client)
        with pytest.raises(ScanGatewayError) as caught:
            await adapter._input_entity_for_selected_channel(
                CHANNEL_ID, allow_bounded_recovery=True,
            )
        assert caught.value.category == "ACCESS_DENIED"
        assert len(client.requests) == 1
        other = FakeClient(Dialogs([], []))
        with pytest.raises(ScanGatewayError):
            await gateway(other)._input_entity_for_selected_channel(CHANNEL_ID)
        assert other.requests == []

    with caplog.at_level(logging.WARNING):
        asyncio.run(run())
    assert "REASON=TARGET_FORBIDDEN" in caplog.text
    assert CANARY not in caplog.text


def test_discovery_invalid_response_reports_safe_reason(caplog):
    async def run():
        client = FakeClient(DialogsNotModified(count=0))
        adapter = gateway(client)
        adapter._receive_updates = False
        adapter._catch_up = False
        with pytest.raises(ChannelDiscoveryError) as caught:
            await adapter.discover_channels(DiscoveryRequest())
        assert caught.value.category is DiscoveryErrorCategory.ADAPTER_FAILURE

    with caplog.at_level(logging.WARNING):
        asyncio.run(run())
    assert "FAILURE_STAGE=RESPONSE_VALIDATION" in caplog.text
    assert "REASON=RESPONSE_NOT_MODIFIED" in caplog.text
    assert CANARY not in caplog.text
