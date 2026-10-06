"""Deterministic local S0 command line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from rich.console import Console

from telegram_courses import __version__
from telegram_courses.config import ConfigurationError, load_configuration


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ConfigurationError from None


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = _ArgumentParser(prog="telegram-courses", add_help=True)
    parser.add_argument("command", choices=("smoke",))
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


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parse_arguments(argv)
        configuration = load_configuration(
            config_path=args.config,
            log_level=args.log_level,
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
    except Exception:
        sys.stderr.write("internal error\n")
        return 1
