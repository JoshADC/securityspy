"""Support for SecuritySpy NVR."""
from __future__ import annotations

import logging
from collections.abc import Iterable

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, slugify_camera_name
from .entity import SecuritySpyEntity

_LOGGER = logging.getLogger(__name__)

_PTZ_STANDARDS = {
    "Left": 1,
    "Right": 2,
    "Up": 3,
    "Down": 4,
    "Zoom In": 5,
    "Zoom Out": 6,
    "Stop": 99,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """SecuritySpy Button Platform."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    secspy_object = entry_data["nvr"]
    secspy_data = entry_data["secspy_data"]
    server_info = entry_data["server_info"]
    if not secspy_data.data:
        return

    sensors = []
    for device_id in secspy_data.data:
        device_data = secspy_data.data[device_id]
        if int(device_data["ptz_capabilities"]) > 0:
            preset_index = 12
            for preset in device_data["ptz_presets"]:
                sensors.append(
                    SecuritySpyButtonEntity(
                        secspy_object,
                        secspy_data,
                        server_info,
                        device_id,
                        preset,
                        preset_index,
                    )
                )
                preset_index += 1
                _LOGGER.debug(
                    "Adding Button Entity %s to Camera %s", preset, device_data["name"]
                )
            # Add Standrad Buttons to each ptz capable Camera
            for name, std_preset in _PTZ_STANDARDS.items():
                sensors.append(
                    SecuritySpyButtonEntity(
                        secspy_object,
                        secspy_data,
                        server_info,
                        device_id,
                        name,
                        std_preset,
                    )
                )

    _async_remove_stale_buttons(
        hass, entry, server_info, secspy_data, {button.unique_id for button in sensors}
    )
    async_add_entities(sensors)

    return True


def stale_button_entity_ids(
    registered: Iterable[tuple[str, str]],
    expected_unique_ids: set[str],
    online_camera_suffixes: set[str],
) -> list[str]:
    """Pick registered buttons that an online camera no longer offers.

    Only cameras SecuritySpy currently reports online are candidates: an offline
    or vanished camera keeps its buttons, so a transient outage can't delete
    them along with the user's customisations.
    """
    return [
        entity_id
        for entity_id, unique_id in registered
        if unique_id not in expected_unique_ids
        and any(unique_id.endswith(suffix) for suffix in online_camera_suffixes)
    ]


@callback
def _async_remove_stale_buttons(
    hass: HomeAssistant,
    entry: ConfigEntry,
    server_info,
    secspy_data,
    expected_unique_ids: set[str],
) -> None:
    """Remove registry entries for PTZ buttons that are no longer created.

    SecuritySpy reports ptzcapabilities from the camera's driver profile, so a
    fixed camera claims PTZ until "Disable PTZ" is ticked in its Device settings.
    After that the buttons stop being created here but would otherwise linger in
    the registry as unavailable.
    """
    server_id = server_info["server_id"]
    online_suffixes = {
        f"_{server_id}_{slugify_camera_name(device_data['name'])}"
        for device_data in secspy_data.data.values()
        if device_data["online"]
    }
    registry = er.async_get(hass)
    registered = [
        (entity_entry.entity_id, entity_entry.unique_id)
        for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id)
        if entity_entry.domain == Platform.BUTTON
    ]
    for entity_id in stale_button_entity_ids(
        registered, expected_unique_ids, online_suffixes
    ):
        _LOGGER.debug("Removing PTZ button %s: camera no longer reports it", entity_id)
        registry.async_remove(entity_id)


class SecuritySpyButtonEntity(SecuritySpyEntity, ButtonEntity):
    """A SecuritySpy Button entity."""

    def __init__(
        self,
        secspy_object,
        secspy_data,
        server_info,
        device_id,
        preset_id,
        preset_index,
    ):
        """Initialize the Button entity."""
        super().__init__(secspy_object, secspy_data, server_info, device_id, preset_id)
        self._preset_id = preset_id
        self._preset_index = preset_index
        self._attr_name = f"{self._device_data['name']} {preset_id.capitalize()}"
        self._attr_device_class = ButtonDeviceClass.UPDATE

    async def async_press(self) -> None:
        """Press the button."""

        _LOGGER.debug(
            "Activating PTZ command %s for Camera %s", self._preset_id, self._device_id
        )
        _preset_speed = 80
        if self._preset_index < 12:
            _preset_speed = 40
        await self.secspy.set_ptz_preset(
            self._device_id, self._preset_index, _preset_speed
        )
