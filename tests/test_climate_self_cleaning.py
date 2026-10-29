"""Tests for climate behavior during self-cleaning.

During self-cleaning the AC reports its status as ON (the fan dries the
heat exchanger), but the user turned it off and the Toshiba app shows it
as off. The climate entity must report OFF, keep the "cleaning" preset,
and power on properly (clearing the flag) when a mode is selected.

Uses the real state strings captured from a Master Bedroom unit during a
clean cycle on 2026-08-20.

Run from the repo root:
    .venv/bin/python tests/test_climate_self_cleaning.py
"""
import asyncio
from pathlib import Path
import sys
import typing as t
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from toshiba_ac.device import ToshibaAcDevice, ToshibaAcStatus
from toshiba_ac.utils.amqp_api import ToshibaAcAmqpApi
from toshiba_ac.utils.http_api import ToshibaAcHttpApi

from custom_components.toshiba_ac_community.climate import ToshibaClimate
from homeassistant.components.climate import HVACMode

# Real states from the same unit: cleaning (status ON + self-clean ON),
# genuinely running (self-clean OFF), and fully off.
STATE_CLEANING = "30421841316400101b7ffe01001e1802001420"
STATE_RUNNING = "30421841316400101918fe01001e1002001420"
STATE_OFF = "31421841316400101c7ffe0200001002000000"


def _make_climate(state: str) -> ToshibaClimate:
    device = ToshibaAcDevice(
        name="Master Bedroom",
        device_id="device",
        ac_id="ac",
        ac_unique_id="unique",
        initial_ac_state=state,
        firmware_version="5.0.00",
        merit_feature="6c03",
        ac_model_id="3",
        amqp_api=t.cast(ToshibaAcAmqpApi, None),
        http_api=t.cast(ToshibaAcHttpApi, None),
    )
    device.set_ac_status = AsyncMock()  # type: ignore[method-assign]
    device.set_ac_mode = AsyncMock()  # type: ignore[method-assign]
    return ToshibaClimate(device)


def test_cleaning_reports_off() -> None:
    """While self-cleaning the entity is off with the cleaning preset."""
    cleaning = _make_climate(STATE_CLEANING)
    assert cleaning.is_on is False
    assert cleaning.hvac_mode == HVACMode.OFF
    assert cleaning.preset_mode == "cleaning"

    running = _make_climate(STATE_RUNNING)
    assert running.is_on is True
    assert running.hvac_mode == HVACMode.COOL

    off = _make_climate(STATE_OFF)
    assert off.is_on is False
    assert off.hvac_mode == HVACMode.OFF


def test_mode_change_during_cleaning_powers_on() -> None:
    """Selecting a mode during cleaning sends a power-on first."""

    async def run() -> None:
        cleaning = _make_climate(STATE_CLEANING)
        await cleaning.async_set_hvac_mode(HVACMode.COOL)
        cleaning._device.set_ac_status.assert_awaited_with(ToshibaAcStatus.ON)

    asyncio.run(run())


if __name__ == "__main__":
    test_cleaning_reports_off()
    test_mode_change_during_cleaning_powers_on()
    print("OK")
