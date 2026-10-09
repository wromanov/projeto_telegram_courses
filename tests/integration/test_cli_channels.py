from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from telethon import types, utils

from telegram_courses import cli
from telegram_courses.auth import AuthState
from telegram_courses.channel_discovery import (
    ChannelKind,
    ChannelSummary,
    DiscoveryLimits,
    DiscoveryResult,
    DiscoveryStats,
    DiscoveryStopReason,
)
from telegram_courses.config import TelegramCredentials
from telegram_courses.telethon_gateway import TelethonGateway

_NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


class FakeVault:
    def _load(self) -> str:
        return "synthetic-protected-session"

    def _save(self, _value: str) -> None:
        raise AssertionError("discovery must not replace the session")


class FakeTelethonClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.requests: list[object] = []
        self.closed = 0

    async def connect(self) -> None:
        return None

    async def get_me(self) -> object:
        return object()

    async def disconnect(self) -> None:
        self.closed += 1

    async def __call__(self, request: object) -> object:
        self.requests.append(request)
        return self.responses.pop(0)


def telethon_channel(channel_id: int) -> types.Channel:
    return types.Channel(
        id=channel_id,
        title=f"Synthetic {channel_id}",
        photo=types.ChatPhotoEmpty(),
        date=_NOW,
        broadcast=True,
        megagroup=False,
        access_hash=channel_id + 1000,
    )


