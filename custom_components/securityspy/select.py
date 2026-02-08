"""Schedule Preset select entity for SecuritySpy."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_ATTRIBUTION,
    DEFAULT_BRAND,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SecuritySpy schedule preset select."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    secspy_object = entry_data["nvr"]
    server_info = entry_data["server_info"]

    presets = server_info.get("schedule_presets", [])
    if not presets:
        return

    async_add_entities(
        [SecuritySpySchedulePresetSelect(secspy_object, server_info, presets)]
    )


class SecuritySpySchedulePresetSelect(SelectEntity):
    """A select entity for SecuritySpy schedule presets."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:shield-home"

    def __init__(self, secspy, server_info, presets):
        """Initialize the select entity."""
        self.secspy = secspy
        self._server_id = server_info["server_id"]
        self._server_ip = server_info["server_ip_address"]
        self._server_port = server_info["server_port"]
        self._use_ssl = server_info.get("use_ssl", False)

        # Build name->id mapping
        self._preset_map = {}
        options = []
        for preset in presets:
            name = preset["name"]
            preset_id = preset["id"]
            self._preset_map[name] = preset_id
            options.append(name)

        self._attr_options = options
        self._attr_current_option = None
        self._attr_unique_id = f"schedule_preset_{self._server_id}"
        self._attr_name = "Schedule Preset"

        _scheme = "https" if self._use_ssl else "http"
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self._server_id)},
            identifiers={(DOMAIN, self._server_id)},
            manufacturer=DEFAULT_BRAND,
            name=server_info.get("server_name", "SecuritySpy"),
            configuration_url=f"{_scheme}://{self._server_ip}:{self._server_port}/",
        )

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        return {
            ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION,
        }

    async def async_select_option(self, option: str) -> None:
        """Handle the user selecting a preset."""
        preset_id = self._preset_map.get(option)
        if preset_id is None:
            _LOGGER.error("Unknown schedule preset: %s", option)
            return

        _LOGGER.debug("Activating schedule preset '%s' (id=%s)", option, preset_id)
        await self.secspy.enable_schedule_preset(preset_id)
        self._attr_current_option = option
        self.async_write_ha_state()
