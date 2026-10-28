from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from telethon import errors, utils
from telethon.tl.functions.messages import GetDialogsRequest, GetHistoryRequest
from telethon.tl.types import (
    Channel,
    ChannelForbidden,
    ChatPhotoEmpty,
    InputPeerChannel,
    PeerChannel,
)

from telegram_courses.auth import AuthState
from telegram_courses.config import ConfigurationError
from telegram_courses.message_scanner import ScanGatewayError
from telegram_courses.telethon_gateway import (
    S6_PEER_RECOVERY_REASONS,
    TelethonGateway,
)

RAW_CHANNEL_ID = 424242
CHANNEL_ID = utils.get_peer_id(PeerChannel(RAW_CHANNEL_ID))


class Dialogs:
    def __init__(self, dialogs, chats):
        self.dialogs = dialogs
        self.chats = chats

    @property
    def messages(self):
        raise AssertionError("response.messages must never be read")


def _channel(
    *, channel_id=RAW_CHANNEL_ID, access_hash=456, title="synthetic-channel", min=False
):
    return Channel(
        id=channel_id,
        title=title,
        photo=ChatPhotoEmpty(),
        date=datetime(2026, 10, 17, tzinfo=UTC),
        access_hash=access_hash,
        broadcast=True,
        megagroup=False,
        min=min,
    )


def _dialog(channel_id=RAW_CHANNEL_ID):
    return SimpleNamespace(peer=PeerChannel(channel_id))


class FakeClient:
    _request_retries = 0
    _connection_retries = 0
    _auto_reconnect = False
    _flood_sleep_threshold = 0

    def __init__(self, responses=()):
        self.responses = list(responses)
        self.requests = []
        self.in_flight = 0
        self.max_in_flight = 0
        self.session = SimpleNamespace(
            get_input_entity=lambda _peer: (_ for _ in ()).throw(
                AssertionError("public/local fallback resolver forbidden")
            )
        )

    async def __call__(self, request):
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        self.requests.append(request)
        try:
            if isinstance(self.responses[0], BaseException):
                raise self.responses.pop(0)
            return self.responses.pop(0)
        finally:
            self.in_flight -= 1


def _gateway(client, *, configured_channel_id=CHANNEL_ID):
    gateway = object.__new__(TelethonGateway)
    gateway._client = client
    gateway._bounded_metadata_channel_id = configured_channel_id
    gateway._state = AuthState.AUTHENTICATED
    gateway._strict_budget_lock = asyncio.Lock()
    gateway._strict_budget_streams = 0
    gateway._strict_budget_previous_retries = None
    gateway._metadata_rpc_lock = asyncio.Lock()
    gateway._selected_metadata_peer = None
    gateway._metadata_peer_recovery_reason = None
    gateway._metadata_dialog_rpcs = 0
    gateway._metadata_dialogs_inspected = 0
    gateway._metadata_message_rpcs = 0
    gateway._metadata_messages_inspected = 0
    return gateway


def test_missing_target_configuration_fails_before_rpc_even_with_cached_peer():
    async def exercise():
        client = FakeClient([Dialogs([_dialog()], [_channel()])])
        gateway = _gateway(client, configured_channel_id=None)
        gateway._selected_metadata_peer = InputPeerChannel(RAW_CHANNEL_ID, 456)

        with pytest.raises(ConfigurationError) as recovery_error:
            await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert str(recovery_error.value) == ""

        with pytest.raises(ConfigurationError) as metadata_error:
            [
                item
                async for item in gateway.iter_channel_metadata(
                    CHANNEL_ID, max_messages=10
                )
            ]
        assert str(metadata_error.value) == ""
        assert client.requests == []
        assert gateway._selected_metadata_peer == InputPeerChannel(
            RAW_CHANNEL_ID, 456
        )

    asyncio.run(exercise())


