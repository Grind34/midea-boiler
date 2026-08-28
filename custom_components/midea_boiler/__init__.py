"""The Midea Boiler integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import MideaCloudClient, MideaCloudError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_APPLIANCE_CODE,
    CONF_TOKEN_EXPIRY,
    CONF_TOKEN_PWD,
    CONF_UID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Midea Boiler from a config entry."""
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    appliance_code = entry.data[CONF_APPLIANCE_CODE]
    saved_uid = entry.data.get(CONF_UID)
    saved_token = entry.data.get(CONF_ACCESS_TOKEN)
    saved_token_pwd = entry.data.get(CONF_TOKEN_PWD)
    saved_token_expiry = entry.data.get(CONF_TOKEN_EXPIRY)

    client = MideaCloudClient(
        email,
        password,
        uid=saved_uid,
        access_token=saved_token,
        token_pwd=saved_token_pwd,
        token_expiry=saved_token_expiry,
    )

    if not client.has_session():
        try:
            await hass.async_add_executor_job(client.login)
        except MideaCloudError as err:
            _LOGGER.error("Login failed: %s", err)
            return False
        _persist_session(hass, entry, client)
    elif client.token_needs_refresh():
        _LOGGER.info("Access token near expiry, refreshing")
        refreshed = await hass.async_add_executor_job(client.refresh_token)
        if refreshed:
            _persist_session(hass, entry, client)
        else:
            _LOGGER.info("Token refresh failed, performing full login")
            await hass.async_add_executor_job(client.login)
            _persist_session(hass, entry, client)

    coordinator = MideaBoilerCoordinator(
        hass, client, appliance_code, DEFAULT_SCAN_INTERVAL, entry
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        _LOGGER.info("First refresh with cached token failed, re-logging in")
        await hass.async_add_executor_job(client.login)
        _persist_session(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _persist_session(hass: HomeAssistant, entry: ConfigEntry, client: MideaCloudClient) -> None:
    """Save uid, access_token, token_pwd and expiry into the config entry."""
    if not client.uid or not client.access_token:
        return
    new_data = dict(entry.data)
    new_data[CONF_UID] = client.uid
    new_data[CONF_ACCESS_TOKEN] = client.access_token
    if client.token_pwd:
        new_data[CONF_TOKEN_PWD] = client.token_pwd
    if client.token_expiry:
        new_data[CONF_TOKEN_EXPIRY] = client.token_expiry
    hass.config_entries.async_update_entry(entry, data=new_data)
    _LOGGER.info("Midea session persisted to config entry")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class MideaBoilerCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Midea Boiler."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MideaCloudClient,
        appliance_code: str,
        scan_interval: int,
        entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._client = client
        self._appliance_code = appliance_code
        self._entry = entry

    async def _async_update_data(self) -> dict:
        """Fetch data from Midea cloud."""
        if self._client.token_needs_refresh():
            _LOGGER.info("Token near expiry, refreshing before poll")
            refreshed = await self.hass.async_add_executor_job(
                self._client.refresh_token
            )
            if refreshed and self._entry is not None:
                _persist_session(self.hass, self._entry, self._client)

        try:
            return await self.hass.async_add_executor_job(
                self._client.get_status, self._appliance_code
            )
        except MideaCloudError as err:
            _LOGGER.warning("Failed to fetch status: %s", err)
            if self._entry is not None:
                try:
                    await self.hass.async_add_executor_job(self._client.login)
                    _persist_session(self.hass, self._entry, self._client)
                    return await self.hass.async_add_executor_job(
                        self._client.get_status, self._appliance_code
                    )
                except MideaCloudError:
                    pass
            raise
