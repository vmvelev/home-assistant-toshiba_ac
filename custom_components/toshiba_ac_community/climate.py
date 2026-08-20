"""Platform for climate integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from toshiba_ac.device import (
    ToshibaAcDevice,
    ToshibaAcFanMode,
    ToshibaAcHorizontalSwingMode,
    ToshibaAcMeritA,
    ToshibaAcMode,
    ToshibaAcPowerSelection,
    ToshibaAcSelfCleaning,
    ToshibaAcStatus,
    ToshibaAcSwingMode,
)
from toshiba_ac.utils import pretty_enum_name

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_OFF,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .const import DOMAIN
from .entity import ToshibaAcStateEntity
from .feature_list import get_feature_by_name, get_feature_list

_LOGGER = logging.getLogger(__name__)

TOSHIBA_TO_HVAC_MODE = {
    ToshibaAcMode.AUTO: HVACMode.AUTO,
    ToshibaAcMode.COOL: HVACMode.COOL,
    ToshibaAcMode.HEAT: HVACMode.HEAT,
    ToshibaAcMode.DRY: HVACMode.DRY,
    ToshibaAcMode.FAN: HVACMode.FAN_ONLY,
}

HVAC_MODE_TO_TOSHIBA = {v: k for k, v in TOSHIBA_TO_HVAC_MODE.items()}

# NONE means "no particular position", which is the horizontal swing's off state.
HORIZONTAL_SWING_TO_NAME = {
    e: "Off" if e == ToshibaAcHorizontalSwingMode.NONE else pretty_enum_name(e)
    for e in ToshibaAcHorizontalSwingMode
}
NAME_TO_HORIZONTAL_SWING = {v: k for k, v in HORIZONTAL_SWING_TO_NAME.items()}


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add climate entities for passed config_entry in HA."""
    device_manager = hass.data[DOMAIN][config_entry.entry_id]

    devices = await device_manager.get_devices()
    new_entities = [ToshibaClimate(device) for device in devices]

    if new_entities:
        _LOGGER.info("Adding %d climate entities", len(new_entities))
        async_add_devices(new_entities)


