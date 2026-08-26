"""Config flow for Toshiba AC integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
import random
from typing import Any

from toshiba_ac.device_manager import ToshibaAcDeviceManager
from toshiba_ac.utils.http_api import ToshibaAcHttpApiAuthError, ToshibaAcHttpApiError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    device_id = f"{random.getrandbits(64):016x}"

    _LOGGER.debug("Toshiba validate input %s %s", data["username"], device_id)

    device_manager = ToshibaAcDeviceManager(
        data["username"], data["password"], device_id
    )

    try:
        sas_token = await device_manager.connect()
        _LOGGER.debug("Toshiba connection OK")
        # http_api is guaranteed set after a successful connect(), but
        # shutdown() below clears it, so the token fields must be read here.
        # Storing them means setup never has to repeat the login validate did.
        assert device_manager.http_api is not None
        access_token = device_manager.http_api.access_token
        access_token_type = device_manager.http_api.access_token_type
        consumer_id = device_manager.http_api.consumer_id
    except ToshibaAcHttpApiAuthError as ex:
        _LOGGER.error("Toshiba connection error %s", ex)
        raise InvalidAuth from ex
    except ToshibaAcHttpApiError as ex:
        _LOGGER.error("Toshiba connection error %s", ex)
        raise CannotConnect from ex
    finally:
        await device_manager.shutdown()

    return {
        "username": data["username"],
        "password": data["password"],
        "device_id": device_id,
        "sas_token": sas_token,
        "access_token": access_token,
        "access_token_type": access_token_type,
        "consumer_id": consumer_id,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Toshiba AC."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            data = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(data["consumer_id"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input["username"], data=data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> FlowResult:
        """Handle re-authentication when the stored credentials stop working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-authentication by re-validating the account password.

        The username is fixed to the existing entry; only the password is asked,
        since re-auth is triggered for the same account whose credentials expired.
        """
        reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                data = await validate_input(
                    self.hass,
                    {
                        "username": reauth_entry.data["username"],
                        "password": user_input["password"],
                    },
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(reauth_entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required("password"): str}),
            description_placeholders={"username": reauth_entry.data["username"]},
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
