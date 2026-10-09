import pytest

from telegram_courses.auth import AuthOutcome, AuthState, RateLimited
from telegram_courses.config import ConfigurationError, load_telegram_credentials


def test_auth_states_and_outcome_are_project_owned_and_immutable() -> None:
    assert {state.name for state in AuthState} == {
        "AUTHENTICATED", "AUTH_REQUIRED", "CODE_REQUIRED",
        "PASSWORD_REQUIRED", "SESSION_INVALID",
    }
    outcome = AuthOutcome(AuthState.AUTHENTICATED)
    assert outcome.state is AuthState.AUTHENTICATED


def test_rate_limit_exposes_duration_and_safe_text() -> None:
    error = RateLimited(17)
    assert error.retry_after_seconds == 17
    assert str(error) == "authentication rate limited"


def test_credentials_are_environment_only_and_validated() -> None:
    class EmptyVault:
        def load(self):
            return None

    vault = EmptyVault()
    credentials = load_telegram_credentials(
        {"TELEGRAM_API_ID": "123", "TELEGRAM_API_HASH": "synthetic-hash"},
        vault=vault,
    )
    assert credentials.api_id == 123
    assert credentials.api_hash == "synthetic-hash"
    for environment in (
        {},
        {"TELEGRAM_API_ID": "0", "TELEGRAM_API_HASH": "synthetic"},
        {"TELEGRAM_API_ID": "bad", "TELEGRAM_API_HASH": "synthetic"},
        {"TELEGRAM_API_ID": "1", "TELEGRAM_API_HASH": "   "},
    ):
        with pytest.raises(ConfigurationError):
            load_telegram_credentials(environment, vault=vault)