def test_request_for_different_target_fails_before_cached_peer_or_rpc():
    async def exercise():
        client = FakeClient()
        gateway = _gateway(client)
        selected_peer = InputPeerChannel(RAW_CHANNEL_ID, 456)
        gateway._selected_metadata_peer = selected_peer

        with pytest.raises(ValueError) as caught:
            await gateway.recover_selected_channel_peer(CHANNEL_ID + 1)
        assert str(caught.value) == "invalid bounded channel request"

        with pytest.raises(ValueError):
            [
                item
                async for item in gateway.iter_channel_metadata(
                    CHANNEL_ID + 1, max_messages=10
                )
            ]

        assert client.requests == []
        assert gateway._selected_metadata_peer is selected_peer

    asyncio.run(exercise())


def test_recovery_finds_only_exact_target_and_never_reads_previews():
    async def exercise():
        client = FakeClient([Dialogs([_dialog()], [_channel()])])
        gateway = _gateway(client)
        assert await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert isinstance(gateway._selected_metadata_peer, InputPeerChannel)
        assert gateway._selected_metadata_peer.channel_id == RAW_CHANNEL_ID
        assert client.requests[0].exclude_pinned is True
        assert client.requests[0].limit <= 100
        assert gateway._metadata_dialog_rpcs == 1
        assert gateway._metadata_dialogs_inspected == 1
        assert gateway._metadata_peer_recovery_reason == "PEER_RESOLVED"
        assert client.max_in_flight == 1
        assert not hasattr(client, "get_file")
        assert not hasattr(client, "get_file_hashes")

    asyncio.run(exercise())


def test_same_title_on_different_id_is_not_examined_or_selected():
    class Dialogs:
        dialogs = [_dialog(RAW_CHANNEL_ID + 1)]
        chat_reads = 0

        @property
        def chats(self):
            self.chat_reads += 1
            return [_channel(channel_id=RAW_CHANNEL_ID + 1, title="synthetic-channel")]

        @property
        def messages(self):
            raise AssertionError("message previews must not be read")

    async def exercise():
        response = Dialogs()
        client = FakeClient([response])
        gateway = _gateway(client)
        assert not await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert gateway._selected_metadata_peer is None
        assert gateway._metadata_peer_recovery_reason == "TARGET_NOT_FOUND_IN_PAGE"
        assert response.chat_reads == 0
        assert client.responses == []
        assert client.requests[0].limit == 100
        assert len(client.requests) == 1

    asyncio.run(exercise())


def test_target_absent_is_inconclusive_and_stops_after_one_rpc():
    async def exercise():
        client = FakeClient([Dialogs([], [])])
        gateway = _gateway(client)
        assert not await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert gateway._metadata_dialog_rpcs == 1
        assert gateway._metadata_dialogs_inspected == 0
        assert gateway._metadata_peer_recovery_reason == "TARGET_NOT_FOUND_IN_PAGE"
        assert len(client.requests) == 1

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("entities", "category", "reason"),
    [
        (
            [ChannelForbidden(id=RAW_CHANNEL_ID, access_hash=456, title="synthetic-channel")],
            "ACCESS_DENIED",
            "TARGET_FORBIDDEN",
        ),
        ([], "CHANNEL_UNRESOLVED", "TARGET_ENTITY_MISSING"),
        (
            [_channel(access_hash=None)],
            "CHANNEL_UNRESOLVED",
            "TARGET_ENTITY_INVALID",
        ),
    ],
)
def test_target_entity_must_be_readable_channel_with_access_hash(
    entities, category, reason
):
    async def exercise():
        client = FakeClient([Dialogs([_dialog()], entities)])
        gateway = _gateway(client)
        with pytest.raises(ScanGatewayError) as caught:
            await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert caught.value.category == category
        assert gateway._selected_metadata_peer is None
        assert gateway._metadata_peer_recovery_reason == reason

    asyncio.run(exercise())


