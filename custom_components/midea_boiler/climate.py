"""Climate platform for Midea Boiler."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CMD_HEATING_TARGET_TEMPERATURE,
    CMD_POWER,
    DOMAIN,
    STATUS_HEATING_MODE,
    STATUS_HEATING_TARGET_TEMPERATURE,
    STATUS_IN_TEMPERATURE,
    STATUS_OUT_TEMPERATURE,
    STATUS_POWER,
)

_LOGGER = logging.getLogger(__name__)

# Temperature limits for the boiler
MIN_TEMP = 30
MAX_TEMP = 80


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Midea Boiler climate from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliance_code = entry.data["appliance_code"]
    async_add_entities([MideaBoilerClimate(coordinator, appliance_code, entry)])


class MideaBoilerClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Midea Boiler climate entity."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator,
        appliance_code: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._appliance_code = appliance_code
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{appliance_code}"
        self._attr_name = entry.title
        self._client = coordinator._client

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        data = self.coordinator.data
        if not data:
            return None
        # Use out_temperature (water output temp) as current
        temp = data.get(STATUS_OUT_TEMPERATURE)
        if temp is None:
            temp = data.get(STATUS_IN_TEMPERATURE)
        return float(temp) if temp is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        data = self.coordinator.data
        if not data:
            return None
        temp = data.get(STATUS_HEATING_TARGET_TEMPERATURE)
        return float(temp) if temp is not None else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        data = self.coordinator.data
        if not data:
            return HVACMode.OFF
        power = data.get(STATUS_POWER, "off")
        return HVACMode.HEAT if power == "on" else HVACMode.OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature.

        The Midea boiler requires heating_target_temperature AND heating_mode
        to be sent together in one command — without heating_mode, the
        temperature change is silently ignored.
        """
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        temperature = int(round(temperature))
        _LOGGER.info("Setting boiler temperature to %s", temperature)

        # Get current heating_mode from coordinator data (required for temp change)
        data = self.coordinator.data or {}
        heating_mode = data.get(STATUS_HEATING_MODE, 2)

        await self.hass.async_add_executor_job(
            self._client.send_command,
            self._appliance_code,
            {
                CMD_HEATING_TARGET_TEMPERATURE: temperature,
                "heating_mode": heating_mode,
            },
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode (on/off)."""
        power = "on" if hvac_mode == HVACMode.HEAT else "off"
        _LOGGER.info("Setting boiler power to %s", power)

        await self.hass.async_add_executor_job(
            self._client.send_command,
            self._appliance_code,
            {CMD_POWER: power},
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn the boiler on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the boiler off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "in_temperature": data.get(STATUS_IN_TEMPERATURE),
            "out_temperature": data.get(STATUS_OUT_TEMPERATURE),
            "heating_mode": data.get("heating_mode"),
            "three_way_mode": data.get("three_way_mode"),
            "pump": data.get("pump"),
            "error_code": data.get("error_code"),
            "buzzer": data.get("buzzer"),
        }
