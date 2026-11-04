"""Prepare a private product workspace without contacting Telegram."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from telegram_courses.s9_operational_ledger import (
    LedgerError,
    _create_private_directory,
    _open_private_directory_guard,
)

PRODUCT_DIRECTORY = "telegram_courses_product"


class PreparationError(RuntimeError):
    """The private workspace could not be safely prepared."""


def prepare_product_workspace(local_app_data: Path) -> Path:
    """Create only missing private directories; never repair existing ACLs."""
    if not local_app_data.is_absolute() or not local_app_data.is_dir():
        raise PreparationError("LOCALAPPDATA_INVALID")
    root = local_app_data / PRODUCT_DIRECTORY
    guards = []
    try:
        for path in (root, root / "db", root / "downloads"):
            guard = (
                _open_private_directory_guard(path)
                if os.path.lexists(path)
                else _create_private_directory(path)
            )
            guards.append(guard)
            guard.verify(path)
        return root
    except (LedgerError, OSError, RuntimeError, ValueError):
        raise PreparationError("PRODUCT_DIRECTORY_PRIVATE_CHECK_FAILED") from None
    finally:
        for guard in reversed(guards):
            guard.close()


def main() -> int:
    if os.name != "nt" or not os.environ.get("LOCALAPPDATA"):
        print("Preparação disponível somente no Windows com LOCALAPPDATA válido.", file=sys.stderr)
        return 2
    try:
        prepare_product_workspace(Path(os.environ["LOCALAPPDATA"]))
    except PreparationError as error:
        print(f"Preparação bloqueada: {error}", file=sys.stderr)
        return 2
    print("Preparação privada concluída; nenhum acesso ao Telegram foi feito.")
    print(r"Banco: %LOCALAPPDATA%\telegram_courses_product\db\catalog.sqlite3")
    print(r"Downloads: %LOCALAPPDATA%\telegram_courses_product\downloads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
