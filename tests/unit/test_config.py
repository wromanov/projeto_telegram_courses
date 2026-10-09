from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telegram_courses.config import (
    ConfigurationError,
    TelegramCredentials,
    load_configuration,
    load_telegram_credentials,
)


class ConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_cwd = Path.cwd()
        self.temp = tempfile.TemporaryDirectory(dir=self.previous_cwd)
        self.root = Path(self.temp.name)
        os.chdir(self.root)
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        os.chdir(self.previous_cwd)
        self.temp.cleanup()

    def write_config(self, contents: str, name: str = "settings.toml") -> str:
        path = self.root / name
        path.write_text(contents, encoding="utf-8")
        return str(path)

    def test_missing_default_uses_defaults(self) -> None:
        result = load_configuration()
        self.assertEqual((result.config, result.log_level), ("defaults", "INFO"))

    def test_empty_file_is_loaded_and_uses_default_level(self) -> None:
        path = self.write_config("")
        result = load_configuration(config_path=path)
        self.assertEqual((result.config, result.log_level), ("file", "INFO"))

    def test_missing_logging_section_is_valid(self) -> None:
        path = self.write_config("# s0 fixture\n")
        result = load_configuration(config_path=path)
        self.assertEqual((result.config, result.log_level), ("file", "INFO"))

    def test_missing_level_is_valid(self) -> None:
        path = self.write_config("[logging]\n")
        result = load_configuration(config_path=path)
        self.assertEqual((result.config, result.log_level), ("file", "INFO"))

    def test_file_level_and_precedence(self) -> None:
        path = self.write_config('[logging]\nlevel = "WARNING"\n')
        self.assertEqual(load_configuration(config_path=path).log_level, "WARNING")
        with patch.dict(os.environ, {"TELEGRAM_COURSES_LOG_LEVEL": "ERROR"}):
            self.assertEqual(load_configuration(config_path=path).log_level, "ERROR")
            result = load_configuration(config_path=path, log_level="DEBUG")
        self.assertEqual((result.config, result.log_level), ("file", "DEBUG"))

    def test_environment_file_selection_and_missing_explicit_path(self) -> None:
        path = self.write_config("", "environment.toml")
        with patch.dict(os.environ, {"TELEGRAM_COURSES_CONFIG": path}):
            self.assertEqual(load_configuration().config, "file")
        missing = str(self.root / "missing.toml")
        with patch.dict(os.environ, {"TELEGRAM_COURSES_CONFIG": missing}):
            with self.assertRaises(ConfigurationError):
                load_configuration()

    def test_invalid_toml_and_values_are_errors_even_with_override(self) -> None:
        invalid = self.write_config("[logging\n")
        with self.assertRaises(ConfigurationError):
            load_configuration(config_path=invalid, log_level="DEBUG")
        for contents in (
            '[logging]\nlevel = "info"\n',
            "[logging]\nlevel = 1\n",
            '[extra]\nvalue = "x"\n',
            "[logging]\nunknown = true\n",
            "[telegram]\napi_hash = 'secret'\n",
        ):
            path = self.write_config(contents)
            with self.subTest(contents=contents), self.assertRaises(ConfigurationError):
                load_configuration(config_path=path, log_level="DEBUG")

    def test_invalid_overrides_are_errors(self) -> None:
        for variable, value in (
            ("TELEGRAM_COURSES_LOG_LEVEL", ""),
            ("TELEGRAM_COURSES_LOG_LEVEL", "info"),
            ("TELEGRAM_COURSES_CONFIG", ""),
        ):
            with patch.dict(os.environ, {variable: value}):
                with self.subTest(variable=variable, value=value), self.assertRaises(
                    ConfigurationError
                ):
                    load_configuration()

    def test_credential_environment_pair_precedes_vault_without_mixing_sources(self) -> None:
        class Vault:
            def load(self) -> TelegramCredentials:
                return TelegramCredentials(9, "b" * 32)

        environment_pair = {
            "TELEGRAM_API_ID": "7",
            "TELEGRAM_API_HASH": "a" * 32,
        }
        self.assertEqual(
            load_telegram_credentials(environment_pair, vault=Vault()),
            TelegramCredentials(7, "a" * 32),
        )
        self.assertEqual(
            load_telegram_credentials({}, vault=Vault()),
            TelegramCredentials(9, "b" * 32),
        )

    def test_incomplete_or_invalid_credential_environment_fails_without_vault(self) -> None:
        class Vault:
            def load(self) -> TelegramCredentials:
                raise AssertionError("partial environment must not fall back")

        for environment in (
            {"TELEGRAM_API_ID": "7"},
            {"TELEGRAM_API_HASH": "a" * 32},
            {"TELEGRAM_API_ID": "7", "TELEGRAM_API_HASH": ""},
        ):
            with self.subTest(environment=environment), self.assertRaises(
                ConfigurationError
            ):
                load_telegram_credentials(environment, vault=Vault())


if __name__ == "__main__":
    unittest.main()
