"""Private Telethon adapter for the project authentication boundary."""

from __future__ import annotations

import asyncio
import logging
import socket
import ssl
import time
import traceback
from importlib import import_module
from typing import Any, Callable

from telegram_courses.auth import (
    AdapterError,
    AuthenticationError,
    AuthRejected,
    AuthState,
    ExpiredCode,
    InvalidCode,
    InvalidPassword,
    InvalidSession,
    NetworkError,
    RateLimited,
)
from telegram_courses.channel_discovery import (
    ChannelDiscoveryError,
    ChannelKind,
    ChannelSummary,
    DiscoveryErrorCategory,
    DiscoveryLimits,
    DiscoveryRequest,
    DiscoveryResult,
    DiscoveryStats,
    DiscoveryStopReason,
)
from telegram_courses.config import ConfigurationError, TelegramCredentials
from telegram_courses.message_scanner import (
    GatewayMedia,
    GatewayMessage,
    ScanGatewayError,
)

_session_storage = import_module("telegram_courses.telethon_session")
IntegrityError = _session_storage.IntegrityError
StorageError = _session_storage.StorageError
_ProtectedSessionVault = _session_storage._ProtectedSessionVault

_DIAGNOSTIC_LOGGER = logging.getLogger(__name__)
_DISCOVERY_LOGGER = logging.getLogger(__name__)
_S6_MAX_DIALOGS = 200
_S6_MAX_DIALOG_RPCS = 3
S6_PEER_RECOVERY_REASONS = frozenset({
    "SESSION_UNAVAILABLE",
    "DIALOG_BUDGET_EXHAUSTED",
    "METADATA_RPC_FAILURE",
    "INVALID_RESPONSE_TYPE",
    "INVALID_DIALOG_COLLECTION",
    "RAW_DIALOG_OVERDELIVERY",
    "INVALID_TARGET_TYPE",
    "TARGET_NOT_FOUND_IN_PAGE",
    "INVALID_CHAT_COLLECTION",
    "TARGET_FORBIDDEN",
    "TARGET_ENTITY_MISSING",
    "TARGET_ENTITY_INVALID",
    "TARGET_ENTITY_CONFLICT",
    "PEER_RESOLVED",
})
_DISCOVERY_ADAPTER_REASONS = {
    "INVALID_LIMITS": "PROFILE",
    "INVALID_REQUEST": "PROFILE",
    "INVALID_STATE": "STATE",
    "INVALID_UPDATE_PROFILE": "PROFILE",
    "RESPONSE_NOT_MODIFIED": "RESPONSE_VALIDATION",
    "INVALID_RESPONSE_TYPE": "RESPONSE_VALIDATION",
    "INVALID_COLLECTIONS": "RESPONSE_VALIDATION",
    "RAW_BUDGET_EXCEEDED": "RESPONSE_VALIDATION",
    "UNSUPPORTED_PAGE_OVERFLOW": "RESPONSE_VALIDATION",
    "CONFLICTING_ENTITY": "RESPONSE_VALIDATION",
    "INVALID_CHANNEL_ID": "RESPONSE_VALIDATION",
    "CONFLICTING_CHANNEL": "RESPONSE_VALIDATION",
    "INVALID_RESPONSE_COUNT": "RESPONSE_VALIDATION",
    "CURSOR_MISSING": "CURSOR",
    "CURSOR_REPEATED": "CURSOR",
}
_FAILURE_STAGES = frozenset({
    "CLIENT_CREATION",
    "CONNECT",
    "SESSION_REUSE_CHECK",
    "REQUEST_CODE",
    "OTP_SUBMISSION",
    "2FA_SUBMISSION",
    "AUTHORIZATION_CONFIRMATION",
    "SESSION_PERSISTENCE",
    "DISCONNECT",
    "MEDIA_DOWNLOAD",
    "MEDIA_HASH",
})


def _discovery_adapter_failure(reason: str) -> ChannelDiscoveryError:
    """Record only predeclared diagnostics; never serialize Telegram objects."""
    stage = _DISCOVERY_ADAPTER_REASONS.get(reason)
    if stage is None:
        reason, stage = "INVALID_RESPONSE_TYPE", "RESPONSE_VALIDATION"
    _DISCOVERY_LOGGER.warning(
        "channel discovery FAILURE_STAGE=%s REASON=%s CATEGORY=ADAPTER_FAILURE",
        stage, reason,
    )
    return ChannelDiscoveryError(DiscoveryErrorCategory.ADAPTER_FAILURE)


def _direct_download_limit(expected_bytes: int, chunk_bytes: int) -> int:
    """Choose a Telethon direct-iterator limit compatible with aligned offsets."""
    if expected_bytes <= 0:
        return 1
    chunk_count = (expected_bytes + chunk_bytes - 1) // chunk_bytes
    limit = 1
    while limit < chunk_count:
        limit *= 2
    if (
        limit <= 0
        or limit < chunk_count
        or limit & (limit - 1)
        or chunk_bytes % limit != 0
    ):
        from telegram_courses.downloads import DownloadGatewayError

        raise DownloadGatewayError("DIRECT_ITERATOR_INCOMPATIBLE")
    return limit


def _log_invalid_chunk(code: str, chunk: Any, *, chunk_bytes: int) -> None:
    allowed_codes = {"CHUNK_TYPE", "CHUNK_EMPTY", "CHUNK_TOO_LARGE", "CHUNK_SHAPE"}
    safe_code = code if code in allowed_codes else "CHUNK_SHAPE"
    length: int | str = "UNAVAILABLE"
    ndim = itemsize = "NA"
    contiguous = "NA"
    if type(chunk) is bytes:
        length = len(chunk)
    elif isinstance(chunk, memoryview):
        try:
            candidate_length = chunk.nbytes
            candidate_ndim = chunk.ndim
            candidate_itemsize = chunk.itemsize
            candidate_contiguous = chunk.c_contiguous
            length = candidate_length if type(candidate_length) is int else "UNAVAILABLE"
            ndim = candidate_ndim if type(candidate_ndim) is int else "NA"
            itemsize = candidate_itemsize if type(candidate_itemsize) is int else "NA"
            contiguous = candidate_contiguous if type(candidate_contiguous) is bool else "NA"
        except Exception:
            pass
    _DIAGNOSTIC_LOGGER.warning(
        "media diagnostic FAILURE_CATEGORY=INVALID_CHUNK CHUNK_CODE=%s "
        "CHUNK_LENGTH=%s CHUNK_LIMIT=%d MEMORYVIEW_NDIM=%s "
        "MEMORYVIEW_ITEMSIZE=%s MEMORYVIEW_C_CONTIGUOUS=%s",
        safe_code, length, chunk_bytes, ndim, itemsize, contiguous,
    )


def _sanitized_exception_class(error: Exception) -> str:
    name = type(error).__name__
    if len(name) > 64 or not name.isascii() or not name.isidentifier():
        return "UnknownException"
    return name


def _sanitized_exception_traceback(error: Exception, *, max_frames: int = 8) -> str:
    """Return stack locations only; never include source lines or exception text."""
    extracted = traceback.extract_tb(error.__traceback__)
    if not extracted:
        return "UNAVAILABLE"
    locations: list[str] = []
    for frame in extracted[-max_frames:]:
        filename = frame.filename.replace("\\", "/").rsplit("/", 1)[-1]
        if (
            not filename.isascii()
            or not filename
            or any(not (char.isalnum() or char in "._-") for char in filename)
        ):
            filename = "UNKNOWN_FILE"
        function = frame.name
        if (
            not function.isascii()
            or not function
            or any(not (char.isalnum() or char in "_<>-") for char in function)
        ):
            function = "UNKNOWN_FUNCTION"
        locations.append(f"{filename}:{frame.lineno}:{function}")
    return " > ".join(locations)


def _project_error_category(error: Exception) -> str:
    if isinstance(error, NetworkError):
        return "NETWORK"
    if isinstance(error, ConfigurationError):
        return "CONFIGURATION"
    if isinstance(error, AdapterError):
        return "ADAPTER"
    if isinstance(error, AuthenticationError):
        return "AUTHENTICATION"
    return "ADAPTER"


class _PasswordChallenge(Exception):
    pass


def _client_logger() -> logging.Logger:
    logger = logging.Logger("telegram_courses.telethon_auth", logging.CRITICAL)
    logger.propagate = False
    logger.addHandler(logging.NullHandler())
    return logger


