"""Deterministic local S0 command line entry point."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from collections.abc import Callable, Sequence

from rich.console import Console

from telegram_courses import __version__
from telegram_courses.auth import AuthenticationError
from telegram_courses.auth_application import AuthenticationApplication
from telegram_courses.config import (
    ConfigurationError,
    load_configuration,
    load_telegram_credentials,
)
from telegram_courses.telethon_gateway import TelethonGateway


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ConfigurationError from None


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = _ArgumentParser(prog="telegram-courses", add_help=True)
    parser.add_argument("command", choices=("smoke", "auth"))
    parser.add_argument("--config", action="append")
    parser.add_argument("--log-level", action="append")
    args = parser.parse_args(argv)
    if (args.config is not None and len(args.config) != 1) or (
        args.log_level is not None and len(args.log_level) != 1
    ):
        raise ConfigurationError
    args.config = args.config[0] if args.config else None
    args.log_level = args.log_level[0] if args.log_level else None
    return args


def _phone_prompt() -> str:
    return input("Phone: ")


def _secret_prompt(label: str) -> str:
    if not sys.stdin.isatty():
        raise ConfigurationError from None
    return getpass.getpass(label)


def _require_interactive() -> None:
    if not sys.stdin.isatty():
        raise ConfigurationError from None


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
    phone_prompt: Callable[[], str] = _phone_prompt,
    code_prompt: Callable[[], str] | None = None,
    password_prompt: Callable[[], str] | None = None,
) -> int:
    try:
        args = _parse_arguments(argv)
        configuration = load_configuration(
            config_path=args.config,
            log_level=args.log_level,
        )
        if args.command == "auth":
            return _authenticate(
                gateway_factory=gateway_factory,
                phone_prompt=phone_prompt,
                code_prompt=code_prompt,
                password_prompt=password_prompt,
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
    except AuthenticationError as error:
        sys.stderr.write(f"{error}\n")
        return 3
    except Exception:
        sys.stderr.write("internal error\n")
        return 1
