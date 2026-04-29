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

    reconnect_state = {
        "attempts": 0,
        "cancel_retry": None,
        "reloading": False,
    }

    async def _do_reconnect(now=None) -> None:
        """Actually attempt a reconnect."""
        reconnect_state["cancel_retry"] = None
        if reconnect_state["reloading"]:
            return
        dm = hass.data[DOMAIN].get(entry.entry_id)
        if dm is None:
            return
        attempt = reconnect_state["attempts"] + 1
        reconnect_state["attempts"] = attempt
        if attempt > MAX_RECONNECT_ATTEMPTS:
            _LOGGER.error("Failed to reconnect after %d attempts, reloading", MAX_RECONNECT_ATTEMPTS)
            reconnect_state["reloading"] = True
            reconnect_state["attempts"] = 0
            await hass.config_entries.async_reload(entry.entry_id)
            return
        _LOGGER.info("Reconnection attempt %d of %d", attempt, MAX_RECONNECT_ATTEMPTS)
        try:
            try:
                await asyncio.wait_for(dm.shutdown(), timeout=10)
            except Exception as ex:
                _LOGGER.debug("Shutdown before reconnect: %s", ex)
            dm.sas_token = None
            dm.http_api = None
            dm.amqp_api = None
            dm.devices = {}
            new_sas_token = await asyncio.wait_for(dm.connect(), timeout=CONNECTION_TIMEOUT)
            if new_sas_token and new_sas_token != entry.data.get("sas_token"):
                new_data = {**entry.data, "sas_token": new_sas_token}
                hass.config_entries.async_update_entry(entry, data=new_data)
            _attach_disconnect_handler(dm)
            await asyncio.wait_for(dm.get_devices(), timeout=CONNECTION_TIMEOUT)
            _LOGGER.info("Successfully reconnected to Toshiba AC cloud")
            reconnect_state["attempts"] = 0
        except asyncio.TimeoutError:
            _LOGGER.warning("Reconnection attempt %d timed out", attempt)
            _schedule_retry()
        except Exception as ex:
            _LOGGER.warning("Reconnection attempt %d failed: %s", attempt, ex)
            _schedule_retry()

    def _schedule_retry() -> None:
        if reconnect_state["reloading"] or reconnect_state["cancel_retry"] is not None:
            return
        attempt = reconnect_state["attempts"]
        delay = RECONNECT_BACKOFF[min(attempt, len(RECONNECT_BACKOFF) - 1)]
        _LOGGER.info("Scheduling reconnect in %d seconds", delay)
        reconnect_state["cancel_retry"] = async_call_later(hass, delay, _do_reconnect)

    def _on_disconnect_in_thread() -> None:
        _LOGGER.warning("Azure IoT Hub connection lost -- scheduling reconnect")
        if reconnect_state["cancel_retry"] is not None or reconnect_state["reloading"]:
            return
        hass.loop.call_soon_threadsafe(_schedule_retry)

    def _attach_disconnect_handler(dm) -> None:
        """Wire up disconnect callback. on_connection_state_change takes NO args."""
        if dm.amqp_api and dm.amqp_api.device:
            def _on_state_change() -> None:
                if not dm.amqp_api.device.connected:
                    _on_disconnect_in_thread()
            dm.amqp_api.device.on_connection_state_change = _on_state_change

    try:
        new_sas_token = await asyncio.wait_for(device_manager.connect(), timeout=CONNECTION_TIMEOUT)
        if new_sas_token and new_sas_token != entry.data.get("sas_token"):
            _LOGGER.info("SAS token updated during connection")
            new_data = {**entry.data, "sas_token": new_sas_token}
            hass.config_entries.async_update_entry(entry, data=new_data)
    except asyncio.TimeoutError:
        try:
            await device_manager.shutdown()
        except Exception:
            pass
        raise ConfigEntryNotReady(f"Connection timed out after {CONNECTION_TIMEOUT}s. Will retry.")
    except Exception as ex:
        error_str = str(ex).lower()
        if any(k in error_str for k in ("401", "unauthorize", "credential", "password")):
            raise ConfigEntryAuthFailed(f"Authentication failed: {ex}.") from ex
        raise ConfigEntryNotReady(f"Failed to connect to Toshiba AC service: {ex}") from ex

    async def sas_token_updated(new_token: str) -> None:
        new_data = {**entry.data, "sas_token": new_token}
        hass.config_entries.async_update_entry(entry, data=new_data)

    device_manager.on_sas_token_updated_callback.add(sas_token_updated)
    _attach_disconnect_handler(device_manager)
    hass.data[DOMAIN][entry.entry_id] = device_manager
    hass.data[DOMAIN][f"{entry.entry_id}_reconnect"] = reconnect_state
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
        raise ConfigEntryNotReady(f"Timed out fetching devices after {CONNECTION_TIMEOUT}s.")
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
    _LOGGER.info("Unloading Toshiba AC integration")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        reconnect_state = hass.data[DOMAIN].pop(f"{entry.entry_id}_reconnect", {})
        reconnect_state["reloading"] = True
        if reconnect_state.get("cancel_retry"):
            reconnect_state["cancel_retry"]()
        device_manager = hass.data[DOMAIN].pop(entry.entry_id)
        try:
            await asyncio.wait_for(device_manager.shutdown(), timeout=10)
        except asyncio.TimeoutError:
            _LOGGER.warning("Shutdown timed out during unload")
        except Exception as ex:
            _LOGGER.warning("Error shutting down device manager: %s", ex)
    return unload_ok
