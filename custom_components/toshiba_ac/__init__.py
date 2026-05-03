"""The Toshiba AC integration."""
from __future__ import annotations

import asyncio
import logging

from toshiba_ac.device_manager import ToshibaAcDeviceManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

PLATFORMS = ["climate", "select", "sensor", "switch"]

_LOGGER = logging.getLogger(__name__)

# The Azure IoT SDK logs WARNING-level noise for every connection drop/retry
# via its internal handle_exceptions logger. Raise it to ERROR so only genuine
# unrecoverable SDK errors appear in HA logs.
logging.getLogger("azure.iot.device").setLevel(logging.ERROR)

CONNECTION_TIMEOUT = 30
# How long to wait for the SDK to self-heal before forcing a reload.
# The Azure IoT SDK reconnects within ~1s on normal SAS token refresh;
# this delay must be long enough that we don't reload a self-healing connection.
_RELOAD_DELAY = 30

_AUTH_KEYWORDS = ("401", "unauthorize", "credential", "password")


class _ReconnectManager:
    """Manages automatic reconnection to the Toshiba AC cloud."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Store HA context and initialise state."""
        self._hass = hass
        self._entry = entry
        self.cancel_retry = None
        self.reloading = False

    async def do_reload(self, _now=None) -> None:
        """Reload the config entry to establish a fresh connection."""
        self.cancel_retry = None
        if self.reloading:
            return
        self.reloading = True
        _LOGGER.info("Reloading Toshiba AC integration to restore connection")
        await self._hass.config_entries.async_reload(self._entry.entry_id)

    def _schedule_reload(self) -> None:
        """Schedule a reload; must be called on the HA event loop."""
        if self.cancel_retry is not None or self.reloading:
            return
        _LOGGER.warning(
            "Azure IoT Hub disconnected -- reloading in %ds if SDK does not recover",
            _RELOAD_DELAY,
        )
        self.cancel_retry = async_call_later(self._hass, _RELOAD_DELAY, self.do_reload)

    def on_disconnect(self) -> None:
        """Handle an IoT Hub disconnect event from a background thread."""
        if self.cancel_retry is not None or self.reloading:
            return
        self._hass.loop.call_soon_threadsafe(self._schedule_reload)

    def on_sdk_reconnected(self, dm) -> None:
        """Called when the SDK reconnects on its own (signalled by SAS token update).

        Cancels any pending reload and re-wires the disconnect handler on the
        new device object that the SDK created during its internal reconnect.
        """
        if self.cancel_retry is not None:
            _LOGGER.info("SDK reconnected -- cancelling scheduled reload")
            self.cancel_retry()
            self.cancel_retry = None
        self.attach_disconnect_handler(dm)

    def attach_disconnect_handler(self, dm) -> None:
        """Wire up the disconnect callback on the current amqp_api.device.

        Captures the specific device object so stale callbacks from old objects
        (replaced by the SDK during its internal reconnect) are ignored.
        """
        if not (dm.amqp_api and dm.amqp_api.device):
            return

        device = dm.amqp_api.device

        def _on_state_change() -> None:
            # If dm has moved to a newer device object this callback is stale.
            if not (dm.amqp_api and dm.amqp_api.device is device):
                return
            if not device.connected:
                self.on_disconnect()

        device.on_connection_state_change = _on_state_change

    def cancel(self) -> None:
        """Stop reconnection activity when the entry is being unloaded."""
        self.reloading = True
        if self.cancel_retry:
            self.cancel_retry()


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Toshiba AC component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Toshiba AC from a config entry."""
    # Never pass a stored SAS token on startup -- it may have expired while HA
    # was stopped. Always fetch a fresh one via RegisterMobileDevice.
    device_manager = ToshibaAcDeviceManager(
        entry.data["username"],
        entry.data["password"],
        entry.data["device_id"],
        sas_token=None,
    )
    reconnect_mgr = _ReconnectManager(hass, entry)

    try:
        new_sas_token = await asyncio.wait_for(
            device_manager.connect(), timeout=CONNECTION_TIMEOUT
        )
        if new_sas_token and new_sas_token != entry.data.get("sas_token"):
            _LOGGER.info("SAS token updated during connection")
            new_data = {**entry.data, "sas_token": new_sas_token}
            hass.config_entries.async_update_entry(entry, data=new_data)
    except asyncio.TimeoutError:
        try:
            await device_manager.shutdown()
        except Exception:
            pass
        raise ConfigEntryNotReady(
            f"Connection timed out after {CONNECTION_TIMEOUT}s. Will retry."
        )
    except Exception as ex:
        error_str = str(ex).lower()
        if any(k in error_str for k in _AUTH_KEYWORDS):
            raise ConfigEntryAuthFailed(f"Authentication failed: {ex}.") from ex
        raise ConfigEntryNotReady(
            f"Failed to connect to Toshiba AC service: {ex}"
        ) from ex

    async def sas_token_updated(new_token: str) -> None:
        new_data = {**entry.data, "sas_token": new_token}
        hass.config_entries.async_update_entry(entry, data=new_data)
        # SAS token update means the SDK successfully reconnected on its own.
        # Cancel any pending reload and re-wire the handler on the new device object.
        reconnect_mgr.on_sdk_reconnected(device_manager)

    device_manager.on_sas_token_updated_callback.add(sas_token_updated)
    reconnect_mgr.attach_disconnect_handler(device_manager)
    hass.data[DOMAIN][entry.entry_id] = device_manager
    hass.data[DOMAIN][f"{entry.entry_id}_reconnect"] = reconnect_mgr
    await _async_register_services(hass)

    # Pre-fetch devices before forwarding to platforms.
    # Caches result so all 4 platforms get it instantly (no 60s deadline risk).
    # Small delay avoids WAF 403s during simultaneous HA startup.
    await asyncio.sleep(2)
    try:
        await asyncio.wait_for(device_manager.get_devices(), timeout=CONNECTION_TIMEOUT)
    except asyncio.TimeoutError:
        try:
            await device_manager.shutdown()
        except Exception:
            pass
        raise ConfigEntryNotReady(
            f"Timed out fetching devices after {CONNECTION_TIMEOUT}s."
        )
    except Exception as ex:
        try:
            await device_manager.shutdown()
        except Exception:
            pass
        raise ConfigEntryNotReady(f"Failed to fetch devices: {ex}") from ex

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "reconnect"):
        return

    async def handle_reconnect(call: ServiceCall) -> None:
        for entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_reload(entry.entry_id)

    hass.services.async_register(DOMAIN, "reconnect", handle_reconnect)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Toshiba AC integration")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        reconnect_mgr = hass.data[DOMAIN].pop(f"{entry.entry_id}_reconnect", None)
        if reconnect_mgr:
            reconnect_mgr.cancel()
        device_manager = hass.data[DOMAIN].pop(entry.entry_id)
        try:
            await asyncio.wait_for(device_manager.shutdown(), timeout=10)
        except asyncio.TimeoutError:
            _LOGGER.warning("Shutdown timed out during unload")
        except Exception as ex:
            _LOGGER.warning("Error shutting down device manager: %s", ex)
    return unload_ok
