"""This component provides Number entities for SecuritySpy."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SecuritySpyEntity
from .models import SecSpyRequiredKeysMixin

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SecSpyNumberDescription(SecSpyRequiredKeysMixin, NumberEntityDescription):
    """Describes SecuritySpy Number entity."""

    setting_key: str = ""


NUMBER_ENTITIES: tuple[SecSpyNumberDescription, ...] = (
    SecSpyNumberDescription(
        key="human_sensitivity",
        name="Human Sensitivity",
        icon="mdi:account-eye",
        setting_key="humanSensitivity",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        entity_registry_enabled_default=False,
    ),
    SecSpyNumberDescription(
        key="vehicle_sensitivity",
        name="Vehicle Sensitivity",
        icon="mdi:car-eye",
        setting_key="vehicleSensitivity",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        entity_registry_enabled_default=False,
    ),
    SecSpyNumberDescription(
        key="animal_sensitivity",
        name="Animal Sensitivity",
        icon="mdi:paw",
        setting_key="animalSensitivity",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        entity_registry_enabled_default=False,
    ),
    SecSpyNumberDescription(
        key="motion_sensitivity",
        name="Motion Sensitivity",
        icon="mdi:motion-sensor",
        setting_key="motionSensitivity",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """SecuritySpy Number Platform."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    secspy_object = entry_data["nvr"]
    secspy_data = entry_data["secspy_data"]
    server_info = entry_data["server_info"]
    if not secspy_data.data:
        return

    entities = []
    for description in NUMBER_ENTITIES:
        for device_id in secspy_data.data:
            device_data = secspy_data.data[device_id]
            entities.append(
                SecuritySpyNumber(
                    secspy_object, secspy_data, server_info, device_id, description
                )
            )
            _LOGGER.debug(
                "Adding number entity %s for Camera %s",
                description.name,
                device_data["name"],
            )

    async_add_entities(entities, True)


class SecuritySpyNumber(SecuritySpyEntity, NumberEntity):
    """A SecuritySpy Number entity for sensitivity sliders."""

    def __init__(
        self,
        secspy_object,
        secspy_data,
        server_info,
        device_id,
        description: SecSpyNumberDescription,
    ):
        """Initialize a SecuritySpy Number."""
        super().__init__(
            secspy_object, secspy_data, server_info, device_id, description.key
        )
        self.entity_description = description
        self._description = description
        self._attr_name = f"{self._device_data['name']} {self._description.name}"
        self._attr_icon = self._description.icon
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_native_min_value = description.native_min_value
        self._attr_native_max_value = description.native_max_value
        self._attr_native_step = description.native_step
        self._value = None

    async def async_added_to_hass(self):
        """Fetch initial value when entity is added."""
        await super().async_added_to_hass()
        await self._async_fetch_value()

    async def _async_fetch_value(self):
        """Fetch the current sensitivity value from SecuritySpy."""
        try:
            settings = await self.secspy.get_camera_settings(self._device_id)
            raw = settings.get(self._description.setting_key)
            if raw is not None:
                self._value = int(raw)
        except Exception as err:
            _LOGGER.warning(
                "Could not fetch %s for camera %s: %s",
                self._description.setting_key,
                self._device_name,
                err,
            )

    @property
    def native_value(self):
        """Return the current value."""
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        """Set the sensitivity value."""
        int_value = int(value)
        await self.secspy.set_camera_setting(
            self._device_id, self._description.setting_key, int_value
        )
        self._value = int_value
        self.async_write_ha_state()