class TelethonGateway:
    """Owns all Telethon objects and session material for one auth attempt."""

    def __init__(
        self,
        credentials: TelegramCredentials,
        *,
        client_factory: Callable[..., Any] | None = None,
        session_factory: Callable[[str], Any] | None = None,
        vault: Any | None = None,
        receive_updates: bool | None = None,
        catch_up: bool | None = None,
        bounded_metadata_channel_id: int | None = None,
        allow_bounded_peer_recovery: bool = False,
        request_retries: int = 1,
        connection_retries: int = 1,
    ) -> None:
        self._bounded_metadata_channel_id = (
            self._validate_bounded_metadata_channel_id(
                bounded_metadata_channel_id
            )
        )
        if (receive_updates is None) != (catch_up is None):
            raise ValueError("discovery update profile must be complete")
        if type(allow_bounded_peer_recovery) is not bool:
            raise ValueError("invalid peer recovery policy")
        if receive_updates is not None and (
            type(receive_updates) is not bool or type(catch_up) is not bool
        ):
            raise ValueError("invalid update profile")
        if (
            type(request_retries) is not int
            or request_retries < 0
            or type(connection_retries) is not int
            or connection_retries < 0
        ):
            raise ValueError("retry counts must be non-negative integers")
        if client_factory is None or session_factory is None:
            try:
                from telethon import TelegramClient
                from telethon.sessions import StringSession
            except Exception as error:
                project_error = AdapterError()
                self._record_failure("CLIENT_CREATION", error, project_error)
                raise AdapterError from None
            client_factory = client_factory or TelegramClient
            session_factory = session_factory or StringSession
        self._credentials = credentials
        self._client_factory = client_factory
        self._session_factory = session_factory
        self._receive_updates = receive_updates
        self._catch_up = catch_up
        self._allow_bounded_peer_recovery = allow_bounded_peer_recovery
        self._request_retries = request_retries
        self._connection_retries = connection_retries
        try:
            self._vault = vault or _ProtectedSessionVault()
        except (StorageError, IntegrityError) as error:
            project_error = AdapterError()
            self._record_failure("SESSION_REUSE_CHECK", error, project_error)
            raise AdapterError from None
        self._client: Any | None = None
        self._strict_budget_lock = asyncio.Lock()
        self._strict_budget_streams = 0
        self._strict_budget_previous_retries: int | None = None
        self._phone: str | None = None
        self._phone_code_hash: str | None = None
        self._state: AuthState | None = None
        self._closed = False
        self._selected_metadata_peer: Any | None = None
        self._metadata_peer_recovery_reason: str | None = None
        self._metadata_dialog_rpcs = 0
        self._metadata_dialogs_inspected = 0
        self._metadata_message_rpcs = 0
        self._metadata_messages_inspected = 0
        self._metadata_rpc_lock = asyncio.Lock()

    @staticmethod
    def _validate_bounded_metadata_channel_id(
        channel_id: int | None,
    ) -> int | None:
        if channel_id is None:
            return None
        if (
            type(channel_id) is not int
            or channel_id < -(1 << 63)
            or channel_id > (1 << 63) - 1
        ):
            raise ConfigurationError from None
        try:
            from telethon import utils
            from telethon.tl.types import PeerChannel

            raw_id, peer_type = utils.resolve_id(channel_id)
            if (
                peer_type is not PeerChannel
                or type(raw_id) is not int
                or raw_id <= 0
                or utils.get_peer_id(PeerChannel(raw_id)) != channel_id
            ):
                raise ValueError
        except Exception:
            raise ConfigurationError from None
        return channel_id

    def _require_bounded_metadata_channel_id(
        self, requested_channel_id: int
    ) -> int:
        configured_channel_id = self._bounded_metadata_channel_id
        if configured_channel_id is None:
            raise ConfigurationError from None
        if (
            type(requested_channel_id) is not int
            or requested_channel_id != configured_channel_id
        ):
            raise ValueError("invalid bounded channel request")
        return configured_channel_id

    def _new_client(self, session: Any) -> Any:
        settings: dict[str, Any] = {
            "flood_sleep_threshold": 0,
            "request_retries": self._request_retries,
            "connection_retries": self._connection_retries,
            "raise_last_call_error": True,
            "auto_reconnect": False,
            "base_logger": _client_logger(),
        }
        if self._receive_updates is not None:
            settings["receive_updates"] = self._receive_updates
            settings["catch_up"] = self._catch_up
        return self._client_factory(
            session,
            self._credentials.api_id,
            self._credentials.api_hash,
            **settings,
        )

    @staticmethod
    def _peer_key(peer: Any) -> tuple[str, int] | None:
        from telethon.tl.types import PeerChannel, PeerChat, PeerUser

        if isinstance(peer, PeerChannel):
            return ("channel", peer.channel_id)
        if isinstance(peer, PeerChat):
            return ("chat", peer.chat_id)
        if isinstance(peer, PeerUser):
            return ("user", peer.user_id)
        return None

    @staticmethod
    def _entity_key(entity: Any) -> tuple[str, int] | None:
        from telethon.tl import types

        if isinstance(entity, (types.Channel, types.ChannelForbidden)):
            return ("channel", entity.id)
        if isinstance(entity, (types.Chat, types.ChatForbidden, types.ChatEmpty)):
            return ("chat", entity.id)
        if isinstance(entity, (types.User, types.UserEmpty)):
            return ("user", entity.id)
        return None

    @staticmethod
    def _discovery_failure(error: Exception) -> ChannelDiscoveryError:
        try:
            from telethon import errors
        except Exception:
            return ChannelDiscoveryError(DiscoveryErrorCategory.ADAPTER_FAILURE)

        if isinstance(error, errors.FloodWaitError):
            seconds = getattr(error, "seconds", None)
            if type(seconds) is int and seconds >= 0:
                return ChannelDiscoveryError(
                    DiscoveryErrorCategory.RATE_LIMITED,
                    retry_after_seconds=seconds,
                )
            return ChannelDiscoveryError(DiscoveryErrorCategory.ADAPTER_FAILURE)

        access_error_types = tuple(
            error_type
            for error_type in (
                getattr(errors, "ChannelPrivateError", None),
                getattr(errors, "ChannelInvalidError", None),
                getattr(errors, "ChannelPublicGroupNaError", None),
                getattr(errors, "ChatIdInvalidError", None),
            )
            if isinstance(error_type, type)
        )
        if access_error_types and isinstance(error, access_error_types):
            return ChannelDiscoveryError(DiscoveryErrorCategory.ACCESS_DENIED)

        try:
            TelethonGateway._translate(error)
        except InvalidSession:
            return ChannelDiscoveryError(DiscoveryErrorCategory.SESSION_INVALID)
        except AuthRejected:
            return ChannelDiscoveryError(DiscoveryErrorCategory.ACCESS_DENIED)
        except NetworkError:
            return ChannelDiscoveryError(DiscoveryErrorCategory.NETWORK)
        except RateLimited as rate_limited:
            return ChannelDiscoveryError(
                DiscoveryErrorCategory.RATE_LIMITED,
                retry_after_seconds=rate_limited.retry_after_seconds,
            )
        except Exception:
            return ChannelDiscoveryError(DiscoveryErrorCategory.ADAPTER_FAILURE)
        return ChannelDiscoveryError(DiscoveryErrorCategory.ADAPTER_FAILURE)

    @staticmethod
    def _channel_kind(entity: Any) -> ChannelKind | None:
        from telethon.tl import types

        if (
            not isinstance(entity, types.Channel)
            or getattr(entity, "left", False)
            or getattr(entity, "restricted", False)
        ):
            return None
        broadcast = getattr(entity, "broadcast", None)
        megagroup = getattr(entity, "megagroup", None)
        if broadcast is True and megagroup is False:
            return ChannelKind.BROADCAST_CHANNEL
        if broadcast is False and megagroup is True:
            return ChannelKind.MEGAGROUP
        return None

    @staticmethod
    def _valid_channel_id(entity: Any, marked_id: Any) -> bool:
        from telethon import utils
        from telethon.tl.types import PeerChannel

        if type(marked_id) is not int or marked_id >= -1_000_000_000_000:
            return False
        try:
            peer_id, peer_type = utils.resolve_id(marked_id)
            return peer_type is PeerChannel and peer_id == entity.id
        except Exception:
            return False

    @classmethod
    def _cursor_for_page(
        cls,
        dialogs: list[Any],
        messages: dict[tuple[tuple[str, int], int], Any],
        entities: dict[tuple[str, int], Any],
    ) -> tuple[int, Any, Any, tuple[str, int, int]] | None:
        from telethon import utils

        for dialog in reversed(dialogs):
            peer_key = cls._peer_key(getattr(dialog, "peer", None))
            message_id = getattr(dialog, "top_message", None)
            if peer_key is None or type(message_id) is not int or message_id <= 0:
                continue
            message = messages.get((peer_key, message_id))
            entity = entities.get(peer_key)
            if message is None or entity is None:
                continue
            date = getattr(message, "date", None)
            if date is None:
                continue
            try:
                input_peer = utils.get_input_peer(entity)
                date.timestamp()
            except Exception:
                continue
            return message_id, date, input_peer, (peer_key[0], peer_key[1], message_id)
        return None

    @staticmethod
    def _validate_limits(limits: DiscoveryLimits) -> None:
        if not isinstance(limits, DiscoveryLimits):
            raise _discovery_adapter_failure("INVALID_LIMITS")

    async def discover_channels(self, request: DiscoveryRequest) -> DiscoveryResult:
        """Enumerate dialogs using bounded requests and return metadata-only DTOs."""
        from telethon import utils
        from telethon.tl.functions.messages import GetDialogsRequest
        from telethon.tl.types import (
            DialogFolder,
            InputPeerEmpty,
            PeerChannel,
        )
        from telethon.tl.types.messages import (
            Dialogs as DialogsResult,
        )
        from telethon.tl.types.messages import (
            DialogsNotModified,
            DialogsSlice,
        )

        if not isinstance(request, DiscoveryRequest):
            raise _discovery_adapter_failure("INVALID_REQUEST")
        self._validate_limits(request.limits)
        if self._state is AuthState.AUTH_REQUIRED:
            raise ChannelDiscoveryError(DiscoveryErrorCategory.AUTH_REQUIRED)
        if self._state is AuthState.SESSION_INVALID:
            raise ChannelDiscoveryError(DiscoveryErrorCategory.SESSION_INVALID)
        if self._state is not AuthState.AUTHENTICATED or self._client is None:
            raise _discovery_adapter_failure("INVALID_STATE")
        if self._receive_updates is not False or self._catch_up is not False:
            raise _discovery_adapter_failure("INVALID_UPDATE_PROFILE")

        limits = request.limits
        deadline = request.deadline
        pages_requested = 0
        pages_received = 0
        raw_dialogs_received = 0
        candidates: dict[int, ChannelSummary] = {}
        cursors: set[tuple[str, int, int]] = set()
        offset_id = 0
        offset_date = None
        offset_peer: Any = InputPeerEmpty()
        exclude_pinned = False
        stop_reason: DiscoveryStopReason | None = None
        complete = False

        try:
            while True:
                remaining_raw = limits.max_raw_dialogs - raw_dialogs_received
                if remaining_raw <= 0:
                    stop_reason = DiscoveryStopReason.RAW_DIALOG_LIMIT
                    break
                if pages_requested >= limits.max_pages:
                    stop_reason = DiscoveryStopReason.PAGE_LIMIT
                    break
                remaining_time = deadline - time.monotonic()
                if remaining_time <= 0:
                    stop_reason = DiscoveryStopReason.TIME_BUDGET
                    break

                requested_limit = min(limits.page_size, remaining_raw)
                pages_requested += 1
                rpc = GetDialogsRequest(
                    offset_date=offset_date,
                    offset_id=offset_id,
                    offset_peer=offset_peer,
                    limit=requested_limit,
                    hash=0,
                    exclude_pinned=exclude_pinned,
                    folder_id=None,
                )
                try:
                    response = await asyncio.wait_for(
                        self._client(rpc), timeout=remaining_time
                    )
                except TimeoutError:
                    stop_reason = DiscoveryStopReason.TIME_BUDGET
                    break
                pages_received += 1

                if isinstance(response, DialogsNotModified):
                    raise _discovery_adapter_failure("RESPONSE_NOT_MODIFIED")
                if isinstance(response, DialogsResult):
                    response_is_terminal = True
                elif isinstance(response, DialogsSlice):
                    response_is_terminal = False
                else:
                    raise _discovery_adapter_failure("INVALID_RESPONSE_TYPE")

                page_dialogs = getattr(response, "dialogs", None)
                page_messages = getattr(response, "messages", None)
                page_chats = getattr(response, "chats", None)
                page_users = getattr(response, "users", None)
                if not all(
                    isinstance(items, (list, tuple))
                    for items in (page_dialogs, page_messages, page_chats, page_users)
                ):
                    raise _discovery_adapter_failure("INVALID_COLLECTIONS")

                raw_dialogs_received += len(page_dialogs)
                page_overflow = len(page_dialogs) - requested_limit
                pinned_dialogs = sum(
                    getattr(dialog, "pinned", False) is True
                    for dialog in page_dialogs
                )
                pinned_overflow = (
                    not exclude_pinned
                    and page_overflow > 0
                    and page_overflow <= pinned_dialogs
                )
                raw_budget_exceeded = len(page_dialogs) > remaining_raw
                if raw_budget_exceeded or (
                    page_overflow > 0 and not pinned_overflow
                ):
                    reason = (
                        "RAW_BUDGET_EXCEEDED"
                        if raw_budget_exceeded
                        else "UNSUPPORTED_PAGE_OVERFLOW"
                    )
                    _DISCOVERY_LOGGER.warning(
                        "channel discovery FAILURE_STAGE=RESPONSE_VALIDATION "
                        "REASON=%s REQUESTED_LIMIT=%d RECEIVED=%d "
                        "PINNED_DIALOGS=%d RAW_DIALOGS_RECEIVED=%d",
                        reason,
                        requested_limit,
                        len(page_dialogs),
                        pinned_dialogs,
                        raw_dialogs_received,
                    )
                    raise _discovery_adapter_failure(reason)

                entities: dict[tuple[str, int], Any] = {}
                for entity in (*page_chats, *page_users):
                    peer_key = self._entity_key(entity)
                    if peer_key is not None:
                        previous_entity = entities.get(peer_key)
                        if previous_entity is not None and (
                            type(previous_entity) is not type(entity)
                            or self._channel_kind(previous_entity)
                            is not self._channel_kind(entity)
                        ):
                            raise _discovery_adapter_failure("CONFLICTING_ENTITY")
                        entities[peer_key] = entity

                messages: dict[tuple[tuple[str, int], int], Any] = {}
                for message in page_messages:
                    peer_key = self._peer_key(getattr(message, "peer_id", None))
                    message_id = getattr(message, "id", None)
                    if peer_key is not None and type(message_id) is int:
                        messages[(peer_key, message_id)] = message

                for dialog in page_dialogs:
                    if isinstance(dialog, DialogFolder):
                        continue
                    peer = getattr(dialog, "peer", None)
                    if not isinstance(peer, PeerChannel):
                        continue
                    peer_key = self._peer_key(peer)
                    entity = entities.get(peer_key) if peer_key is not None else None
                    kind = self._channel_kind(entity)
                    if kind is None:
                        continue
                    marked_id = utils.get_peer_id(entity)
                    if not self._valid_channel_id(entity, marked_id):
                        raise _discovery_adapter_failure("INVALID_CHANNEL_ID")
                    channel = ChannelSummary(
                        telegram_chat_id=marked_id,
                        title=entity.title,
                        username=getattr(entity, "username", None),
                        kind=kind,
                    )
                    previous = candidates.get(marked_id)
                    if previous is not None and previous.kind is not kind:
                        raise _discovery_adapter_failure("CONFLICTING_CHANNEL")
                    candidates.setdefault(marked_id, channel)

                if time.monotonic() >= deadline:
                    stop_reason = DiscoveryStopReason.TIME_BUDGET
                    break
                if response_is_terminal:
                    complete = True
                    break

                if len(page_dialogs) < requested_limit:
                    total_count = getattr(response, "count", None)
                    if (
                        type(total_count) is not int
                        or total_count < 0
                        or total_count > raw_dialogs_received
                    ):
                        raise _discovery_adapter_failure("INVALID_RESPONSE_COUNT")
                    complete = True
                    break

                if time.monotonic() >= deadline:
                    stop_reason = DiscoveryStopReason.TIME_BUDGET
                    break
                if raw_dialogs_received >= limits.max_raw_dialogs:
                    stop_reason = DiscoveryStopReason.RAW_DIALOG_LIMIT
                    break
                if pages_requested >= limits.max_pages:
                    stop_reason = DiscoveryStopReason.PAGE_LIMIT
                    break

                cursor = self._cursor_for_page(page_dialogs, messages, entities)
                if cursor is None:
                    raise _discovery_adapter_failure("CURSOR_MISSING")
                offset_id, offset_date, offset_peer, fingerprint = cursor
                if fingerprint in cursors:
                    raise _discovery_adapter_failure("CURSOR_REPEATED")
                cursors.add(fingerprint)
                exclude_pinned = True

            elapsed = max(0.0, time.monotonic() - request.started_at)
            stats = DiscoveryStats(
                pages_requested=pages_requested,
                pages_received=pages_received,
                raw_dialogs_received=raw_dialogs_received,
                unique_candidates=len(candidates),
                elapsed_seconds=elapsed,
                limits=limits,
            )
            return DiscoveryResult(
                channels=tuple(candidates.values()),
                complete=complete,
                stop_reason=None if complete else stop_reason,
                stats=stats,
            )
        except asyncio.CancelledError:
            raise
        except ChannelDiscoveryError as error:
            _DISCOVERY_LOGGER.warning(
                "channel discovery CATEGORY=%s PAGES_REQUESTED=%d "
                "PAGES_RECEIVED=%d RAW_DIALOGS_RECEIVED=%d",
                error.category.value,
                pages_requested,
                pages_received,
                raw_dialogs_received,
            )
            raise
        except Exception as error:
            project_error = self._discovery_failure(error)
            _DISCOVERY_LOGGER.warning(
                "channel discovery FAILURE_STAGE=REQUEST_OR_RESPONSE "
                "CATEGORY=%s SANITIZED_EXCEPTION_CLASS=%s PAGES_REQUESTED=%d "
                "PAGES_RECEIVED=%d RAW_DIALOGS_RECEIVED=%d",
                project_error.category.value,
                _sanitized_exception_class(error),
                pages_requested,
                pages_received,
                raw_dialogs_received,
            )
            raise project_error from None

    async def _input_entity_for_selected_channel(
        self, telegram_chat_id: int, *, allow_bounded_recovery: bool | None = None,
    ) -> Any:
        if allow_bounded_recovery is None:
            allow_bounded_recovery = getattr(
                self, "_allow_bounded_peer_recovery", False,
            )
        try:
            return await self._client.get_input_entity(telegram_chat_id)
        except ValueError:
            if (
                allow_bounded_recovery
                and type(telegram_chat_id) is int
                and self._bounded_metadata_channel_id == telegram_chat_id
            ):
                try:
                    recovered = await self.recover_selected_channel_peer(
                        telegram_chat_id, max_dialogs=100,
                    )
                except ScanGatewayError:
                    reason = self._metadata_peer_recovery_reason
                    if reason not in S6_PEER_RECOVERY_REASONS:
                        reason = "METADATA_RPC_FAILURE"
                    _DISCOVERY_LOGGER.warning(
                        "channel resolution FAILURE_STAGE=PEER_RESOLUTION REASON=%s",
                        reason,
                    )
                    raise
                if recovered and self._selected_metadata_peer is not None:
                    _DISCOVERY_LOGGER.warning(
                        "channel resolution FAILURE_STAGE=PEER_RESOLUTION "
                        "REASON=PEER_RESOLVED"
                    )
                    return self._selected_metadata_peer
                _DISCOVERY_LOGGER.warning(
                    "channel resolution FAILURE_STAGE=PEER_RESOLUTION "
                    "REASON=TARGET_NOT_FOUND_IN_PAGE"
                )
            else:
                _DISCOVERY_LOGGER.warning(
                    "channel resolution FAILURE_STAGE=PEER_RESOLUTION "
                    "REASON=RECOVERY_NOT_AUTHORIZED_FOR_TARGET"
                )
            raise ScanGatewayError("CHANNEL_UNRESOLVED") from None

    @staticmethod
    def _raise_scan_failure(error: Exception) -> None:
        try:
            from telethon import errors
        except Exception:
            raise ScanGatewayError("ADAPTER_FAILURE") from None
        access_error_types = tuple(
            error_type
            for error_type in (
                getattr(errors, "ChannelPrivateError", None),
                getattr(errors, "ChannelInvalidError", None),
                getattr(errors, "ChannelPublicGroupNaError", None),
                getattr(errors, "ChatIdInvalidError", None),
            )
            if isinstance(error_type, type)
        )
        if access_error_types and isinstance(error, access_error_types):
            raise ScanGatewayError("ACCESS_DENIED") from None
        try:
            TelethonGateway._translate(error)
        except RateLimited as limited:
            raise ScanGatewayError(
                "RATE_LIMITED", retry_after_seconds=limited.retry_after_seconds
            ) from None
        except InvalidSession:
            raise ScanGatewayError("SESSION_INVALID") from None
        except NetworkError:
            raise ScanGatewayError("NETWORK") from None
        except Exception:
            raise ScanGatewayError("ADAPTER_FAILURE") from None
        raise ScanGatewayError("ADAPTER_FAILURE") from None

    async def _project_message(
        self,
        telegram_chat_id: int,
        message: Any,
        *,
        include_text: bool = True,
    ) -> GatewayMessage:
        from datetime import UTC

        date = message.date
        edit_date = getattr(message, "edit_date", None)
        media: list[GatewayMedia] = []
        raw_media = getattr(message, "media", None)
        if raw_media is not None:
            document = getattr(raw_media, "document", None)
            photo = getattr(raw_media, "photo", None)
            filename = None
            mime_type = None
            size = None
            media_id = None
            kind = "UNSUPPORTED"
            if document is not None:
                media_id = str(document.id)
                mime_type = getattr(document, "mime_type", None)
                size = getattr(document, "size", None)
                kind = "DOCUMENT"
                for attribute in getattr(document, "attributes", ()):
                    filename = filename or getattr(attribute, "file_name", None)
            elif photo is not None:
                media_id = str(photo.id)
                kind = "PHOTO"
            media.append(GatewayMedia(0, kind, media_id, filename, mime_type, size))
        return GatewayMessage(
            telegram_chat_id=telegram_chat_id,
            telegram_message_id=int(message.id),
            date_utc=date.astimezone(UTC).isoformat(),
            edit_date_utc=edit_date.astimezone(UTC).isoformat() if edit_date else None,
            text=(getattr(message, "message", None) or None) if include_text else None,
            grouped_id=getattr(message, "grouped_id", None),
            media=tuple(media),
        )

    async def _iterate_messages(
        self,
        telegram_chat_id: int,
        *,
        through_message_id: int | None,
        before_message_id: int | None,
        limit: int,
        min_message_id: int | None = None,
    ):
        if self._state is not AuthState.AUTHENTICATED or self._client is None:
            raise AdapterError from None
        try:
            entity = await self._input_entity_for_selected_channel(
                telegram_chat_id, allow_bounded_recovery=True,
            )
            options = {
                "offset_id": before_message_id or 0,
                "reverse": False,
                "limit": limit,
            }
            if through_message_id is not None:
                options["max_id"] = through_message_id + 1
            if min_message_id is not None:
                if type(min_message_id) is not int or min_message_id <= 0:
                    raise ValueError("invalid minimum message id")
                options["min_id"] = min_message_id - 1
            iterator = self._client.iter_messages(entity, **options)
            async for message in iterator:
                yield await self._project_message(telegram_chat_id, message)
        except ScanGatewayError:
            raise
        except Exception as error:
            self._record_failure("MESSAGE_HISTORY", error, AdapterError())
            self._raise_scan_failure(error)

    async def _iterate_media(
        self,
        channel_id: int,
        message_id: int,
        media_ordinal: int,
        *,
        telegram_media_id: str,
        expected_bytes: int,
        chunk_bytes: int,
        reserve_chunk=None,
        offset: int = 0,
    ):
        from telethon import utils

        from telegram_courses.downloads import DownloadGatewayError

        if self._state is not AuthState.AUTHENTICATED or self._client is None:
            raise DownloadGatewayError("SESSION_INVALID")
        try:
            entity = await self._input_entity_for_selected_channel(channel_id)
            message = await self._client.get_messages(entity, ids=message_id)
            if message is None or type(getattr(message, "id", None)) is not int or message.id != message_id:
                raise DownloadGatewayError("MESSAGE_NOT_FOUND")
            peer = getattr(message, "peer_id", None)
            if peer is None or utils.get_peer_id(peer) != channel_id:
                raise DownloadGatewayError("CHANNEL_MISMATCH")
            raw_media = getattr(message, "media", None)
            document = getattr(raw_media, "document", None) if raw_media is not None else None
            if document is None or media_ordinal != 0:
                raise DownloadGatewayError("MEDIA_MISMATCH")
            actual_id = str(getattr(document, "id", ""))
            actual_size = getattr(document, "size", None)
            if actual_id != telegram_media_id or type(actual_size) is not int or actual_size != expected_bytes:
                raise DownloadGatewayError("MEDIA_MISMATCH")
            if (
                type(offset) is not int or offset < 0 or offset > expected_bytes
                or offset % (256 * 1024) != 0
            ):
                raise DownloadGatewayError("INVALID_OFFSET")
            if not callable(reserve_chunk):
                raise DownloadGatewayError("BUDGET_ENFORCEMENT_UNAVAILABLE")
            limit = _direct_download_limit(expected_bytes, chunk_bytes)
            if offset % limit != 0:
                raise DownloadGatewayError("DIRECT_ITERATOR_INCOMPATIBLE")
            remaining = expected_bytes - offset
            if remaining == 0:
                return
            stream = self._client.iter_download(
                document, request_size=chunk_bytes, chunk_size=chunk_bytes,
                file_size=expected_bytes, offset=offset, limit=limit,
            )
            iterator_class = type(stream).__name__
            safe_iterator_class = (
                iterator_class
                if iterator_class in {"_DirectDownloadIter", "_GenericDownloadIter"}
                else "UNKNOWN"
            )
            _DIAGNOSTIC_LOGGER.warning(
                "media diagnostic ITERATOR_CLASS=%s DOWNLOAD_LIMIT=%d "
                "CHUNK_COUNT=%d",
                safe_iterator_class,
                limit,
                (expected_bytes + chunk_bytes - 1) // chunk_bytes,
            )
            if safe_iterator_class != "_DirectDownloadIter":
                raise DownloadGatewayError("DIRECT_ITERATOR_INCOMPATIBLE")
            if reserve_chunk is None:
                try:
                    async for chunk in stream:
                        if type(chunk) is not bytes:
                            _log_invalid_chunk("CHUNK_TYPE", chunk, chunk_bytes=chunk_bytes)
                            raise DownloadGatewayError("INVALID_CHUNK")
                        if not chunk:
                            _log_invalid_chunk("CHUNK_EMPTY", chunk, chunk_bytes=chunk_bytes)
                            raise DownloadGatewayError("INVALID_CHUNK")
                        if len(chunk) > chunk_bytes:
                            _log_invalid_chunk("CHUNK_TOO_LARGE", chunk, chunk_bytes=chunk_bytes)
                            raise DownloadGatewayError("INVALID_CHUNK")
                        if len(chunk) > remaining:
                            _log_invalid_chunk("CHUNK_SHAPE", chunk, chunk_bytes=remaining)
                            raise DownloadGatewayError("INVALID_CHUNK")
                        yield chunk
                        remaining -= len(chunk)
                        if remaining == 0:
                            break
                    if remaining:
                        raise DownloadGatewayError("SIZE_MISMATCH")
                finally:
                    close = getattr(stream, "close", None)
                    if callable(close):
                        await close()
            else:
                await self._begin_strict_budget_stream()
                try:
                    # Telethon 1.45 uses this hook for every GetFile request, including
                    # its internal timeout/migration retries. An explicit compatible
                    # limit selects its direct iterator, which does not prefetch.
                    request = getattr(stream, "_request", None)
                    if not callable(request):
                        raise DownloadGatewayError("BUDGET_ENFORCEMENT_UNAVAILABLE")

                    async def reserved_request():
                        request_limit = chunk_bytes
                        # Telegram's precise mode permits 1 KiB-aligned limits.
                        # Reserve the entire wire request, including its final
                        # alignment padding, before performing any RPC.
                        if 1024 <= chunk_bytes and remaining < chunk_bytes:
                            wire_request = getattr(stream, "request", None)
                            wire_offset = getattr(wire_request, "offset", None)
                            if (
                                wire_request is None
                                or type(wire_offset) is not int
                                or not hasattr(wire_request, "precise")
                                or wire_offset % 1024
                            ):
                                raise DownloadGatewayError("BUDGET_ENFORCEMENT_UNAVAILABLE")
                            request_limit = ((remaining + 1023) // 1024) * 1024
                            if (
                                request_limit <= 0
                                or request_limit > chunk_bytes
                                or wire_offset // (1024 * 1024)
                                != (wire_offset + request_limit - 1) // (1024 * 1024)
                            ):
                                raise DownloadGatewayError("BUDGET_ENFORCEMENT_UNAVAILABLE")
                            wire_request.limit = request_limit
                            wire_request.precise = True
                        try:
                            reservation = await reserve_chunk(request_limit)
                        except Exception as error:
                            from telegram_courses.downloads import DownloadError
                            if isinstance(error, DownloadError):
                                raise DownloadGatewayError(error.category) from None
                            raise
                        if reservation is None:
                            raise DownloadGatewayError("TRANSFER_BUDGET_EXHAUSTED")
                        try:
                            data = await request()
                        except BaseException:
                            reservation.charge_uncertain()
                            raise
                        if type(data) is not bytes:
                            reservation.charge_uncertain()
                            _log_invalid_chunk("CHUNK_TYPE", data, chunk_bytes=chunk_bytes)
                            raise DownloadGatewayError("INVALID_CHUNK")
                        if not data:
                            reservation.charge_uncertain()
                            _log_invalid_chunk("CHUNK_EMPTY", data, chunk_bytes=chunk_bytes)
                            raise DownloadGatewayError("INVALID_CHUNK")
                        if len(data) > request_limit:
                            _log_invalid_chunk("CHUNK_TOO_LARGE", data, chunk_bytes=request_limit)
                            try:
                                reservation.received(len(data))
                            except Exception as error:
                                from telegram_courses.downloads import DownloadError
                                if isinstance(error, DownloadError):
                                    raise DownloadGatewayError(error.category) from None
                                raise
                            raise DownloadGatewayError("INVALID_CHUNK")
                        try:
                            reservation.received(len(data))
                        except Exception as error:
                            from telegram_courses.downloads import DownloadError
                            if isinstance(error, DownloadError):
                                raise DownloadGatewayError(error.category) from None
                            raise
                        return data

                    stream._request = reserved_request
                    async for chunk in stream:
                        if type(chunk) is not bytes:
                            _log_invalid_chunk("CHUNK_TYPE", chunk, chunk_bytes=chunk_bytes)
                            raise DownloadGatewayError("INVALID_CHUNK")
                        if not chunk:
                            _log_invalid_chunk("CHUNK_EMPTY", chunk, chunk_bytes=chunk_bytes)
                            raise DownloadGatewayError("INVALID_CHUNK")
                        if len(chunk) > chunk_bytes:
                            _log_invalid_chunk("CHUNK_TOO_LARGE", chunk, chunk_bytes=chunk_bytes)
                            raise DownloadGatewayError("INVALID_CHUNK")
                        if len(chunk) > remaining:
                            _log_invalid_chunk("CHUNK_SHAPE", chunk, chunk_bytes=remaining)
                            raise DownloadGatewayError("INVALID_CHUNK")
                        yield chunk
                        remaining -= len(chunk)
                        if remaining == 0:
                            break
                    if remaining:
                        raise DownloadGatewayError("SIZE_MISMATCH")
                finally:
                    try:
                        close = getattr(stream, "close", None)
                        if callable(close):
                            await close()
                    finally:
                        await self._end_strict_budget_stream()
        except DownloadGatewayError:
            raise
        except Exception as error:
            self._record_failure("MEDIA_DOWNLOAD", error, AdapterError())
            try:
                from telethon import errors
                if isinstance(error, errors.FloodWaitError):
                    raise DownloadGatewayError(
                        "RATE_LIMITED", retry_after_seconds=int(error.seconds)
                    ) from None
                if isinstance(error, (OSError, TimeoutError, ConnectionError, asyncio.IncompleteReadError)):
                    raise DownloadGatewayError("NETWORK") from None
            except DownloadGatewayError:
                raise
            except Exception:
                pass
            raise DownloadGatewayError("GATEWAY_FAILURE") from None

    async def _begin_strict_budget_stream(self) -> None:
        from telegram_courses.downloads import DownloadGatewayError

        if self._client is None:
            raise DownloadGatewayError("SESSION_INVALID")
        async with self._strict_budget_lock:
            retries = getattr(self._client, "_request_retries", None)
            if type(retries) is not int:
                raise DownloadGatewayError("BUDGET_ENFORCEMENT_UNAVAILABLE")
            if self._strict_budget_streams == 0:
                self._strict_budget_previous_retries = retries
                self._client._request_retries = 0
            self._strict_budget_streams += 1

    async def _end_strict_budget_stream(self) -> None:
        if self._client is None:
            return
        async with self._strict_budget_lock:
            self._strict_budget_streams -= 1
            if self._strict_budget_streams == 0:
                self._client._request_retries = self._strict_budget_previous_retries
                self._strict_budget_previous_retries = None

    def stream_media(
        self,
        channel_id: int,
        message_id: int,
        media_ordinal: int,
        *,
        telegram_media_id: str,
        expected_bytes: int,
        chunk_bytes: int = 256 * 1024,
        reserve_chunk=None,
        offset: int = 0,
    ):
        if (
            type(channel_id) is not int or type(message_id) is not int
            or type(media_ordinal) is not int or type(expected_bytes) is not int
            or type(chunk_bytes) is not int or chunk_bytes <= 0 or chunk_bytes > 256 * 1024
            or type(offset) is not int or offset < 0 or offset > expected_bytes
            or (offset and (offset % (256 * 1024) != 0 or chunk_bytes != 256 * 1024))
            or not telegram_media_id or expected_bytes < 0
        ):
            raise ValueError("invalid media stream request")
        return self._iterate_media(
            channel_id, message_id, media_ordinal,
            telegram_media_id=telegram_media_id,
            expected_bytes=expected_bytes,
            chunk_bytes=chunk_bytes,
            reserve_chunk=reserve_chunk,
            offset=offset,
        )

    async def get_file_hashes(
        self,
        channel_id: int,
        message_id: int,
        media_ordinal: int,
        *,
        telegram_media_id: str,
        expected_bytes: int,
        offset: int = 0,
    ):
        from telethon import utils
        from telethon.tl.functions.upload import GetFileHashesRequest

        from telegram_courses.downloads import DownloadGatewayError, RemoteFileHash

        if (
            type(channel_id) is not int or type(message_id) is not int
            or type(media_ordinal) is not int or media_ordinal != 0 or not telegram_media_id
            or type(expected_bytes) is not int or expected_bytes < 0
            or type(offset) is not int or offset < 0 or offset > expected_bytes
        ):
            raise DownloadGatewayError("INVALID_HASH_REQUEST")
        if self._state is not AuthState.AUTHENTICATED or self._client is None:
            raise DownloadGatewayError("SESSION_INVALID")
        try:
            entity = await self._input_entity_for_selected_channel(channel_id)
            message = await self._client.get_messages(entity, ids=message_id)
            if message is None or type(getattr(message, "id", None)) is not int or message.id != message_id:
                raise DownloadGatewayError("MESSAGE_NOT_FOUND")
            peer = getattr(message, "peer_id", None)
            if peer is None or utils.get_peer_id(peer) != channel_id:
                raise DownloadGatewayError("CHANNEL_MISMATCH")
            raw_media = getattr(message, "media", None)
            document = getattr(raw_media, "document", None) if raw_media is not None else None
            if (
                document is None or str(getattr(document, "id", "")) != telegram_media_id
                or type(getattr(document, "size", None)) is not int
                or document.size != expected_bytes
            ):
                raise DownloadGatewayError("MEDIA_MISMATCH")
            _dc_id, location = utils.get_input_location(document)
            await self._begin_strict_budget_stream()
            try:
                response = await self._client(GetFileHashesRequest(location, offset))
            finally:
                await self._end_strict_budget_stream()
            if not isinstance(response, (tuple, list)):
                raise DownloadGatewayError("INVALID_HASH_RESPONSE")
            result: list[RemoteFileHash] = []
            for item in response:
                try:
                    item_offset, item_limit, item_hash = item.offset, item.limit, item.hash
                except (AttributeError, TypeError):
                    raise DownloadGatewayError("INVALID_HASH_RESPONSE") from None
                if (
                    type(item_offset) is not int
                    or type(item_limit) is not int
                    or not isinstance(item_hash, bytes)
                ):
                    raise DownloadGatewayError("INVALID_HASH_RESPONSE")
                result.append(RemoteFileHash(item_offset, item_limit, item_hash))
            return tuple(result)
        except DownloadGatewayError:
            raise
        except Exception as error:
            self._record_failure("MEDIA_HASH", error, AdapterError())
            try:
                from telethon import errors
                if isinstance(error, errors.FloodWaitError):
                    raise DownloadGatewayError(
                        "RATE_LIMITED", retry_after_seconds=int(error.seconds)
                    ) from None
                if isinstance(error, (OSError, TimeoutError, ConnectionError, asyncio.IncompleteReadError)):
                    raise DownloadGatewayError("NETWORK") from None
            except DownloadGatewayError:
                raise
            except Exception:
                pass
            raise DownloadGatewayError("REMOTE_HASHES_UNAVAILABLE") from None

    async def validate_media_identity(
        self,
        channel_id: int,
        message_id: int,
        media_ordinal: int,
        *,
        telegram_media_id: str,
        expected_bytes: int,
    ) -> bool:
        """Re-fetch and compare the selected remote document identity and size."""
        from telethon import utils

        from telegram_courses.downloads import DownloadGatewayError

        if (
            type(channel_id) is not int or type(message_id) is not int
            or type(media_ordinal) is not int or media_ordinal != 0
            or not telegram_media_id or type(expected_bytes) is not int or expected_bytes < 0
        ):
            raise DownloadGatewayError("INVALID_MEDIA_IDENTITY_REQUEST")
        if self._state is not AuthState.AUTHENTICATED or self._client is None:
            raise DownloadGatewayError("SESSION_INVALID")
        try:
            entity = await self._input_entity_for_selected_channel(channel_id)
            message = await self._client.get_messages(entity, ids=message_id)
            if message is None or type(getattr(message, "id", None)) is not int or message.id != message_id:
                raise DownloadGatewayError("MESSAGE_NOT_FOUND")
            peer = getattr(message, "peer_id", None)
            if peer is None or utils.get_peer_id(peer) != channel_id:
                raise DownloadGatewayError("CHANNEL_MISMATCH")
            raw_media = getattr(message, "media", None)
            document = getattr(raw_media, "document", None) if raw_media is not None else None
            if (
                document is None or str(getattr(document, "id", "")) != telegram_media_id
                or type(getattr(document, "size", None)) is not int
                or document.size != expected_bytes
            ):
                raise DownloadGatewayError("MEDIA_MISMATCH")
            return True
        except DownloadGatewayError:
            raise
        except Exception as error:
            self._record_failure("MEDIA_IDENTITY", error, AdapterError())
            try:
                self._translate(error)
            except DownloadGatewayError:
                raise
            raise DownloadGatewayError("GATEWAY_FAILURE") from None

    def iter_channel_messages(
        self,
        telegram_chat_id: int,
        *,
        through_message_id: int | None,
        before_message_id: int | None,
        limit: int,
        min_message_id: int | None = None,
    ):
        if type(limit) is not int or limit <= 0:
            raise ValueError("invalid message limit")
        return self._iterate_messages(
            telegram_chat_id,
            through_message_id=through_message_id,
            before_message_id=before_message_id,
            limit=limit,
            min_message_id=min_message_id,
        )

    async def _metadata_rpc(self, request: Any, *, stage: str) -> Any:
        if self._client is None:
            raise ScanGatewayError("SESSION_INVALID")
        async with self._metadata_rpc_lock:
            previous = {
                "connection_retries": getattr(
                    self._client, "_connection_retries", None
                ),
                "auto_reconnect": getattr(
                    self._client, "_auto_reconnect", None
                ),
                "flood_sleep_threshold": getattr(
                    self._client, "_flood_sleep_threshold", None
                ),
            }
            if (
                type(previous["connection_retries"]) is not int
                or type(previous["auto_reconnect"]) is not bool
                or type(previous["flood_sleep_threshold"]) not in (int, float)
            ):
                raise ScanGatewayError("ADAPTER_FAILURE")
            try:
                await self._begin_strict_budget_stream()
            except Exception:
                raise ScanGatewayError("ADAPTER_FAILURE") from None
            try:
                self._client._connection_retries = 0
                self._client._auto_reconnect = False
                self._client._flood_sleep_threshold = 0
                try:
                    request_name = type(request).__name__
                    if request_name == "GetDialogsRequest":
                        self._metadata_dialog_rpcs += 1
                    elif request_name == "GetHistoryRequest":
                        self._metadata_message_rpcs += 1
                    return await asyncio.wait_for(
                        self._client(request), timeout=30.0
                    )
                except asyncio.CancelledError:
                    raise
                except TimeoutError:
                    raise ScanGatewayError("NETWORK") from None
                except ScanGatewayError:
                    raise
                except Exception as error:
                    self._record_failure(stage, error, AdapterError())
                    self._raise_scan_failure(error)
            finally:
                self._client._connection_retries = previous["connection_retries"]
                self._client._auto_reconnect = previous["auto_reconnect"]
                self._client._flood_sleep_threshold = previous[
                    "flood_sleep_threshold"
                ]
                await self._end_strict_budget_stream()

    async def recover_selected_channel_peer(
        self, telegram_chat_id: int, *, max_dialogs: int = 100
    ) -> bool:
        """Resolve only the confirmed channel from one bounded dialog page."""
        configured_channel_id = self._require_bounded_metadata_channel_id(
            telegram_chat_id
        )
        from datetime import UTC, datetime

        from telethon import utils
        from telethon.tl.functions.messages import GetDialogsRequest
        from telethon.tl.types import (
            Channel,
            ChannelForbidden,
            InputPeerChannel,
            InputPeerEmpty,
            PeerChannel,
        )

        if (
            type(telegram_chat_id) is not int
            or type(max_dialogs) is not int
            or not 1 <= max_dialogs <= 100
        ):
            raise ValueError("invalid bounded channel recovery request")
        self._metadata_peer_recovery_reason = None
        if self._state is not AuthState.AUTHENTICATED or self._client is None:
            self._metadata_peer_recovery_reason = "SESSION_UNAVAILABLE"
            raise ScanGatewayError("SESSION_INVALID")
        if self._selected_metadata_peer is not None:
            self._metadata_peer_recovery_reason = "PEER_RESOLVED"
            return True
        remaining_dialog_budget = _S6_MAX_DIALOGS - self._metadata_dialogs_inspected
        if (
            self._metadata_dialog_rpcs >= 1
            or remaining_dialog_budget <= 0
            or self._metadata_dialog_rpcs >= _S6_MAX_DIALOG_RPCS
        ):
            self._metadata_peer_recovery_reason = "DIALOG_BUDGET_EXHAUSTED"
            raise ScanGatewayError("ADAPTER_FAILURE")
        requested_limit = min(max_dialogs, remaining_dialog_budget, 100)

        request = GetDialogsRequest(
            offset_date=datetime(1970, 1, 1, tzinfo=UTC),
            offset_id=0,
            offset_peer=InputPeerEmpty(),
            limit=requested_limit,
            hash=0,
            exclude_pinned=True,
            folder_id=None,
        )
        try:
            response = await self._metadata_rpc(request, stage="MESSAGE_HISTORY")
        except ScanGatewayError:
            self._metadata_peer_recovery_reason = "METADATA_RPC_FAILURE"
            raise
        if type(response).__name__ not in {"Dialogs", "DialogsSlice"}:
            self._metadata_peer_recovery_reason = "INVALID_RESPONSE_TYPE"
            raise ScanGatewayError("ADAPTER_FAILURE")

        dialogs = getattr(response, "dialogs", None)
        if not isinstance(dialogs, (list, tuple)):
            self._metadata_peer_recovery_reason = "INVALID_DIALOG_COLLECTION"
            raise ScanGatewayError("ADAPTER_FAILURE")
        raw_dialog_count = len(dialogs)
        self._metadata_dialogs_inspected += raw_dialog_count
        if (
            raw_dialog_count > requested_limit
            or self._metadata_dialogs_inspected > _S6_MAX_DIALOGS
        ):
            self._metadata_peer_recovery_reason = "RAW_DIALOG_OVERDELIVERY"
            _DISCOVERY_LOGGER.warning(
                "metadata peer recovery REASON=RAW_DIALOG_OVERDELIVERY "
                "REQUESTED_LIMIT=%d RECEIVED=%d",
                requested_limit,
                raw_dialog_count,
            )
            del response
            raise ScanGatewayError("ADAPTER_FAILURE")

        target_raw_id, target_type = utils.resolve_id(configured_channel_id)
        if target_type is not PeerChannel:
            self._metadata_peer_recovery_reason = "INVALID_TARGET_TYPE"
            raise ScanGatewayError("ADAPTER_FAILURE")
        target_present = False
        for dialog in dialogs:
            peer = getattr(dialog, "peer", None)
            if (
                isinstance(peer, PeerChannel)
                and type(peer.channel_id) is int
                and peer.channel_id == target_raw_id
            ):
                target_present = True
                break
        if not target_present:
            self._metadata_peer_recovery_reason = "TARGET_NOT_FOUND_IN_PAGE"
            del response
            return False

        entities = getattr(response, "chats", None)
        del response
        if not isinstance(entities, (list, tuple)):
            self._metadata_peer_recovery_reason = "INVALID_CHAT_COLLECTION"
            raise ScanGatewayError("ADAPTER_FAILURE")
        forbidden = False
        target_occurrences = 0
        invalid_target_entity = False
        conflicting_target_entities = False
        selected_signature: tuple[int, int] | None = None
        selected_peer: Any | None = None
        for entity in entities:
            if isinstance(entity, ChannelForbidden):
                entity_id = getattr(entity, "id", None)
                if type(entity_id) is int and entity_id == target_raw_id:
                    forbidden = True
            elif isinstance(entity, Channel):
                entity_id = getattr(entity, "id", None)
                if type(entity_id) is int and entity_id == target_raw_id:
                    target_occurrences += 1
                    access_hash = getattr(entity, "access_hash", None)
                    entity_min = getattr(entity, "min", None)
                    try:
                        if (
                            type(entity_id) is not int
                            or entity_id != target_raw_id
                            or type(access_hash) is not int
                            or access_hash == 0
                            or (entity_min is not None and entity_min is not False)
                        ):
                            raise ValueError("invalid target channel")
                        input_peer = utils.get_input_peer(entity, check_hash=True)
                        if (
                            not isinstance(input_peer, InputPeerChannel)
                            or type(getattr(input_peer, "channel_id", None)) is not int
                            or input_peer.channel_id != target_raw_id
                            or type(getattr(input_peer, "access_hash", None)) is not int
                            or input_peer.access_hash == 0
                            or input_peer.access_hash != access_hash
                        ):
                            raise ValueError("invalid target input peer")
                    except Exception:
                        invalid_target_entity = True
                        continue
                    signature = (input_peer.channel_id, input_peer.access_hash)
                    if selected_signature is None:
                        selected_signature = signature
                        selected_peer = input_peer
                    elif signature != selected_signature:
                        conflicting_target_entities = True
        if forbidden:
            self._metadata_peer_recovery_reason = "TARGET_FORBIDDEN"
            raise ScanGatewayError("ACCESS_DENIED")
        if conflicting_target_entities:
            self._metadata_peer_recovery_reason = "TARGET_ENTITY_CONFLICT"
            raise ScanGatewayError("ADAPTER_FAILURE")
        if invalid_target_entity:
            self._metadata_peer_recovery_reason = "TARGET_ENTITY_INVALID"
            raise ScanGatewayError("CHANNEL_UNRESOLVED")
        if target_occurrences == 0:
            self._metadata_peer_recovery_reason = "TARGET_ENTITY_MISSING"
            raise ScanGatewayError("CHANNEL_UNRESOLVED")
        self._selected_metadata_peer = selected_peer
        self._metadata_peer_recovery_reason = "PEER_RESOLVED"
        return True

    async def _iterate_channel_metadata(
        self, telegram_chat_id: int, *, max_messages: int
    ):
        configured_channel_id = self._require_bounded_metadata_channel_id(
            telegram_chat_id
        )
        from datetime import UTC, datetime

        from telethon import utils
        from telethon.tl.functions.messages import GetHistoryRequest
        from telethon.tl.types import InputPeerChannel, PeerChannel

        if self._state is not AuthState.AUTHENTICATED or self._client is None:
            raise ScanGatewayError("SESSION_INVALID")
        if type(telegram_chat_id) is not int:
            raise ValueError("invalid channel id")
        try:
            if type(max_messages) is not int or not 1 <= max_messages <= 200:
                raise ValueError("invalid metadata message limit")
            channel_id, peer_type = utils.resolve_id(telegram_chat_id)
            entity = self._selected_metadata_peer
            if (
                peer_type is not PeerChannel
                or channel_id
                != utils.resolve_id(configured_channel_id)[0]
            ):
                raise ValueError("invalid channel id")
            if entity is None:
                raise ScanGatewayError("CHANNEL_UNRESOLVED")
            if (
                not isinstance(entity, InputPeerChannel)
                or type(getattr(entity, "channel_id", None)) is not int
                or entity.channel_id != channel_id
                or type(getattr(entity, "access_hash", None)) is not int
                or entity.access_hash == 0
            ):
                raise ScanGatewayError("CHANNEL_UNRESOLVED")
            inspected = 0
            offset_id = 0
            per_call_budget = min(
                max_messages,
                max(0, 200 - self._metadata_messages_inspected),
            )
            while inspected < per_call_budget:
                page_limit = min(100, per_call_budget - inspected)
                request = GetHistoryRequest(
                    peer=entity,
                    offset_id=offset_id,
                    offset_date=datetime(1970, 1, 1, tzinfo=UTC),
                    add_offset=0,
                    limit=page_limit,
                    max_id=0,
                    min_id=0,
                    hash=0,
                )
                response = await self._metadata_rpc(
                    request, stage="MESSAGE_HISTORY"
                )
                raw_messages = getattr(response, "messages", None)
                if not isinstance(raw_messages, (list, tuple)):
                    raise ScanGatewayError("ADAPTER_FAILURE")
                raw_count = len(raw_messages)
                inspected += raw_count
                self._metadata_messages_inspected += raw_count
                if (
                    raw_count > page_limit
                    or self._metadata_messages_inspected > 200
                ):
                    raise ScanGatewayError("ADAPTER_FAILURE")
                if raw_count == 0:
                    break

                # Validate the whole raw page before emitting any DTO from it.
                for raw in raw_messages:
                    peer = getattr(raw, "peer_id", None)
                    try:
                        actual_id = utils.get_peer_id(peer)
                    except Exception:
                        raise ScanGatewayError("CHANNEL_UNRESOLVED") from None
                    if actual_id != telegram_chat_id:
                        raise ScanGatewayError("CHANNEL_UNRESOLVED")

                ids = [getattr(raw, "id", None) for raw in raw_messages]
                if any(
                    type(message_id) is not int or message_id <= 0
                    for message_id in ids
                ):
                    raise ScanGatewayError("ADAPTER_FAILURE")
                if any(left <= right for left, right in zip(ids, ids[1:])):
                    raise ScanGatewayError("ADAPTER_FAILURE")
                next_offset = min(ids)
                if next_offset <= 0 or (offset_id and next_offset >= offset_id):
                    raise ScanGatewayError("ADAPTER_FAILURE")

                from telethon.tl.types import MessageEmpty

                projected_messages = []
                for raw in raw_messages:
                    if isinstance(raw, MessageEmpty):
                        continue
                    projected_messages.append(
                        await self._project_message(
                            telegram_chat_id, raw, include_text=False
                        )
                    )
                del raw_messages, response, raw
                for projected_message in projected_messages:
                    yield projected_message
                if raw_count < page_limit or inspected >= per_call_budget:
                    break
                offset_id = next_offset
        except ScanGatewayError:
            raise
        except Exception as error:
            self._record_failure("MESSAGE_HISTORY", error, AdapterError())
            self._raise_scan_failure(error)

    def iter_channel_metadata(
        self, telegram_chat_id: int, *, max_messages: int
    ):
        if type(max_messages) is not int or not 1 <= max_messages <= 200:
            raise ValueError("invalid metadata message limit")
        return self._iterate_channel_metadata(
            telegram_chat_id, max_messages=max_messages
        )

    @staticmethod
    def _record_failure(
        stage: str, original: Exception, project_error: Exception
    ) -> None:
        safe_stage = stage if stage in _FAILURE_STAGES else "UNKNOWN"
        _DIAGNOSTIC_LOGGER.warning(
            "authentication diagnostic FAILURE_STAGE=%s "
            "SANITIZED_EXCEPTION_CLASS=%s PROJECT_ERROR_CATEGORY=%s "
            "SANITIZED_TRACEBACK=%s",
            safe_stage,
            _sanitized_exception_class(original),
            _project_error_category(project_error),
            _sanitized_exception_traceback(original),
        )

    def _translate_with_diagnostics(self, error: Exception, stage: str) -> None:
        try:
            self._translate(error)
        except _PasswordChallenge:
            raise
        except Exception as project_error:
            self._record_failure(stage, error, project_error)
            raise

    async def _disconnect(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            try:
                await client.disconnect()
            except Exception as error:
                project_error = AdapterError()
                self._record_failure("DISCONNECT", error, project_error)
                raise AdapterError from None

    @staticmethod
    def _translate(error: Exception) -> None:
        try:
            from telethon import errors
        except Exception:
            raise AdapterError from None
        if isinstance(error, errors.FloodWaitError):
            seconds = getattr(error, "seconds", None)
            if type(seconds) is not int or seconds < 0:
                raise AdapterError from None
            raise RateLimited(seconds) from None
        if isinstance(error, (errors.PhoneCodeExpiredError, errors.PhoneCodeHashEmptyError)):
            raise ExpiredCode from None
        if isinstance(error, (errors.PhoneCodeInvalidError, errors.PhoneCodeEmptyError)):
            raise InvalidCode from None
        if isinstance(error, errors.PasswordHashInvalidError):
            raise InvalidPassword from None
        if isinstance(error, errors.ApiIdInvalidError):
            raise ConfigurationError from None
        if isinstance(
            error,
            (
                errors.PhoneNumberInvalidError,
                errors.PhoneNumberBannedError,
                errors.PhoneNumberUnoccupiedError,
            ),
        ):
            raise AuthRejected from None
        if isinstance(error, errors.SessionPasswordNeededError):
            raise _PasswordChallenge from None
        if isinstance(
            error,
            (
                errors.AuthKeyInvalidError,
                errors.AuthKeyUnregisteredError,
                errors.SessionRevokedError,
                errors.SessionExpiredError,
                errors.UnauthorizedError,
            ),
        ):
            raise InvalidSession from None
        if isinstance(error, (errors.AuthKeyError, errors.AuthBytesInvalidError)):
            raise AuthRejected from None
        network_types = (
            asyncio.IncompleteReadError,
            OSError,
            TimeoutError,
            ConnectionError,
            socket.error,
            ssl.SSLError,
        )
        network_errors = tuple(
            item for item in (
                getattr(errors, "RpcCallFailError", None),
                getattr(errors, "ServerError", None),
                getattr(errors, "TimedOutError", None),
            ) if isinstance(item, type)
        )
        if isinstance(error, network_types + network_errors):
            raise NetworkError from None
        raise AdapterError from None

    async def _call(self, awaitable: Any, *, stage: str) -> Any:
        try:
            return await awaitable
        except _PasswordChallenge:
            raise
        except (ConfigurationError, AuthenticationError) as error:
            self._record_failure(stage, error, error)
            raise
        except (StorageError, IntegrityError) as error:
            project_error = AdapterError()
            self._record_failure(stage, error, project_error)
            raise AdapterError from None
        except Exception as error:
            self._translate_with_diagnostics(error, stage)

    async def _confirm_and_save(self) -> AuthState:
        stage = "AUTHORIZATION_CONFIRMATION"
        try:
            me = await self._call(
                self._client.get_me(), stage=stage
            )
            if me is None:
                error = AuthRejected()
                self._record_failure(stage, error, error)
                raise AuthRejected from None
            stage = "SESSION_PERSISTENCE"
            session_value = self._client.session.save()
            if not isinstance(session_value, str) or not session_value:
                error = AdapterError()
                self._record_failure(stage, error, error)
                raise AdapterError from None
            self._vault._save(session_value)
        except (ConfigurationError, AuthenticationError):
            raise
        except (StorageError, IntegrityError) as error:
            project_error = AdapterError()
            self._record_failure(stage, error, project_error)
            raise AdapterError from None
        except Exception as error:
            self._translate_with_diagnostics(error, stage)
        self._state = AuthState.AUTHENTICATED
        return self._state

    async def restore(self) -> AuthState:
        if self._state is not None:
            raise AdapterError from None
        stage = "SESSION_REUSE_CHECK"
        try:
            try:
                stored = self._vault._load()
            except ConfigurationError as error:
                self._record_failure(stage, error, error)
                raise
            except (StorageError, IntegrityError) as error:
                project_error = AdapterError()
                self._record_failure(stage, error, project_error)
                raise AdapterError from None

            stage = "CLIENT_CREATION"
            self._client = self._new_client(self._session_factory(stored or ""))
            stage = "CONNECT"
            await self._call(self._client.connect(), stage=stage)
            if stored is None:
                self._state = AuthState.AUTH_REQUIRED
                return self._state
            stage = "SESSION_REUSE_CHECK"
            me = await self._call(self._client.get_me(), stage=stage)
            if me is not None:
                self._state = AuthState.AUTHENTICATED
            else:
                self._state = AuthState.SESSION_INVALID
            return self._state
        except ConfigurationError:
            raise
        except (StorageError, IntegrityError) as error:
            project_error = AdapterError()
            self._record_failure(stage, error, project_error)
            raise AdapterError from None
        except InvalidSession:
            self._state = AuthState.SESSION_INVALID
            return self._state
        except AuthenticationError:
            raise
        except Exception as error:
            self._translate_with_diagnostics(error, stage)

    async def begin(self, phone: str) -> AuthState:
        if self._state not in {AuthState.AUTH_REQUIRED, AuthState.SESSION_INVALID}:
            raise AdapterError from None
        stage = "DISCONNECT"
        try:
            await self._disconnect()
            stage = "CLIENT_CREATION"
            self._client = self._new_client(self._session_factory(""))
            stage = "CONNECT"
            await self._call(self._client.connect(), stage=stage)
            self._phone = phone
            stage = "REQUEST_CODE"
            result = await self._call(
                self._client.send_code_request(phone), stage=stage
            )
            code_hash = getattr(result, "phone_code_hash", None)
            if not isinstance(code_hash, str) or not code_hash:
                error = AdapterError()
                self._record_failure(stage, error, error)
                raise AdapterError from None
            self._phone_code_hash = code_hash
            self._state = AuthState.CODE_REQUIRED
            return self._state
        except (ConfigurationError, AuthenticationError):
            raise
        except Exception as error:
            self._translate_with_diagnostics(error, stage)

    async def submit_code(self, code: str) -> AuthState:
        if (self._state is not AuthState.CODE_REQUIRED or self._phone is None
                or self._phone_code_hash is None):
            raise AdapterError from None
        try:
            await self._call(
                self._client.sign_in(
                    self._phone, code, phone_code_hash=self._phone_code_hash
                ),
                stage="OTP_SUBMISSION",
            )
        except ExpiredCode:
            self._state = AuthState.AUTH_REQUIRED
            self._phone_code_hash = None
            raise
        except AuthRejected:
            self._state = AuthState.AUTH_REQUIRED
            self._phone_code_hash = None
            raise
        except InvalidCode:
            raise
        except _PasswordChallenge:
            self._state = AuthState.PASSWORD_REQUIRED
            self._phone_code_hash = None
            return self._state
        self._phone_code_hash = None
        return await self._confirm_and_save()

    async def submit_password(self, password: str) -> AuthState:
        if self._state is not AuthState.PASSWORD_REQUIRED:
            raise AdapterError from None
        await self._call(
            self._client.sign_in(password=password), stage="2FA_SUBMISSION"
        )
        return await self._confirm_and_save()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._selected_metadata_peer = None
        self._metadata_peer_recovery_reason = None
        try:
            await self._disconnect()
        finally:
            self._selected_metadata_peer = None
            self._metadata_peer_recovery_reason = None
