from __future__ import annotations

import os
import sys
from pathlib import Path


def _user_data_directory() -> Path:
    value = os.environ.get("LOCALAPPDATA")
    if not value:
        raise RuntimeError("O Windows não informou a pasta LOCALAPPDATA do usuário.")
    path = Path(value)
    if not path.is_absolute() or not path.drive or value.startswith(("\\\\", "//")):
        raise RuntimeError("A pasta LOCALAPPDATA do usuário não é local e válida.")
    return path / "telegram_courses_data"


def _ensure_private_data_directory() -> Path:
    if os.name != "nt":
        raise RuntimeError("Este pacote candidato foi preparado para Windows.")
    try:
        from telegram_courses.telethon_session import _ProtectedCredentialsVault

        vault_storage = _ProtectedCredentialsVault()
        vault_storage._prepare_directory()
        directory = _user_data_directory()
        directory.mkdir(exist_ok=True)
        attributes = vault_storage._api.attributes(directory)
        owner, _protected, _entries = vault_storage._api.inspect_acl(directory)
        if (
            attributes is None
            or attributes & 0x400
            or not attributes & 0x10
            or owner != vault_storage._current_user_sid
        ):
            raise RuntimeError
        return directory
    except Exception:
        raise RuntimeError(
            "Não foi possível validar a pasta privada do aplicativo. "
            "Confira LOCALAPPDATA e as permissões da conta do Windows."
        ) from None


def _toml_string(value: Path) -> str:
    return '"' + value.as_posix().replace('"', '\\"') + '"'


def _create_default_settings(directory: Path) -> None:
    if os.environ.get("TELEGRAM_COURSES_CONFIG") is not None:
        return
    settings_path = directory / "settings.toml"
    os.environ["TELEGRAM_COURSES_CONFIG"] = str(settings_path)
    if settings_path.exists():
        return
    downloads = Path.home() / "Downloads" / "TelegramCourses"
    database = directory / "catalog.sqlite3"
    settings = (
        "[logging]\n"
        'level = "INFO"\n\n'
        "[download]\n"
        "workers = 2\n"
        "attempts_per_media = 3\n"
        f"directory = {_toml_string(downloads)}\n\n"
        "[storage]\n"
        f"database_path = {_toml_string(database)}\n"
    )
    try:
        with settings_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(settings)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        return
    except OSError as error:
        raise RuntimeError(
            "Não foi possível criar as configurações iniciais em LOCALAPPDATA "
            f"(erro do sistema {error.errno})."
        ) from None


def main(arguments: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if arguments is None else arguments)
    try:
        data_directory = _ensure_private_data_directory()
        _create_default_settings(data_directory)
    except RuntimeError as error:
        print(f"Configuração inicial: {error}", file=sys.stderr)
        return 2

    if not args:
        args = ["--help"]
    try:
        from telegram_courses.cli import main as application_main

        return application_main(args)
    except Exception:
        print(
            "O aplicativo não conseguiu iniciar. Confira a configuração e tente novamente.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
