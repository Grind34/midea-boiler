"""Config flow for Midea Boiler."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import MideaCloudClient, MideaCloudError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_APPLIANCE_CODE,
    CONF_TOKEN_EXPIRY,
    CONF_TOKEN_PWD,
    CONF_UID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Midea Boiler."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._email: str | None = None
        self._password: str | None = None
        self._appliances: list[dict[str, Any]] = []
        self._uid: str | None = None
        self._access_token: str | None = None
        self._token_pwd: str | None = None
        self._token_expiry: float | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step (email + password)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]

            client = MideaCloudClient(self._email, self._password)
            try:
                await self.hass.async_add_executor_job(client.login)
                self._uid = client.uid
                self._access_token = client.access_token
                self._token_pwd = client.token_pwd
                self._token_expiry = client.token_expiry
                self._appliances = await self.hass.async_add_executor_job(
                    client.list_appliances
                )
            except MideaCloudError:
                errors["base"] = "auth_error"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during login")
                errors["base"] = "unknown"
            else:
                if not self._appliances:
                    errors["base"] = "no_devices"
                else:
                    return await self.async_step_select_device()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user select which appliance to add."""
        errors: dict[str, str] = {}

        if user_input is not None:
            appliance_code = user_input[CONF_APPLIANCE_CODE]
            # Find the selected appliance for a friendly name
            name = "Midea Boiler"
            for app in self._appliances:
                if str(app.get("applianceCode")) == appliance_code:
                    name = app.get("name", name)
                    break

            await self.async_set_unique_id(appliance_code)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=name,
                data={
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_APPLIANCE_CODE: appliance_code,
                    CONF_UID: self._uid,
                    CONF_ACCESS_TOKEN: self._access_token,
                    CONF_TOKEN_PWD: self._token_pwd,
                    CONF_TOKEN_EXPIRY: self._token_expiry,
                },
            )

        # Build selector options from appliances
        options = []
        for app in self._appliances:
            code = str(app.get("applianceCode", ""))
            name = app.get("name", f"Device {code}")
            app_type = app.get("type", "")
            options.append(
                {"value": code, "label": f"{name} (type: {app_type}, id: {code})"}
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_APPLIANCE_CODE): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="select_device",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication."""
        return await self.async_step_user()
