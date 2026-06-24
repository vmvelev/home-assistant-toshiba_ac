"""The Toshiba AC integration."""
from __future__ import annotations

import asyncio
import logging


def _toshiba_patch_from_raw() -> None:
    """Make all ToshibaAcFcuState.*.from_raw calls safe against unknown raw values.

    Without this, receiving an unrecognised byte (e.g. 0x60 for H.DA before the
    HADA patch runs) raises KeyError and crashes the state-update callback.
    """
    from toshiba_ac.device.fcu_state import ToshibaAcFcuState

    none_val = ToshibaAcFcuState.NONE_VAL
    patched: list[str] = []

    for name in dir(ToshibaAcFcuState):
        if name.startswith("_"):
            continue
        cls = getattr(ToshibaAcFcuState, name, None)
        if not isinstance(cls, type) or not hasattr(cls, "from_raw"):
            continue

        original = cls.from_raw
        try:
            default = original(none_val)
        except Exception:
            continue

        def _make_safe(orig, default_val):
            def safe_from_raw(raw):
                try:
                    return orig(raw)
                except (KeyError, ValueError):
                    return default_val
            return safe_from_raw

        cls.from_raw = staticmethod(_make_safe(original, default))
        patched.append(name)

    logging.getLogger(__name__).info(
        "toshiba_ac safe-from_raw applied to: %s", ", ".join(patched) or "(none)"
    )


def _toshiba_patch_hada() -> None:
    """Add H.DA airflow mode (raw 0x60) to the ToshibaAcSwingMode enum and
    patch AcSwingMode.from_raw / to_raw for bidirectional encoding.

    Devices with FIXED_1-5 swing support (merit_bits[14]=True, model_id=3)
    expose H.DA as a separate airflow direction mode with raw value 0x60.
    The swing_modes list in the climate entity is extended in climate.py
    (check for 'Fixed 1' presence → add 'Hada').

    Reference: github.com/KaSroka/Toshiba-AC-control/issues/69
    """
    # Step 1 — extend ToshibaAcSwingMode with HADA.
    # CRITICAL: must use toshiba_ac.device.properties, NOT toshiba_ac.utils.properties —
    # they are different class objects even though they share the same name.
    from toshiba_ac.device.properties import ToshibaAcSwingMode

    if "HADA" not in ToshibaAcSwingMode._member_names_:
        _new = object.__new__(ToshibaAcSwingMode)
        # CRITICAL: ToshibaAcSwingMode.NONE has value=None (not int), filter before max().
        _int_vals = [m.value for m in ToshibaAcSwingMode if isinstance(m.value, int)]
        _new._value_ = (max(_int_vals) + 1) if _int_vals else 100
        _new._name_ = "HADA"
        ToshibaAcSwingMode._value2member_map_[_new._value_] = _new
        ToshibaAcSwingMode._member_map_["HADA"] = _new
        ToshibaAcSwingMode._member_names_.append("HADA")
        # ToshibaAcSwingMode.HADA = _new  # Python 3.14: EnumType.__setattr__ raises AttributeError

    hada = ToshibaAcSwingMode._member_map_["HADA"]

    # Step 2 — patch AcSwingMode.from_raw / to_raw.
    # Runs AFTER _toshiba_patch_from_raw so we wrap the safe fallback version.
    from toshiba_ac.device.fcu_state import ToshibaAcFcuState

    _safe_from = ToshibaAcFcuState.AcSwingMode.from_raw
    _safe_to = ToshibaAcFcuState.AcSwingMode.to_raw

    def _from_raw_hada(raw: int) -> ToshibaAcSwingMode:
        return hada if raw == 0x60 else _safe_from(raw)

    def _to_raw_hada(val: ToshibaAcSwingMode) -> int:
        return 0x60 if val is hada else _safe_to(val)

    ToshibaAcFcuState.AcSwingMode.from_raw = staticmethod(_from_raw_hada)
    ToshibaAcFcuState.AcSwingMode.to_raw = staticmethod(_to_raw_hada)

    logging.getLogger(__name__).info("toshiba_ac HADA (0x60) patch applied")


try:
    _toshiba_patch_from_raw()
except Exception:
    logging.getLogger(__name__).exception(
        "Could not apply toshiba_ac safe from_raw patch"
    )

try:
    _toshiba_patch_hada()
except Exception:
    logging.getLogger(__name__).exception(
        "Could not apply toshiba_ac HADA patch"
    )


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
        """Cancel any pending reload and re-wire the handler on the new device object.

        Call this when the SDK reconnects on its own (signalled by SAS token update).
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
