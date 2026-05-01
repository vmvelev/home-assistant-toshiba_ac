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

CONNECTION_TIMEOUT = 30
RECONNECT_BACKOFF = [10, 60, 300]
MAX_RECONNECT_ATTEMPTS = 3

_AUTH_KEYWORDS = ("401", "unauthorize", "credential", "password")


class _ReconnectManager:
    """Manages automatic reconnection to the Toshiba AC cloud."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Store HA context and initialise counters."""
        self._hass = hass
        self._entry = entry
        self.attempts = 0
        self.cancel_retry = None
        self.reloading = False

    async def do_reconnect(self, now=None) -> None:
        """Attempt a reconnect; reload the entry after too many failures."""
        self.cancel_retry = None
        if self.reloading:
            return
        dm = self._hass.data[DOMAIN].get(self._entry.entry_id)
        if dm is None:
            return
        self.attempts += 1
        if self.attempts > MAX_RECONNECT_ATTEMPTS:
            _LOGGER.error(
                "Failed to reconnect after %d attempts, reloading",
                MAX_RECONNECT_ATTEMPTS,
            )
            self.reloading = True
            self.attempts = 0
            await self._hass.config_entries.async_reload(self._entry.entry_id)
            return
        _LOGGER.info(
            "Reconnection attempt %d of %d", self.attempts, MAX_RECONNECT_ATTEMPTS
        )
        try:
            try:
                await asyncio.wait_for(dm.shutdown(), timeout=10)
            except Exception as ex:
                _LOGGER.debug("Shutdown before reconnect: %s", ex)
            dm.sas_token = None
            dm.http_api = None
            dm.amqp_api = None
            dm.devices = {}
            new_sas_token = await asyncio.wait_for(
                dm.connect(), timeout=CONNECTION_TIMEOUT
            )
            if new_sas_token and new_sas_token != self._entry.data.get("sas_token"):
                new_data = {**self._entry.data, "sas_token": new_sas_token}
                self._hass.config_entries.async_update_entry(self._entry, data=new_data)
            self.attach_disconnect_handler(dm)
            await asyncio.wait_for(dm.get_devices(), timeout=CONNECTION_TIMEOUT)
            _LOGGER.info("Successfully reconnected to Toshiba AC cloud")
            self.attempts = 0
        except asyncio.TimeoutError:
            _LOGGER.warning("Reconnection attempt %d timed out", self.attempts)
            self.schedule_retry()
        except Exception as ex:
            _LOGGER.warning("Reconnection attempt %d failed: %s", self.attempts, ex)
            self.schedule_retry()

    def schedule_retry(self) -> None:
        """Schedule the next reconnect attempt with exponential backoff."""
        if self.reloading or self.cancel_retry is not None:
            return
        delay = RECONNECT_BACKOFF[min(self.attempts, len(RECONNECT_BACKOFF) - 1)]
        _LOGGER.info("Scheduling reconnect in %d seconds", delay)
        self.cancel_retry = async_call_later(self._hass, delay, self.do_reconnect)

    def on_disconnect(self) -> None:
        """Handle an IoT Hub disconnect event from a background thread."""
        _LOGGER.warning("Azure IoT Hub connection lost -- scheduling reconnect")
        if self.cancel_retry is not None or self.reloading:
            return
        self._hass.loop.call_soon_threadsafe(self.schedule_retry)

    def attach_disconnect_handler(self, dm) -> None:
        """Wire up the disconnect callback; on_connection_state_change takes no args."""
        if not (dm.amqp_api and dm.amqp_api.device):
            return

        def _on_state_change() -> None:
            if not dm.amqp_api.device.connected:
                self.on_disconnect()

        dm.amqp_api.device.on_connection_state_change = _on_state_change

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
