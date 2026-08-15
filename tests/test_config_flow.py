"""Tests for the Toshiba AC config flow.

Runs against the real ToshibaAcDeviceManager from the pinned
toshiba-ac-community release; only the network edges (HTTP login, device
registration, AMQP) are stubbed. Reproduces vmvelev/Toshiba-AC-control#13:
validate_input read device_manager.http_api after shutdown() had set it to
None, so every successful login crashed with AssertionError.

Run from the repo root:
    .venv/bin/python tests/test_config_flow.py
"""
import asyncio
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import toshiba_ac.device_manager  # noqa: F401  # must precede http_api (circular import)
from toshiba_ac.utils.http_api import ToshibaAcHttpApi, ToshibaAcHttpApiAuthError

from custom_components.toshiba_ac_community.config_flow import (
    InvalidAuth,
    validate_input,
)

USER_INPUT = {"username": "user@example.com", "password": "hunter2"}


def _network_stubs(connect=None):
    """Stub the HTTP login, device registration and AMQP connection."""

    async def fake_connect(self):
        # Mirrors the side effects of the real ToshibaAcHttpApi.connect().
        self.access_token = "token-123"
        self.access_token_type = "Bearer"
        self.consumer_id = "consumer-1"

    amqp = MagicMock()
    amqp.connect = AsyncMock()
    amqp.shutdown = AsyncMock()

    return (
        patch.object(ToshibaAcHttpApi, "connect", connect or fake_connect),
        patch.object(
            ToshibaAcHttpApi, "register_client", AsyncMock(return_value="sas-token")
        ),
        patch(
            "toshiba_ac.device_manager.ToshibaAcAmqpApi", MagicMock(return_value=amqp)
        ),
        amqp,
    )


async def _successful_login():
    http_connect, register, amqp_cls, amqp = _network_stubs()
    with http_connect, register, amqp_cls:
        data = await validate_input(None, USER_INPUT)

    assert data["username"] == USER_INPUT["username"]
    assert data["password"] == USER_INPUT["password"]
    assert data["sas_token"] == "sas-token"
    # The cached-token fields added in 2026.8.1; reading them after
    # device_manager.shutdown() is what broke the whole flow.
    assert data["access_token"] == "token-123"
    assert data["access_token_type"] == "Bearer"
    assert data["consumer_id"] == "consumer-1"
    # The manager must still be torn down after validation.
    assert amqp.shutdown.await_count == 1


async def _invalid_auth():
    async def failing_connect(self):
        raise ToshibaAcHttpApiAuthError("Invalid password")

    http_connect, register, amqp_cls, _ = _network_stubs(connect=failing_connect)
    with http_connect, register, amqp_cls:
        try:
            await validate_input(None, USER_INPUT)
        except InvalidAuth:
            return
    raise AssertionError("InvalidAuth was not raised")


def test_successful_login_returns_cached_tokens():
    """A correct login must return entry data including the cached tokens."""
    asyncio.run(_successful_login())


def test_auth_error_maps_to_invalid_auth():
    """A login failure must surface as InvalidAuth, not a crash."""
    asyncio.run(_invalid_auth())


if __name__ == "__main__":
    test_successful_login_returns_cached_tokens()
    test_auth_error_maps_to_invalid_auth()
    print("OK")