def test_duplicate_channels_with_same_negative_hash_are_accepted():
    async def exercise():
        client = FakeClient([
            Dialogs(
                [_dialog()],
                [_channel(access_hash=-456), _channel(access_hash=-456)],
            )
        ])
        gateway = _gateway(client)
        assert await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert isinstance(gateway._selected_metadata_peer, InputPeerChannel)
        assert gateway._selected_metadata_peer.channel_id == RAW_CHANNEL_ID
        assert gateway._selected_metadata_peer.access_hash == -456
        assert gateway._metadata_peer_recovery_reason == "PEER_RESOLVED"
        assert await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert gateway._metadata_peer_recovery_reason == "PEER_RESOLVED"
        assert len(client.requests) == 1

    asyncio.run(exercise())


def test_min_channel_duplicate_blocks_valid_duplicate():
    async def exercise():
        client = FakeClient([
            Dialogs([_dialog()], [_channel(), _channel(min=True)])
        ])
        gateway = _gateway(client)
        with pytest.raises(ScanGatewayError) as caught:
            await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert caught.value.category == "CHANNEL_UNRESOLVED"
        assert gateway._metadata_peer_recovery_reason == "TARGET_ENTITY_INVALID"
        assert gateway._selected_metadata_peer is None

    asyncio.run(exercise())


def test_converted_hash_must_match_channel_hash(monkeypatch):
    checked_entities = []

    def mismatched_get_input_peer(entity, *, check_hash=False):
        checked_entities.append((entity, check_hash))
        return InputPeerChannel(RAW_CHANNEL_ID, 999)

    monkeypatch.setattr(utils, "get_input_peer", mismatched_get_input_peer)

    async def exercise():
        gateway = _gateway(FakeClient([
            Dialogs([_dialog()], [_channel(), _channel()])
        ]))
        with pytest.raises(ScanGatewayError) as caught:
            await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert caught.value.category == "CHANNEL_UNRESOLVED"
        assert gateway._metadata_peer_recovery_reason == "TARGET_ENTITY_INVALID"
        assert gateway._selected_metadata_peer is None

    asyncio.run(exercise())
    assert len(checked_entities) == 2
    assert all(check_hash is True for _, check_hash in checked_entities)


@pytest.mark.parametrize(
    ("entities", "category", "reason"),
    [
        (
            [_channel(access_hash=456), _channel(access_hash=789)],
            "ADAPTER_FAILURE",
            "TARGET_ENTITY_CONFLICT",
        ),
        (
            [
                _channel(access_hash=456),
                _channel(access_hash=789),
                _channel(access_hash=None),
            ],
            "ADAPTER_FAILURE",
            "TARGET_ENTITY_CONFLICT",
        ),
        (
            [
                _channel(access_hash=456),
                _channel(access_hash=789),
                _channel(access_hash=None),
                ChannelForbidden(
                    id=RAW_CHANNEL_ID, access_hash=456, title="sentinel-title"
                ),
            ],
            "ACCESS_DENIED",
            "TARGET_FORBIDDEN",
        ),
        (
            [_channel(access_hash=456), _channel(access_hash=None)],
            "CHANNEL_UNRESOLVED",
            "TARGET_ENTITY_INVALID",
        ),
    ],
)
def test_duplicate_channel_failure_precedence(
    entities, category, reason, monkeypatch
):
    original_get_input_peer = utils.get_input_peer
    checked_entities = []

    def tracked_get_input_peer(entity, *, check_hash=False):
        checked_entities.append(entity)
        return original_get_input_peer(entity, check_hash=check_hash)

    monkeypatch.setattr(utils, "get_input_peer", tracked_get_input_peer)

    async def exercise():
        gateway = _gateway(FakeClient([Dialogs([_dialog()], entities)]))
        with pytest.raises(ScanGatewayError) as caught:
            await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert caught.value.category == category
        assert gateway._metadata_peer_recovery_reason == reason
        assert gateway._selected_metadata_peer is None

    asyncio.run(exercise())
    assert len(checked_entities) == sum(
        isinstance(entity, Channel)
        and entity.id == RAW_CHANNEL_ID
        and type(entity.access_hash) is int
        and entity.access_hash != 0
        and (entity.min is None or entity.min is False)
        for entity in entities
    )


