"""Private Telethon adapter for the project authentication boundary."""

from __future__ import annotations

import asyncio
import logging
import socket
import ssl
import time
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
})


def _sanitized_exception_class(error: Exception) -> str:
    name = type(error).__name__
    if len(name) > 64 or not name.isascii() or not name.isidentifier():
        return "UnknownException"
    return name


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
        request_retries: int = 1,
        connection_retries: int = 1,
    ) -> None:
        if (receive_updates is None) != (catch_up is None):
            raise ValueError("discovery update profile must be complete")
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
        self._request_retries = request_retries
        self._connection_retries = connection_retries
        try:
            self._vault = vault or _ProtectedSessionVault()
        except (StorageError, IntegrityError) as error:
            project_error = AdapterError()
            self._record_failure("SESSION_REUSE_CHECK", error, project_error)
            raise AdapterError from None
        self._client: Any | None = None
        self._phone: str | None = None
        self._phone_code_hash: str | None = None
        self._state: AuthState | None = None
        self._closed = False

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
            raise ChannelDiscoveryError(DiscoveryErrorCategory.ADAPTER_FAILURE)

    async def discover_channels(self, request: DiscoveryRequest) -> DiscoveryResult:
        """Enumerate dialogs using bounded requests and return metadata-only DTOs."""
        from telethon import utils
        from telethon.tl.functions.messages import GetDialogsRequest
        from telethon.tl.types import (
            DialogFolder,
            InputPeerEmpty,
            PeerChannel,
        )
        from telethon.tl.types.messages import Dialogs as DialogsResult
        from telethon.tl.types.messages import DialogsNotModified, DialogsSlice

        if not isinstance(request, DiscoveryRequest):
            raise ChannelDiscoveryError(DiscoveryErrorCategory.ADAPTER_FAILURE)
        self._validate_limits(request.limits)
        if self._state is AuthState.AUTH_REQUIRED:
            raise ChannelDiscoveryError(DiscoveryErrorCategory.AUTH_REQUIRED)
        if self._state is AuthState.SESSION_INVALID:
            raise ChannelDiscoveryError(DiscoveryErrorCategory.SESSION_INVALID)
        if self._state is not AuthState.AUTHENTICATED or self._client is None:
            raise ChannelDiscoveryError(DiscoveryErrorCategory.ADAPTER_FAILURE)
        if self._receive_updates is not False or self._catch_up is not False:
            raise ChannelDiscoveryError(DiscoveryErrorCategory.ADAPTER_FAILURE)

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
                    raise ChannelDiscoveryError(
                        DiscoveryErrorCategory.ADAPTER_FAILURE
                    )
                if isinstance(response, DialogsResult):
                    response_is_terminal = True
                elif isinstance(response, DialogsSlice):
                    response_is_terminal = False
                else:
                    raise ChannelDiscoveryError(
                        DiscoveryErrorCategory.ADAPTER_FAILURE
                    )

                page_dialogs = getattr(response, "dialogs", None)
                page_messages = getattr(response, "messages", None)
                page_chats = getattr(response, "chats", None)
                page_users = getattr(response, "users", None)
                if not all(
                    isinstance(items, (list, tuple))
                    for items in (page_dialogs, page_messages, page_chats, page_users)
                ):
                    raise ChannelDiscoveryError(
                        DiscoveryErrorCategory.ADAPTER_FAILURE
                    )

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
                    raise ChannelDiscoveryError(
                        DiscoveryErrorCategory.ADAPTER_FAILURE
                    )

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
                            raise ChannelDiscoveryError(
                                DiscoveryErrorCategory.ADAPTER_FAILURE
                            )
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
                        raise ChannelDiscoveryError(
                            DiscoveryErrorCategory.ADAPTER_FAILURE
                        )
                    channel = ChannelSummary(
                        telegram_chat_id=marked_id,
                        title=entity.title,
                        username=getattr(entity, "username", None),
                        kind=kind,
                    )
                    previous = candidates.get(marked_id)
                    if previous is not None and previous.kind is not kind:
                        raise ChannelDiscoveryError(
                            DiscoveryErrorCategory.ADAPTER_FAILURE
                        )
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
                        raise ChannelDiscoveryError(
                            DiscoveryErrorCategory.ADAPTER_FAILURE
                        )
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
                    raise ChannelDiscoveryError(
                        DiscoveryErrorCategory.ADAPTER_FAILURE
                    )
                offset_id, offset_date, offset_peer, fingerprint = cursor
                if fingerprint in cursors:
                    raise ChannelDiscoveryError(
                        DiscoveryErrorCategory.ADAPTER_FAILURE
                    )
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

    async def _input_entity_for_selected_channel(self, telegram_chat_id: int) -> Any:
        try:
            return await self._client.get_input_entity(telegram_chat_id)
        except ValueError:
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

    async def _project_message(self, telegram_chat_id: int, message: Any) -> GatewayMessage:
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
            text=getattr(message, "message", None) or None,
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
    ):
        if self._state is not AuthState.AUTHENTICATED or self._client is None:
            raise AdapterError from None
        try:
            entity = await self._input_entity_for_selected_channel(telegram_chat_id)
            options = {
                "offset_id": before_message_id or 0,
                "reverse": False,
                "limit": limit,
            }
            if through_message_id is not None:
                options["max_id"] = through_message_id + 1
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
            async for chunk in self._client.iter_download(
                document, request_size=chunk_bytes, chunk_size=chunk_bytes
            ):
                if not isinstance(chunk, bytes) or not chunk or len(chunk) > chunk_bytes:
                    raise DownloadGatewayError("INVALID_CHUNK")
                yield chunk
        except DownloadGatewayError:
            raise
        except Exception as error:
            self._record_failure("MEDIA_DOWNLOAD", error, AdapterError())
            try:
                from telethon import errors
                if isinstance(error, errors.FloodWaitError):
                    raise DownloadGatewayError("RATE_LIMITED") from None
                if isinstance(error, (OSError, TimeoutError, ConnectionError, asyncio.IncompleteReadError)):
                    raise DownloadGatewayError("NETWORK") from None
            except DownloadGatewayError:
                raise
            except Exception:
                pass
            raise DownloadGatewayError("GATEWAY_FAILURE") from None

    def stream_media(
        self,
        channel_id: int,
        message_id: int,
        media_ordinal: int,
        *,
        telegram_media_id: str,
        expected_bytes: int,
        chunk_bytes: int = 256 * 1024,
    ):
        if (
            type(channel_id) is not int or type(message_id) is not int
            or type(media_ordinal) is not int or type(expected_bytes) is not int
            or type(chunk_bytes) is not int or chunk_bytes <= 0 or chunk_bytes > 256 * 1024
            or not telegram_media_id or expected_bytes < 0
        ):
            raise ValueError("invalid media stream request")
        return self._iterate_media(
            channel_id, message_id, media_ordinal,
            telegram_media_id=telegram_media_id,
            expected_bytes=expected_bytes,
            chunk_bytes=chunk_bytes,
        )

    def iter_channel_messages(
        self,
        telegram_chat_id: int,
        *,
        through_message_id: int | None,
        before_message_id: int | None,
        limit: int,
    ):
        if type(limit) is not int or limit <= 0:
            raise ValueError("invalid message limit")
        return self._iterate_messages(
            telegram_chat_id,
            through_message_id=through_message_id,
            before_message_id=before_message_id,
            limit=limit,
        )

    @staticmethod
    def _record_failure(
        stage: str, original: Exception, project_error: Exception
    ) -> None:
        safe_stage = stage if stage in _FAILURE_STAGES else "UNKNOWN"
        _DIAGNOSTIC_LOGGER.warning(
            "authentication diagnostic FAILURE_STAGE=%s "
            "SANITIZED_EXCEPTION_CLASS=%s PROJECT_ERROR_CATEGORY=%s",
            safe_stage,
            _sanitized_exception_class(original),
            _project_error_category(project_error),
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
        await self._disconnect()