class ToshibaClimate(ToshibaAcStateEntity, ClimateEntity):
    """Provides a Toshiba climates."""

    # This is the main entity for the device
    _attr_has_entity_name = True
    _attr_name = None

    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_target_temperature_step = 1
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, toshiba_device: ToshibaAcDevice):
        """Initialize the climate."""
        super().__init__(toshiba_device)

        self._enable_turn_on_off_backwards_compatibility = False
        self._attr_unique_id = f"{self._device.ac_unique_id}_climate"
        self._attr_fan_modes = get_feature_list(self._device.supported.ac_fan_mode)
        self._attr_swing_modes = get_feature_list(self._device.supported.ac_swing_mode)

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the supported features, adding horizontal swing once the device reports it.

        2026 Shorai Curve units encode the two vanes independently. Support is
        only detectable from the unit having reported that encoding at least
        once, which may first happen after startup, so this is dynamic.
        """
        features = self._attr_supported_features
        if self._device.supports_independent_swing:
            features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE
        return features

    @property
    def is_on(self):
        """Return True if the device is running at the user's request.

        During self-cleaning the AC reports its status as ON (the fan dries
        the heat exchanger), but the user turned it off and the Toshiba app
        shows it as off - treat it as off here too. Turning it back on goes
        through set_ac_status(ON), which clears the cleaning flag.
        """
        return (
            self._device.ac_status == ToshibaAcStatus.ON
            and self._device.ac_self_cleaning != ToshibaAcSelfCleaning.ON
        )

    def _heating_8c_max_temp(self) -> int:
        """Return the ceiling for 8C frost-protection mode on this unit.

        Model id 3 units (e.g. Shorai Edge) accept 5-16, model id 2 units
        (e.g. Shorai+) cap at 13 (#35). If a model 3 unit turns out to cap
        at 13, the failure is benign: the unit reports its real state back
        and the UI corrects itself.
        """
        return 16 if self._device.ac_model_id == "3" else 13

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        set_temperature = kwargs[ATTR_TEMPERATURE]

        # Check if HEATING_8C mode is active (not just supported)
        if (
            hasattr(self._device, "ac_merit_a")
            and self._device.ac_merit_a == ToshibaAcMeritA.HEATING_8C
        ):
            # upper limit for target temp
            if set_temperature > self._heating_8c_max_temp():
                set_temperature = self._heating_8c_max_temp()
            # lower limit for target temp
            elif set_temperature < 5:
                set_temperature = 5
        else:
            # upper limit for target temp
            if set_temperature > 30:
                set_temperature = 30
            # lower limit for target temp
            elif set_temperature < 17:
                set_temperature = 17

        await self._device.set_ac_temperature(set_temperature)

    # PRESET MODE / POWER SETTING

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        if self._device.ac_self_cleaning == ToshibaAcSelfCleaning.ON:
            return "cleaning"

        if not self.is_on:
            return None

        return pretty_enum_name(self._device.ac_power_selection)

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
        """
        return get_feature_list(self._device.supported.ac_power_selection)

    async def async_turn_on(self) -> None:
        """Turn device on."""
        await self._device.set_ac_status(ToshibaAcStatus.ON)

    async def async_turn_off(self) -> None:
        """Turn device off."""
        await self._device.set_ac_status(ToshibaAcStatus.OFF)

    async def async_toggle(self) -> None:
        """Toggle device status."""
        state = self._device.ac_status
        if state == ToshibaAcStatus.OFF:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.info("Toshiba Climate setting preset_mode: %s", preset_mode)

        feature_list_id = get_feature_by_name(
            list(ToshibaAcPowerSelection), preset_mode
        )
        if feature_list_id is not None:
            await self._device.set_ac_power_selection(feature_list_id)

    @property
    def hvac_mode(self) -> HVACMode | str | None:
        """Return hvac operation ie. heat, cool mode."""
        if not self.is_on:
            return HVACMode.OFF

        return TOSHIBA_TO_HVAC_MODE[self._device.ac_mode]

    @property
    def hvac_modes(self) -> list[HVACMode] | list[str]:
        """Return the list of available hvac operation modes."""
        available_modes = [HVACMode.OFF]
        for toshiba_mode, hvac_mode in TOSHIBA_TO_HVAC_MODE.items():
            if toshiba_mode in self._device.supported.ac_mode:
                available_modes.append(hvac_mode)
        return available_modes

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        _LOGGER.info("Toshiba Climate setting hvac_mode: %s", hvac_mode)

        if hvac_mode == HVACMode.OFF:
            await self._device.set_ac_status(ToshibaAcStatus.OFF)
        else:
            if not self.is_on:
                await self._device.set_ac_status(ToshibaAcStatus.ON)
            await self._device.set_ac_mode(HVAC_MODE_TO_TOSHIBA[hvac_mode])

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        _LOGGER.info("Toshiba Climate setting fan_mode: %s", fan_mode)
        if fan_mode == FAN_OFF:
            await self._device.set_ac_fan_mode(ToshibaAcStatus.OFF)
        else:
            if not self.is_on:
                await self._device.set_ac_status(ToshibaAcStatus.ON)
            fan_mode = fan_mode.title().replace("_", " ")
            feature_list_id = get_feature_by_name(list(ToshibaAcFanMode), fan_mode)
            if feature_list_id is not None:
                await self._device.set_ac_fan_mode(feature_list_id)

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return pretty_enum_name(self._device.ac_fan_mode)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        swing_mode = swing_mode.title().replace("_", " ")
        feature_list_id = get_feature_by_name(list(ToshibaAcSwingMode), swing_mode)
        if feature_list_id is not None:
            await self._device.set_ac_swing_mode(feature_list_id)

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        return pretty_enum_name(self._device.ac_swing_mode)

    @property
    def swing_horizontal_modes(self) -> list[str] | None:
        """Return the list of horizontal swing positions."""
        if not self._device.supports_independent_swing:
            return None
        return list(NAME_TO_HORIZONTAL_SWING)

    @property
    def swing_horizontal_mode(self) -> str | None:
        """Return the horizontal swing setting."""
        if not self._device.supports_independent_swing:
            return None
        return HORIZONTAL_SWING_TO_NAME[self._device.ac_horizontal_swing_mode]

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new horizontal swing position."""
        mode = NAME_TO_HORIZONTAL_SWING.get(swing_horizontal_mode)
        if mode is not None:
            await self._device.set_ac_horizontal_swing_mode(mode)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.ac_indoor_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._device.ac_temperature

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if (
            hasattr(self._device, "ac_merit_a")
            and self._device.ac_merit_a == ToshibaAcMeritA.HEATING_8C
        ):
            return 5
        return 17

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if (
            hasattr(self._device, "ac_merit_a")
            and self._device.ac_merit_a == ToshibaAcMeritA.HEATING_8C
        ):
            return self._heating_8c_max_temp()
        return 30

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes.

        Implemented by platform classes. Convention for attribute names
        is lowercase snake_case.
        """
        return {
            "merit_a_feature": self._device.ac_merit_a.name,
            "merit_b_feature": self._device.ac_merit_b.name,
            "air_pure_ion": self._device.ac_air_pure_ion.name,
            "self_cleaning": self._device.ac_self_cleaning.name,
            "outdoor_temperature": self._device.ac_outdoor_temperature,
        }