def test_dialog_overdelivery_is_rejected_before_iterating_dialogs(caplog):
    class NonIterableOverdelivery(list):
        def __iter__(self):
            raise AssertionError("over-delivered dialogs must not be examined")

    gateway = None

    async def exercise():
        nonlocal gateway
        client = FakeClient([Dialogs(NonIterableOverdelivery([1, 2]), [])])
        gateway = _gateway(client)
        await gateway.recover_selected_channel_peer(CHANNEL_ID, max_dialogs=1)
        assert gateway._metadata_dialogs_inspected == 2
        assert len(client.requests) == 1

    with pytest.raises(ScanGatewayError) as caught:
        asyncio.run(exercise())
    assert caught.value.category == "ADAPTER_FAILURE"
    assert gateway._metadata_peer_recovery_reason == "RAW_DIALOG_OVERDELIVERY"


@pytest.mark.parametrize(
    ("response", "category", "reason"),
    [
        (SimpleNamespace(), "ADAPTER_FAILURE", "INVALID_RESPONSE_TYPE"),
        (
            type("Dialogs", (), {"dialogs": None, "chats": []})(),
            "ADAPTER_FAILURE",
            "INVALID_DIALOG_COLLECTION",
        ),
        (
            type("Dialogs", (), {"dialogs": [_dialog()], "chats": None})(),
            "ADAPTER_FAILURE",
            "INVALID_CHAT_COLLECTION",
        ),
    ],
)
def test_malformed_dialog_responses_have_allowlisted_reasons(
    response, category, reason
):
    async def exercise():
        gateway = _gateway(FakeClient([response]))
        with pytest.raises(ScanGatewayError) as caught:
            await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert caught.value.category == category
        assert gateway._metadata_peer_recovery_reason == reason

    asyncio.run(exercise())


def test_peer_recovery_reason_is_allowlisted_and_cleanup_clears_it(caplog):
    async def exercise():
        gateway = _gateway(FakeClient([RuntimeError("sensitive-sentinel")]))
        gateway._closed = False
        with pytest.raises(ScanGatewayError):
            await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert gateway._metadata_peer_recovery_reason == "METADATA_RPC_FAILURE"
        gateway._selected_metadata_peer = InputPeerChannel(RAW_CHANNEL_ID, -456)

        async def disconnect():
            return None

        gateway._disconnect = disconnect
        await gateway.close()
        assert gateway._selected_metadata_peer is None
        assert gateway._metadata_peer_recovery_reason is None

    with caplog.at_level("WARNING"):
        asyncio.run(exercise())
    assert "sensitive-sentinel" not in caplog.text
    assert isinstance(S6_PEER_RECOVERY_REASONS, frozenset)



def test_dialog_limit_and_rpc_ceiling_are_enforced():
    async def exercise():
        client = FakeClient([Dialogs([], [])])
        gateway = _gateway(client)
        with pytest.raises(ValueError):
            await gateway.recover_selected_channel_peer(CHANNEL_ID, max_dialogs=101)
        assert client.requests == []
        assert not await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert len(client.requests) == 1
        assert gateway._metadata_peer_recovery_reason == "TARGET_NOT_FOUND_IN_PAGE"
        assert isinstance(client.requests[0], GetDialogsRequest)
        assert client.requests[0].limit == 100
        with pytest.raises(ScanGatewayError):
            await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert len(client.requests) == 1
        assert gateway._metadata_peer_recovery_reason == "DIALOG_BUDGET_EXHAUSTED"

    asyncio.run(exercise())


