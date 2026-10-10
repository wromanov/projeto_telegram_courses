"""Deterministic local S0 command line entry point."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import re
import sys
import unicodedata
from collections.abc import Callable, Sequence

from rich.console import Console

from telegram_courses import __version__
from telegram_courses.auth import AuthenticationError
from telegram_courses.auth_application import AuthenticationApplication
from telegram_courses.channel_discovery import (
    ChannelDiscoveryApplication,
    ChannelDiscoveryError,
    DiscoveryErrorCategory,
    DiscoveryOutcomeState,
    DiscoveryResult,
    select_channel,
)
from telegram_courses.config import (
    ConfigurationError,
    TelegramCredentials,
    load_configuration,
    load_telegram_credentials,
)
from telegram_courses.credentials import (
    CredentialVault,
    CredentialVaultError,
    validate_credentials,
)
from telegram_courses.message_scanner import ScanGatewayError
from telegram_courses.telethon_gateway import TelethonGateway


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ConfigurationError from None


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = _ArgumentParser(prog="telegram-courses", add_help=True)
    parser.add_argument(
        "command", choices=("smoke", "auth", "channels", "scan", "credentials")
    )
    parser.add_argument(
        "credentials_action", nargs="?", choices=("setup", "status")
    )
    parser.add_argument("--config", action="append")
    parser.add_argument("--log-level", action="append")
    parser.add_argument("--channel-id", type=int)
    parser.add_argument("--max-messages", type=int)
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--database", default="data/catalog.sqlite3")
    args = parser.parse_args(argv)
    if (args.config is not None and len(args.config) != 1) or (
        args.log_level is not None and len(args.log_level) != 1
    ):
        raise ConfigurationError
    args.config = args.config[0] if args.config else None
    args.log_level = args.log_level[0] if args.log_level else None
    if (args.command == "credentials") != (args.credentials_action is not None):
        raise ConfigurationError from None
    if args.command == "scan":
        if (
            args.channel_id is None
            or not args.channel_id
            or not args.max_messages
            or args.timeout_seconds is None
        ):
            raise ConfigurationError from None
        if args.max_messages <= 0 or args.timeout_seconds <= 0:
            raise ConfigurationError from None
    elif any(value is not None for value in (args.channel_id, args.max_messages)):
        raise ConfigurationError from None
    return args


def _scan_channel(
    *,
    channel_id: int,
    max_messages: int,
    timeout_seconds: float,
    database: str,
    gateway_factory: Callable[[TelegramCredentials], object],
    credentials_loader: Callable[[], TelegramCredentials] = load_telegram_credentials,
) -> int:
    from telegram_courses.message_scanner import ScanRequest
    from telegram_courses.scan_application import ScanApplication
    from telegram_courses.sqlite_repository import SQLiteMessageRepository

    application = ScanApplication(
        gateway_factory,
        credentials_loader,
        SQLiteMessageRepository(database),
    )
    outcome = asyncio.run(
        application.scan(
            channel_id,
            ScanRequest(max_messages=max_messages, timeout_seconds=timeout_seconds),
        )
    )
    Console(file=sys.stdout, force_terminal=False, no_color=True).print(
        f"scan run={outcome.run_id} status={outcome.status.value} "
        f"messages={outcome.messages_seen} media={outcome.media_seen}"
        + (f" stop={outcome.stop_reason}" if outcome.stop_reason else ""),
        markup=False,
        highlight=False,
    )
    return 0 if outcome.status.value == "COMPLETE" else 4


def _phone_prompt() -> str:
    return input("Phone: ")


def _secret_prompt(label: str) -> str:
    if not sys.stdin.isatty():
        raise ConfigurationError from None
    return getpass.getpass(label)


def _require_interactive() -> None:
    if not sys.stdin.isatty():
        raise ConfigurationError from None


def _credentials_setup(
    *,
    api_id_prompt: Callable[[], str],
    api_hash_prompt: Callable[[], str],
    vault_factory: Callable[[], CredentialVault],
) -> int:
    _require_interactive()
    api_id = api_id_prompt()
    api_hash = api_hash_prompt()
    credentials = validate_credentials(api_id, api_hash)
    vault_factory().setup(credentials)
    Console(file=sys.stdout, force_terminal=False, no_color=True).print(
        "credentials setup successful", markup=False, highlight=False
    )
    return 0


def _credentials_status(
    *, vault_factory: Callable[[], CredentialVault]
) -> int:
    available = vault_factory().status()
    state = "yes" if available else "no"
    Console(file=sys.stdout, force_terminal=False, no_color=True).print(
        f"credentials vault configured: {state}\ncredentials available: {state}",
        markup=False,
        highlight=False,
    )
    return 0


def _discovery_gateway(credentials: TelegramCredentials) -> TelethonGateway:
    return TelethonGateway(
        credentials,
        receive_updates=False,
        catch_up=False,
    )


def _scan_gateway(credentials: TelegramCredentials) -> TelethonGateway:
    return TelethonGateway(
        credentials,
        receive_updates=False,
        catch_up=False,
        request_retries=0,
        connection_retries=0,
    )


def _safe_terminal_text(value: str) -> str:
    return "".join(
        " " if character in "\r\n\t" else character
        for character in value
        if unicodedata.category(character) not in {"Cc", "Cf", "Cs"}
    )


def _render_discovery(result: DiscoveryResult) -> None:
    console = Console(
        file=sys.stdout,
        force_terminal=False,
        no_color=True,
        color_system=None,
        width=120,
    )
    if result.complete:
        console.print("discovery complete", markup=False, highlight=False)
    else:
        console.print(
            f"discovery partial: {result.stop_reason.value}",
            markup=False,
            highlight=False,
        )
    if not result.channels:
        console.print(
            "no eligible channels" if result.complete else "no candidates in partial discovery",
            markup=False,
            highlight=False,
        )
        return
    for index, channel in enumerate(result.channels, start=1):
        title = _safe_terminal_text(channel.title)
        username = (
            f" @{_safe_terminal_text(channel.username)}"
            if channel.username
            else ""
        )
        console.print(
            f"[{index}] {title}{username} | {channel.kind.value}",
            markup=False,
            highlight=False,
        )


def _select_from_local_snapshot(
    result: DiscoveryResult, selection: str
) -> int | None:
    if not isinstance(selection, str):
        raise ChannelDiscoveryError(DiscoveryErrorCategory.INVALID_SELECTION)
    selected_text = selection.strip()
    if not selected_text or selected_text.casefold() == "q":
        return None
    if re.fullmatch(r"[0-9]+", selected_text):
        try:
            index = int(selected_text)
        except ValueError:
            raise ChannelDiscoveryError(
                DiscoveryErrorCategory.INVALID_SELECTION
            ) from None
        if 1 <= index <= len(result.channels):
            return result.channels[index - 1].telegram_chat_id
        raise ChannelDiscoveryError(DiscoveryErrorCategory.INVALID_SELECTION)
    if re.fullmatch(r"-[0-9]+", selected_text) is None:
        raise ChannelDiscoveryError(DiscoveryErrorCategory.INVALID_SELECTION)
    try:
        selected_id = int(selected_text)
    except ValueError:
        raise ChannelDiscoveryError(
            DiscoveryErrorCategory.INVALID_SELECTION
        ) from None
    return select_channel(result, selected_id).telegram_chat_id


def _discover_channels(
    *,
    gateway_factory: Callable[[TelegramCredentials], object],
    selection_prompt: Callable[[str], str],
) -> int:
    if not sys.stdin.isatty() and selection_prompt is input:
        raise ConfigurationError from None
    application = ChannelDiscoveryApplication(
        gateway_factory,
        load_telegram_credentials,
    )
    try:
        outcome = asyncio.run(application.discover())
    except KeyboardInterrupt:
        Console(file=sys.stdout, force_terminal=False, no_color=True).print(
            "discovery cancelled", markup=False, highlight=False
        )
        return 130

    if outcome.state is DiscoveryOutcomeState.AUTH_REQUIRED:
        Console(file=sys.stdout, force_terminal=False, no_color=True).print(
            "run `telegram-courses auth` before channel discovery",
            markup=False,
            highlight=False,
        )
        return 3
    if outcome.state is DiscoveryOutcomeState.SESSION_INVALID:
        Console(file=sys.stdout, force_terminal=False, no_color=True).print(
            "session invalid; run `telegram-courses auth` before channel discovery",
            markup=False,
            highlight=False,
        )
        return 3

    assert outcome.result is not None
    result = outcome.result
    _render_discovery(result)
    if not result.channels:
        return 0 if result.complete else 4
    try:
        selection = selection_prompt("Select a number or Q to cancel: ")
    except KeyboardInterrupt:
        Console(file=sys.stdout, force_terminal=False, no_color=True).print(
            "selection cancelled", markup=False, highlight=False
        )
        return 0
    selected_id = _select_from_local_snapshot(result, selection)
    if selected_id is None:
        Console(file=sys.stdout, force_terminal=False, no_color=True).print(
            "selection cancelled", markup=False, highlight=False
        )
        return 0
    selected_summary = next(
        item for item in result.channels
        if item.telegram_chat_id == selected_id
    )
    Console(file=sys.stdout, force_terminal=False, no_color=True).print(
        f"selected telegram_chat_id={selected_id} "
        f"kind={selected_summary.kind.value}",
        markup=False,
        highlight=False,
    )
    return 0


def _authenticate(
    *,
    gateway_factory: Callable[..., object] = TelethonGateway,
    phone_prompt: Callable[[], str] = _phone_prompt,
    code_prompt: Callable[[], str] | None = None,
    password_prompt: Callable[[], str] | None = None,
) -> int:
    injected_prompts = code_prompt is not None and password_prompt is not None
    if code_prompt is None or password_prompt is None:
        code_prompt = code_prompt or (lambda: _secret_prompt("Code: "))
        password_prompt = password_prompt or (
            lambda: _secret_prompt("2FA password: ")
        )
    application = AuthenticationApplication(
        gateway_factory=gateway_factory,
        credentials=load_telegram_credentials,
        phone_prompt=phone_prompt,
        code_prompt=code_prompt,
        password_prompt=password_prompt,
        interactive_check=None if injected_prompts else _require_interactive,
    )
    outcome = asyncio.run(application.authenticate())
    if outcome.state.name != "AUTHENTICATED":
        raise AuthenticationError from None
    Console(file=sys.stdout, force_terminal=False, no_color=True).print(
        "authentication successful", markup=False, highlight=False
    )
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    gateway_factory: Callable[..., object] = TelethonGateway,
    discovery_gateway_factory: Callable[[TelegramCredentials], object] | None = None,
    scan_gateway_factory: Callable[[TelegramCredentials], object] | None = None,
    phone_prompt: Callable[[], str] = _phone_prompt,
    code_prompt: Callable[[], str] | None = None,
    password_prompt: Callable[[], str] | None = None,
    selection_prompt: Callable[[str], str] = input,
    api_id_prompt: Callable[[], str] = lambda: input("Telegram API ID: "),
    api_hash_prompt: Callable[[], str] = lambda: _secret_prompt("Telegram API HASH: "),
    credential_vault_factory: Callable[[], CredentialVault] = CredentialVault,
    credentials_loader: Callable[[], TelegramCredentials] = load_telegram_credentials,
) -> int:
    try:
        args = _parse_arguments(argv)
        configuration = load_configuration(
            config_path=args.config,
            log_level=args.log_level,
        )
        if args.command == "credentials":
            if args.credentials_action == "setup":
                return _credentials_setup(
                    api_id_prompt=api_id_prompt,
                    api_hash_prompt=api_hash_prompt,
                    vault_factory=credential_vault_factory,
                )
            return _credentials_status(vault_factory=credential_vault_factory)
        if args.command == "auth":
            return _authenticate(
                gateway_factory=gateway_factory,
                phone_prompt=phone_prompt,
                code_prompt=code_prompt,
                password_prompt=password_prompt,
            )
        if args.command == "channels":
            return _discover_channels(
                gateway_factory=(
                    discovery_gateway_factory or _discovery_gateway
                ),
                selection_prompt=selection_prompt,
            )
        if args.command == "scan":
            return _scan_channel(
                channel_id=args.channel_id,
                max_messages=args.max_messages,
                timeout_seconds=args.timeout_seconds,
                database=args.database,
                gateway_factory=scan_gateway_factory or _scan_gateway,
                credentials_loader=credentials_loader,
            )
        line = (
            f"telegram-courses {__version__} config={configuration.config} "
            f"log_level={configuration.log_level}"
        )
        Console(
            file=sys.stdout,
            force_terminal=False,
            no_color=True,
            color_system=None,
            width=120,
        ).print(line, markup=False, highlight=False, soft_wrap=True)
        return 0
    except ConfigurationError:
        sys.stderr.write("configuration error\n")
        return 2
    except CredentialVaultError:
        sys.stderr.write("credentials vault error\n")
        return 2
    except AuthenticationError as error:
        sys.stderr.write(f"{error}\n")
        return 3
    except ChannelDiscoveryError as error:
        sys.stderr.write(f"{error}\n")
        return 3
    except TimeoutError:
        sys.stderr.write("scan timeout\n")
        return 4
    except ScanGatewayError as error:
        sys.stderr.write(f"scan failed category={error.category}\n")
        return 4
    except Exception:
        sys.stderr.write("internal error\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
