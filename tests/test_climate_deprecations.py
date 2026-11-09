"""Tests for the native climate temperature attributes (#48).

Home Assistant 2026.11 deprecated temperature_unit, current_temperature and
target_temperature in favor of native_* names, and logs a warning when the
climate class is created if it only provides the old names. Older Home
Assistant (down to the HACS floor) reads only the old names, so both must
work.

Run from the repo root:
    .venv/bin/python tests/test_climate_deprecations.py
"""
import logging
from pathlib import Path
import sys
import typing as t

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The warnings are emitted when the class is created, so the handler must be
# attached before the climate module is imported.
_records: list[logging.LogRecord] = []


class _ListHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _records.append(record)


_logger = logging.getLogger("custom_components.toshiba_ac_community.climate")
_logger.addHandler(_ListHandler())
_logger.setLevel(logging.DEBUG)

from toshiba_ac_community.device import ToshibaAcDevice  # noqa: E402
from toshiba_ac_community.utils.amqp_api import ToshibaAcAmqpApi  # noqa: E402
from toshiba_ac_community.utils.http_api import ToshibaAcHttpApi  # noqa: E402

from custom_components.toshiba_ac_community.climate import ToshibaClimate  # noqa: E402
from homeassistant.const import UnitOfTemperature  # noqa: E402

# Real running state from the Master Bedroom unit (see
# test_climate_self_cleaning.py): target 24 C, indoor 25 C.
STATE_RUNNING = "30421841316400101918fe01001e1002001420"


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
    return ToshibaClimate(device)


def test_no_deprecation_warning_at_import() -> None:
    """Creating the class logs nothing about deprecated members."""
    deprecated = [r.getMessage() for r in _records if "deprecated" in r.getMessage()]
    assert not deprecated, deprecated


def test_native_attributes() -> None:
    """The native_* names return Celsius and the device's values."""
    climate = _make_climate(STATE_RUNNING)
    device = climate._device
    assert device.ac_temperature is not None
    assert device.ac_indoor_temperature is not None

    assert climate._attr_native_temperature_unit == UnitOfTemperature.CELSIUS
    # The native_temperature_unit property only exists on HA 2026.11+.
    if hasattr(climate, "native_temperature_unit"):
        assert climate.native_temperature_unit == UnitOfTemperature.CELSIUS
    assert climate.native_current_temperature == device.ac_indoor_temperature
    assert climate.native_target_temperature == device.ac_temperature


def test_legacy_names_still_work() -> None:
    """The old names stay for Home Assistant before 2026.11."""
    climate = _make_climate(STATE_RUNNING)
    device = climate._device
    assert "current_temperature" in vars(ToshibaClimate)
    assert "target_temperature" in vars(ToshibaClimate)
    assert climate._attr_temperature_unit == UnitOfTemperature.CELSIUS
    assert climate.temperature_unit == UnitOfTemperature.CELSIUS
    assert climate.current_temperature == device.ac_indoor_temperature
    assert climate.target_temperature == device.ac_temperature


if __name__ == "__main__":
    test_no_deprecation_warning_at_import()
    test_native_attributes()
    test_legacy_names_still_work()
    print("OK")
