"""Tests for vertical swing commands on independent-axis (2026 Shorai Curve) units.

Reproduces the report on PR #34 by @simontaen and @harmpert: setting the
vertical swing from Home Assistant reset the horizontal vane to Off, because
the climate entity always sent the legacy combined preset (vertical N +
horizontal none) even on units that encode the two axes independently.

Run from the repo root:
    .venv/bin/python tests/test_climate_swing.py
"""
import asyncio
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from toshiba_ac.device import (
    ToshibaAcFanMode,
    ToshibaAcHorizontalSwingMode,
    ToshibaAcSwingMode,
    ToshibaAcVerticalSwingMode,
)

from custom_components.toshiba_ac_community.climate import ToshibaClimate


def _climate(independent: bool) -> ToshibaClimate:
    device = MagicMock()
    device.ac_unique_id = "unit-1"
    device.supported.ac_fan_mode = list(ToshibaAcFanMode)
    device.supported.ac_swing_mode = list(ToshibaAcSwingMode)
    device.supports_independent_swing = independent
    device.ac_horizontal_swing_mode = ToshibaAcHorizontalSwingMode.SWING
    device.set_ac_swing_mode = AsyncMock()
    device.set_ac_vertical_swing_mode = AsyncMock()
    return ToshibaClimate(device)


async def _independent_unit_keeps_horizontal():
    for name, vertical in {
        "Off": ToshibaAcVerticalSwingMode.NONE,
        "Fixed 2": ToshibaAcVerticalSwingMode.FIXED_2,
        "Swing Vertical": ToshibaAcVerticalSwingMode.SWING,
    }.items():
        climate = _climate(independent=True)
        await climate.async_set_swing_mode(name)
        # The per-axis call re-sends the current horizontal position; the legacy
        # preset would reset it to none.
        climate._device.set_ac_vertical_swing_mode.assert_awaited_once_with(vertical)
        climate._device.set_ac_swing_mode.assert_not_awaited()


async def _independent_unit_combined_presets_stay_legacy():
    climate = _climate(independent=True)
    await climate.async_set_swing_mode("Swing Vertical And Horizontal")
    climate._device.set_ac_swing_mode.assert_awaited_once_with(
        ToshibaAcSwingMode.SWING_VERTICAL_AND_HORIZONTAL
    )
    climate._device.set_ac_vertical_swing_mode.assert_not_awaited()


async def _legacy_unit_unchanged():
    climate = _climate(independent=False)
    await climate.async_set_swing_mode("Fixed 2")
    climate._device.set_ac_swing_mode.assert_awaited_once_with(
        ToshibaAcSwingMode.FIXED_2
    )
    climate._device.set_ac_vertical_swing_mode.assert_not_awaited()


if __name__ == "__main__":
    asyncio.run(_independent_unit_keeps_horizontal())
    asyncio.run(_independent_unit_combined_presets_stay_legacy())
    asyncio.run(_legacy_unit_unchanged())
    print("ok")