def telethon_dialog(
    peer: types.PeerChannel, message_id: int, *, pinned: bool | None = None
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


def snapshot(*, complete: bool = True) -> DiscoveryResult:
    limits = DiscoveryLimits()
    return DiscoveryResult(
        channels=(
            ChannelSummary(
                -1_000_000_000_123,
                "Course\x1b[31m [bold]Name[/bold]",
                "safe_user",
                ChannelKind.BROADCAST_CHANNEL,
            ),
        ),
        complete=complete,
        stop_reason=None if complete else DiscoveryStopReason.PAGE_LIMIT,
        stats=DiscoveryStats(1, 1, 1, 1, 0.1, limits),
    )


def multi_snapshot(*, complete: bool = True) -> DiscoveryResult:
    limits = DiscoveryLimits()
    return DiscoveryResult(
        channels=(
            ChannelSummary(
                -1_000_000_000_123,
                "Broadcast course",
                "broadcast_course",
                ChannelKind.BROADCAST_CHANNEL,
            ),
            ChannelSummary(
                -1_000_000_000_456,
                "Megagroup course",
                None,
                ChannelKind.MEGAGROUP,
            ),
        ),
        complete=complete,
        stop_reason=None if complete else DiscoveryStopReason.PAGE_LIMIT,
        stats=DiscoveryStats(2, 2, 2, 2, 0.1, limits),
    )


class FakeGateway:
    def __init__(
        self,
        *,
        state: AuthState = AuthState.AUTHENTICATED,
        discovery: DiscoveryResult | None = None,
    ) -> None:
        self.state = state
        self.discovery = discovery or snapshot()
        self.closed = False
        self.discovery_calls = 0

    async def restore(self) -> AuthState:
        return self.state

    async def discover_channels(self, request) -> DiscoveryResult:
        self.discovery_calls += 1
        assert request.limits == DiscoveryLimits()
        return self.discovery

    async def close(self) -> None:
        self.closed = True


def test_channels_command_lists_selects_locally_after_close(
    monkeypatch, capsys
) -> None:
    gateway = FakeGateway()
    monkeypatch.setattr(
        cli,
        "load_telegram_credentials",
        lambda: TelegramCredentials(7, "synthetic-api-hash"),
    )
    prompts_after_close: list[bool] = []
    prompt_messages: list[str] = []

    def selection_prompt(message: str) -> str:
        prompts_after_close.append(gateway.closed)
        prompt_messages.append(message)
        return "-1000000000123"

    result = cli.main(
        ["channels"],
        discovery_gateway_factory=lambda _credentials: gateway,
        selection_prompt=selection_prompt,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert gateway.discovery_calls == 1
    assert gateway.closed is True
    assert prompts_after_close == [True]
    assert prompt_messages == ["Select a number or Q to cancel: "]
    assert "discovery complete" in captured.out
    assert (
        "[1] Course[31m [bold]Name[/bold] @safe_user | BROADCAST_CHANNEL"
        in captured.out
    )
    assert "selected telegram_chat_id=-1000000000123" in captured.out
    assert "\x1b" not in captured.out
    assert "[bold]" in captured.out
    assert "INCIDENTAL" not in captured.out
    assert "synthetic-api-hash" not in captured.out + captured.err


@pytest.mark.parametrize("selection", ["q", "Q", ""])
def test_channels_command_displays_partial_and_cancel_has_no_selection(
    monkeypatch, capsys, selection
) -> None:
    gateway = FakeGateway(discovery=snapshot(complete=False))
    monkeypatch.setattr(
        cli,
        "load_telegram_credentials",
        lambda: TelegramCredentials(7, "synthetic-api-hash"),
    )

    result = cli.main(
        ["channels"],
        discovery_gateway_factory=lambda _credentials: gateway,
        selection_prompt=lambda _message: selection,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "discovery partial: PAGE_LIMIT" in captured.out
    assert "selection cancelled" in captured.out
    assert "selected telegram_chat_id" not in captured.out


@pytest.mark.parametrize(
    ("selection", "expected_id", "expected_kind"),
    [
        ("1", -1_000_000_000_123, "BROADCAST_CHANNEL"),
        ("2", -1_000_000_000_456, "MEGAGROUP"),
        ("-1000000000123", -1_000_000_000_123, "BROADCAST_CHANNEL"),
        ("-1000000000456", -1_000_000_000_456, "MEGAGROUP"),
    ],
)
def test_channels_command_selects_by_index_or_full_id_locally(
    monkeypatch, capsys, selection, expected_id, expected_kind
) -> None:
    gateway = FakeGateway(discovery=multi_snapshot(complete=False))
    monkeypatch.setattr(
        cli,
        "load_telegram_credentials",
        lambda: TelegramCredentials(7, "synthetic-api-hash"),
    )
    prompts_after_close: list[bool] = []

    def selection_prompt(message: str) -> str:
        prompts_after_close.append(gateway.closed)
        assert message == "Select a number or Q to cancel: "
        return selection

    result = cli.main(
        ["channels"],
        discovery_gateway_factory=lambda _credentials: gateway,
        selection_prompt=selection_prompt,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert gateway.discovery_calls == 1
    assert gateway.closed is True
    assert prompts_after_close == [True]
    assert "discovery partial: PAGE_LIMIT" in captured.out
    assert "[1] Broadcast course @broadcast_course | BROADCAST_CHANNEL" in captured.out
    assert "[2] Megagroup course | MEGAGROUP" in captured.out
    assert f"selected telegram_chat_id={expected_id} kind={expected_kind}" in captured.out
    assert "synthetic-api-hash" not in captured.out + captured.err


@pytest.mark.parametrize("selection", ["0", "3", "-1000000000", "abc"])
def test_channels_command_rejects_invalid_or_partial_selection(
    monkeypatch, capsys, selection
) -> None:
    gateway = FakeGateway(discovery=multi_snapshot())
    monkeypatch.setattr(
        cli,
        "load_telegram_credentials",
        lambda: TelegramCredentials(7, "synthetic-api-hash"),
    )

    result = cli.main(
        ["channels"],
        discovery_gateway_factory=lambda _credentials: gateway,
        selection_prompt=lambda _message: selection,
    )

    captured = capsys.readouterr()
    assert result == 3
    assert gateway.discovery_calls == 1
    assert gateway.closed is True
    assert "invalid channel selection" in captured.err
    assert "selected telegram_chat_id" not in captured.out
    assert "synthetic-api-hash" not in captured.out + captured.err


def test_channels_command_empty_snapshot_skips_selection_prompt(
    monkeypatch, capsys
) -> None:
    empty = DiscoveryResult(
        channels=(),
        complete=True,
        stop_reason=None,
        stats=DiscoveryStats(0, 0, 0, 0, 0.1, DiscoveryLimits()),
    )
    gateway = FakeGateway(discovery=empty)
    prompts: list[str] = []
    monkeypatch.setattr(
        cli,
        "load_telegram_credentials",
        lambda: TelegramCredentials(7, "synthetic-api-hash"),
    )

    result = cli.main(
        ["channels"],
        discovery_gateway_factory=lambda _credentials: gateway,
        selection_prompt=lambda message: prompts.append(message) or "1",
    )

    captured = capsys.readouterr()
    assert result == 0
    assert gateway.discovery_calls == 1
    assert gateway.closed is True
    assert prompts == []
    assert "no eligible channels" in captured.out
    assert "selected telegram_chat_id" not in captured.out
    assert "synthetic-api-hash" not in captured.out + captured.err


def test_channels_command_requires_existing_authentication_flow(
    monkeypatch, capsys
) -> None:
    gateway = FakeGateway(state=AuthState.AUTH_REQUIRED)
    prompts: list[str] = []
    monkeypatch.setattr(
        cli,
        "load_telegram_credentials",
        lambda: TelegramCredentials(7, "synthetic-api-hash"),
    )

    result = cli.main(
        ["channels"],
        discovery_gateway_factory=lambda _credentials: gateway,
        selection_prompt=lambda message: prompts.append(message) or "-1000000000123",
    )

    captured = capsys.readouterr()
    assert result == 3
    assert gateway.closed is True
    assert gateway.discovery_calls == 0
    assert prompts == []
    assert "run `telegram-courses auth`" in captured.out


def test_channels_command_lists_101_dialog_pinned_overflow_after_cleanup(
    monkeypatch, capsys
) -> None:
    entities = [telethon_channel(1200 + index) for index in range(101)]
    rows = [
        telethon_dialog(
            types.PeerChannel(entity.id),
            index + 1,
            pinned=True if index == 0 else None,
        )
        for index, entity in enumerate(entities)
    ]
    messages = [
        SimpleNamespace(id=index + 1, peer_id=row.peer, date=_NOW)
        for index, row in enumerate(rows)
    ]
    first_page = types.messages.DialogsSlice(
        count=101,
        dialogs=rows,
        messages=messages,
        chats=entities,
        users=[],
    )
    last_page = types.messages.Dialogs(dialogs=[], messages=[], chats=[], users=[])
    client = FakeTelethonClient([first_page, last_page])

    def gateway_factory(credentials: TelegramCredentials) -> TelethonGateway:
        return TelethonGateway(
            credentials,
            client_factory=lambda _session, *_args, **_kwargs: client,
            session_factory=lambda value: value,
            vault=FakeVault(),
            receive_updates=False,
            catch_up=False,
        )

    monkeypatch.setattr(
        cli,
        "load_telegram_credentials",
        lambda: TelegramCredentials(7, "synthetic-api-hash"),
    )
    selected_id = utils.get_peer_id(entities[-1])

    def select_after_disconnect(_prompt: str) -> str:
        assert client.closed == 1
        return str(selected_id)

    result = cli.main(
        ["channels"],
        discovery_gateway_factory=gateway_factory,
        selection_prompt=select_after_disconnect,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert len(client.requests) == 2
    assert [request.limit for request in client.requests] == [100, 100]
    assert [request.exclude_pinned for request in client.requests] == [False, True]
    assert "discovery complete" in captured.out
    assert captured.out.count(" | BROADCAST_CHANNEL") == 101
    assert f"selected telegram_chat_id={selected_id}" in captured.out
    assert client.closed == 1
