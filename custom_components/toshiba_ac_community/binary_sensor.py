"""Binary sensor platform for the Toshiba AC integration."""
from __future__ import annotations

import logging

from toshiba_ac.device import ToshibaAcDevice, ToshibaAcSelfCleaning

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .const import DOMAIN
from .entity import ToshibaAcStateEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add binary sensor entities for passed config_entry in HA."""
    device_manager = hass.data[DOMAIN][config_entry.entry_id]
    new_entities = []

    devices: list[ToshibaAcDevice] = await device_manager.get_devices()
    for device in devices:
        # Support is only detectable from the reported state: no report means
        # the unit has no self cleaning function
        if device.ac_self_cleaning is not ToshibaAcSelfCleaning.NONE:
            new_entities.append(ToshibaAcSelfCleaningEntity(device))
        else:
            _LOGGER.debug("AC device %s does not support self cleaning", device.name)

    if new_entities:
        _LOGGER.info("Adding %d binary sensor entities", len(new_entities))
        async_add_devices(new_entities)


class ToshibaAcSelfCleaningEntity(ToshibaAcStateEntity, BinarySensorEntity):
    """Reports whether the AC is currently self cleaning."""

    _attr_has_entity_name = True
    _attr_translation_key = "self_cleaning"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:broom"

    def __init__(self, device: ToshibaAcDevice):
        """Initialize the binary sensor."""
        super().__init__(device)
        self._attr_unique_id = f"{device.ac_unique_id}_self_cleaning"

    @property
    def is_on(self) -> bool:
        """Return True if the AC is self cleaning."""
        return self._device.ac_self_cleaning == ToshibaAcSelfCleaning.ON
