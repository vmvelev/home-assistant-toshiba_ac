"""Tests for the 8C frost-protection temperature range (#35).

Uses real ToshibaAcDevice objects built from the exact device data in the
issue report: the Shorai Edge (model id 3) supports 5-16 in 8C mode, the
Shorai+ (model id 2) caps at 13. Requires toshiba-ac-community >= 0.7.1
(ac_model_id stored on the device).

Run from the repo root:
    .venv/bin/python tests/test_climate_8c.py
"""
import asyncio
from pathlib import Path
import sys
import typing as t
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from toshiba_ac.device import ToshibaAcDevice, ToshibaAcMeritA
from toshiba_ac.utils.amqp_api import ToshibaAcAmqpApi
from toshiba_ac.utils.http_api import ToshibaAcHttpApi

from custom_components.toshiba_ac_community.climate import ToshibaClimate

# Real devices from the #35 report (names, merit strings, states from the log).
SHORAI_EDGE = ("Salon", "6c02", "3", "30421b41316400101b23fe02000010ff000000")
SHORAI_PLUS = ("Bureau", "2c00", "2", "30421b41316400101a23fe0200001002000000")


async def _make_climate(
    unit: tuple[str, str, str, str], heating_8c: bool
) -> ToshibaClimate:
    name, merit, model_id, state = unit
    device = ToshibaAcDevice(
        name=name,
        device_id="device",
        ac_id="ac",
        ac_unique_id="unique",
        initial_ac_state=state,
        firmware_version="5.0.00",
        merit_feature=merit,
        ac_model_id=model_id,
        amqp_api=t.cast(ToshibaAcAmqpApi, None),
        http_api=t.cast(ToshibaAcHttpApi, None),
    )
    if heating_8c:
        device.fcu_state.ac_merit_a = ToshibaAcMeritA.HEATING_8C
    device.set_ac_temperature = AsyncMock()  # type: ignore[method-assign]
    return ToshibaClimate(device)


async def _range_checks() -> None:
    edge = await _make_climate(SHORAI_EDGE, heating_8c=True)
    assert edge.min_temp == 5
    assert edge.max_temp == 16

    plus = await _make_climate(SHORAI_PLUS, heating_8c=True)
    assert plus.min_temp == 5
    assert plus.max_temp == 13

    normal = await _make_climate(SHORAI_EDGE, heating_8c=False)
    assert normal.min_temp == 17
    assert normal.max_temp == 30


async def _clamp_checks() -> None:
    # The reporter's use case: 16 must reach the Shorai Edge unchanged.
    edge = await _make_climate(SHORAI_EDGE, heating_8c=True)
    await edge.async_set_temperature(temperature=16)
    edge._device.set_ac_temperature.assert_awaited_with(16)
    await edge.async_set_temperature(temperature=20)
    edge._device.set_ac_temperature.assert_awaited_with(16)
    await edge.async_set_temperature(temperature=3)
    edge._device.set_ac_temperature.assert_awaited_with(5)

    # Shorai+ keeps the 13 ceiling.
    plus = await _make_climate(SHORAI_PLUS, heating_8c=True)
    await plus.async_set_temperature(temperature=16)
    plus._device.set_ac_temperature.assert_awaited_with(13)

    # Outside 8C mode the normal 17-30 clamp is untouched.
    normal = await _make_climate(SHORAI_EDGE, heating_8c=False)
    await normal.async_set_temperature(temperature=16)
    normal._device.set_ac_temperature.assert_awaited_with(17)


def test_8c_temperature_ranges() -> None:
    """8C mode range is 5-16 on model 3 and 5-13 on model 2."""
    asyncio.run(_range_checks())


def test_8c_temperature_clamp() -> None:
    """Set-temperature clamps to the per-model 8C ceiling."""
    asyncio.run(_clamp_checks())


if __name__ == "__main__":
    test_8c_temperature_ranges()
    test_8c_temperature_clamp()
    print("OK")
