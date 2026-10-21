"""Environment-level token storage using the OS credential vault."""

import base64
import json
import time

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

SERVICE = "web-technology-inspector/aem"


def _key(environment):
    return (
        str(environment["id"])
        + "|"
        + environment["author_base"].rstrip("/")
    )


def _require_backend():
    backend = keyring.get_keyring()

    if getattr(backend, "priority", 0) <= 0:
        raise RuntimeError(
            "No usable OS credential store is available"
        )


def save_token(environment, token):
    _require_backend()

    if not token or not token.strip():
        raise ValueError("A nonempty token is required")

    keyring.set_password(
        SERVICE,
        _key(environment),
        token.strip()
    )


def get_token(environment):
    _require_backend()

    return keyring.get_password(
        SERVICE,
        _key(environment)
    )


def delete_token(environment):
    _require_backend()

    try:
        keyring.delete_password(
            SERVICE,
            _key(environment)
        )
    except PasswordDeleteError:
        pass


def token_status(environment):
    try:
        token = get_token(environment)

    except (KeyringError, RuntimeError, OSError) as exc:
        return {
            "status": "unavailable",
            "message": (
                "Secure credential storage unavailable: "
                + type(exc).__name__
            ),
            "token": None
        }

    if not token:
        return {
            "status": "missing",
            "message": "No token configured",
            "token": None
        }

    # JWT expiry is an unverified local hint.
    # Server acceptance remains authoritative.

    parts = token.split(".")

    if len(parts) == 3:
        try:
            payload = parts[1]
            payload += "=" * (-len(payload) % 4)

            decoded = json.loads(
                base64.urlsafe_b64decode(payload)
            )

            expiry = decoded.get("exp")

            if (
                isinstance(expiry, (int, float))
                and not isinstance(expiry, bool)
            ):
                remaining = expiry - time.time()

                if remaining <= 0:
                    return {
                        "status": "expired",
                        "message": "Token has expired",
                        "token": None
                    }

                if remaining < 900:
                    return {
                        "status": "expiring",
                        "message": (
                            "Token expires within 15 minutes"
                        ),
                        "token": token
                    }

                return {
                    "status": "available",
                    "message": (
                        "Token stored; JWT expiry "
                        "has not been reached"
                    ),
                    "token": token
                }

        except (
            ValueError,
            TypeError,
            UnicodeError,
            OverflowError
        ):
            pass

    return {
        "status": "unknown",
        "message": (
            "Token stored; expiry unknown "
            "until server validation"
        ),
        "token": token
    }