def test_floodwait_stops_without_retry_and_restores_client_controls():
    async def exercise():
        client = FakeClient([errors.FloodWaitError(request=None, capture=15)])
        client._request_retries = 4
        client._connection_retries = 3
        client._auto_reconnect = True
        client._flood_sleep_threshold = 30
        gateway = _gateway(client)
        with pytest.raises(ScanGatewayError) as caught:
            await gateway.recover_selected_channel_peer(CHANNEL_ID)
        assert caught.value.category == "RATE_LIMITED"
        assert gateway._metadata_peer_recovery_reason == "METADATA_RPC_FAILURE"
        assert len(client.requests) == 1
        assert client._request_retries == 4
        assert client._connection_retries == 3
        assert client._auto_reconnect is True
        assert client._flood_sleep_threshold == 30

    asyncio.run(exercise())


def test_metadata_uses_private_peer_and_only_history_without_media_or_storage():
    async def exercise():
        client = FakeClient([
            Dialogs([_dialog()], [_channel()]),
            SimpleNamespace(messages=[]),
        ])
        gateway = _gateway(client)
        assert await gateway.recover_selected_channel_peer(CHANNEL_ID)
        items = [item async for item in gateway.iter_channel_metadata(
            CHANNEL_ID, max_messages=200
        )]
        assert items == []
        assert [type(request) for request in client.requests] == [
            GetDialogsRequest,
            GetHistoryRequest,
        ]
        assert client.requests[1].peer.channel_id == RAW_CHANNEL_ID
        assert gateway._metadata_messages_inspected == 0
        assert gateway._metadata_message_rpcs == 1
        assert client.max_in_flight == 1
        assert client._request_retries == 0
        assert client._connection_retries == 0
        assert client._auto_reconnect is False
        assert client._flood_sleep_threshold == 0
        assert not hasattr(client, "get_file")
        assert not hasattr(client, "get_file_hashes")

    asyncio.run(exercise())


def test_document_metadata_projection_never_reads_message_body_or_file_bytes():
    class RawMessage:
        id = 77
        peer_id = PeerChannel(RAW_CHANNEL_ID)
        date = datetime(2026, 10, 17, tzinfo=UTC)
        edit_date = None
        grouped_id = None
        media = SimpleNamespace(
            document=SimpleNamespace(
                id=7788,
                mime_type="application/pdf",
                size=1024,
                attributes=[SimpleNamespace(file_name="proof.pdf")],
            ),
            photo=None,
        )

        @property
        def message(self):
            raise AssertionError("message body must not be read")

    async def exercise():
        client = FakeClient([
            Dialogs([_dialog()], [_channel()]),
            SimpleNamespace(messages=[RawMessage()]),
        ])
        gateway = _gateway(client)
        assert await gateway.recover_selected_channel_peer(CHANNEL_ID)
        items = [item async for item in gateway.iter_channel_metadata(
            CHANNEL_ID, max_messages=10
        )]
        assert len(items) == 1
        assert items[0].text is None
        assert items[0].media[0].telegram_media_id == "7788"
        assert items[0].media[0].file_size_bytes == 1024
        assert [type(request) for request in client.requests] == [
            GetDialogsRequest,
            GetHistoryRequest,
        ]
        assert gateway._metadata_messages_inspected == 1

    asyncio.run(exercise())


def test_failures_are_sanitized_and_close_clears_private_peer(caplog):
    async def exercise():
        client = FakeClient([RuntimeError("synthetic-sensitive-message-body")])
        gateway = _gateway(client)
        gateway._closed = False
        with pytest.raises(ScanGatewayError):
            await gateway.recover_selected_channel_peer(CHANNEL_ID)
        gateway._selected_metadata_peer = InputPeerChannel(RAW_CHANNEL_ID, 456)

        async def disconnect():
            return None

        gateway._disconnect = disconnect
        await gateway.close()
        assert gateway._selected_metadata_peer is None

    with caplog.at_level("WARNING"):
        asyncio.run(exercise())
    assert "synthetic-sensitive-message-body" not in caplog.text

