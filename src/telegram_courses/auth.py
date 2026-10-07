"""Project-owned, secret-free authentication states and errors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class AuthState(Enum):
    AUTHENTICATED = auto()
    AUTH_REQUIRED = auto()
    CODE_REQUIRED = auto()
    PASSWORD_REQUIRED = auto()
    SESSION_INVALID = auto()


@dataclass(frozen=True)
class AuthOutcome:
    state: AuthState


class AuthenticationError(Exception):
    """Base class for safe authentication failures."""

    safe_message = "authentication failed"

    def __str__(self) -> str:
        return self.safe_message


class AuthRejected(AuthenticationError):
    safe_message = "authentication rejected"


class InvalidCode(AuthenticationError):
    safe_message = "invalid authentication code"


class ExpiredCode(AuthenticationError):
    safe_message = "authentication code expired"


class InvalidPassword(AuthenticationError):
    safe_message = "invalid authentication password"


class InvalidSession(AuthenticationError):
    safe_message = "stored session is invalid"


class NetworkError(AuthenticationError):
    safe_message = "network unavailable"


class RateLimited(AuthenticationError):
    safe_message = "authentication rate limited"

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(self.safe_message)


class AdapterError(AuthenticationError):
    safe_message = "authentication service failure"
