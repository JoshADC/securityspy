"""This component provides Switches for SecuritySpy."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    RECORDING_TYPE_ACTION,
    RECORDING_TYPE_CONTINUOUS,
    RECORDING_TYPE_MOTION,
    STRETCH_SNAPSHOTS,
)
from .entity import SecuritySpyEntity
from .models import SecSpyRequiredKeysMixin

DEVICE_TYPE_CAMERA_ENABLED = "camera_enabled"


@dataclass(frozen=True, kw_only=True)
class SecSpyBinarySwitchDescription(SecSpyRequiredKeysMixin, SwitchEntityDescription):
    """Describes SecuritySpy Switch entity."""


SWITCH_ENTITIES: tuple[SecSpyBinarySwitchDescription, ...] = (
    # Disabled by default: unlike arm/disarm which use dedicated GET endpoints,
    # this POSTs to the settings-cameras configuration endpoint. It's meant for
    # setup (e.g. disabling interior cameras when home), not routine toggling.
    SecSpyBinarySwitchDescription(
        key="camera_enabled",
        name="Enabled",
        icon="mdi:video-check",
        device_type=DEVICE_TYPE_CAMERA_ENABLED,
        entity_registry_enabled_default=False,
    ),
    SecSpyBinarySwitchDescription(
        key="enable_action",
        name="Actions",
        icon="mdi:script-text-play",
        device_type=RECORDING_TYPE_ACTION,
    ),
    SecSpyBinarySwitchDescription(
        key="record_motion",
        name="Record Motion",
        icon="mdi:motion-sensor",
        device_type=RECORDING_TYPE_MOTION,
    ),
    SecSpyBinarySwitchDescription(
        key="record_continuous",
        name="Record Continuous",
        icon="mdi:video",
        device_type=RECORDING_TYPE_CONTINUOUS,
    ),
)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """SecuritySpy Switch Platform."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    secspy_object = entry_data["nvr"]
    secspy_data = entry_data["secspy_data"]
    server_info = entry_data["server_info"]
    if not secspy_data.data:
        return

    switches = []
    for description in SWITCH_ENTITIES:
        for device_id in secspy_data.data:
            device_data = secspy_data.data[device_id]
            switches.append(
                SecuritySpySwitch(
                    secspy_object, secspy_data, server_info, device_id, description
                )
            )
            _LOGGER.debug(
                "Adding switch entity %s for Camera %s",
                description.name,
                device_data["name"],
            )
    for device_id in secspy_data.data:
        switches.append(
            SecuritySpyStretchSnapshotsSwitch(
                secspy_object,
                secspy_data,
                server_info,
                device_id,
                entry_data["stretch_snapshots"],
            )
        )

    # update_before_add costs nothing: no entity here defines async_update, so
    # HA skips it and the purely local stretch switch causes no NVR traffic.
    async_add_entities(switches, True)


class SecuritySpySwitch(SecuritySpyEntity, SwitchEntity):
    """A SecuritySpy Switch."""

    def __init__(
        self,
        secspy_object,
        secspy_data,
        server_info,
        device_id,
        description: SecSpyBinarySwitchDescription,
    ):
        """Initialize a SecuritySpy Switch."""
        super().__init__(
            secspy_object, secspy_data, server_info, device_id, description.key
        )
        self._description = description
        self._attr_name = f"{self._device_data['name']} {self._description.name}"
        self._attr_icon = self._description.icon
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self):
        """Return true if device is on."""
        if self._description.device_type == DEVICE_TYPE_CAMERA_ENABLED:
            return self._device_data.get("enabled", True)
        if self._description.device_type == RECORDING_TYPE_ACTION:
            return self._device_data["recording_mode_a"]
        if self._description.device_type == RECORDING_TYPE_MOTION:
            return self._device_data["recording_mode_m"]
        if self._description.device_type == RECORDING_TYPE_CONTINUOUS:
            return self._device_data["recording_mode_c"]

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        if self._description.device_type == DEVICE_TYPE_CAMERA_ENABLED:
            _LOGGER.debug("Enabling camera %s", self._device_name)
            await self.secspy.enable_camera(self._device_id, True)
        elif self._description.device_type == RECORDING_TYPE_ACTION:
            _LOGGER.debug("Turning on Actions")
            await self.secspy.set_arm_mode(self._device_id, RECORDING_TYPE_ACTION, True)
        elif self._description.device_type == RECORDING_TYPE_MOTION:
            _LOGGER.debug("Turning on Motion Recording")
            await self.secspy.set_arm_mode(self._device_id, RECORDING_TYPE_MOTION, True)
        elif self._description.device_type == RECORDING_TYPE_CONTINUOUS:
            _LOGGER.debug("Turning on Continuous Recording")
            await self.secspy.set_arm_mode(
                self._device_id, RECORDING_TYPE_CONTINUOUS, True
            )

        await self.secspy_data.async_refresh(force_camera_update=True)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        if self._description.device_type == DEVICE_TYPE_CAMERA_ENABLED:
            _LOGGER.debug("Disabling camera %s", self._device_name)
            await self.secspy.enable_camera(self._device_id, False)
        else:
            _LOGGER.debug("Turning off Action or Recording")
            await self.secspy.set_arm_mode(
                self._device_id, self._description.device_type, False
            )

        await self.secspy_data.async_refresh(force_camera_update=True)


class SecuritySpyStretchSnapshotsSwitch(SecuritySpyEntity, SwitchEntity, RestoreEntity):
    """Per-camera choice to stretch snapshots to HA's box instead of fitting them.

    SecuritySpy has no such setting, so this is a local preference. Setup seeds
    the per-entry set of stretched camera slugs from HA's restore cache before
    any platform loads; this entity starts from that set, keeps it current, and
    is a RestoreEntity only so HA persists its state for the next seed.

    Fit is the default on purpose: HA's width/height are a bounding box and other
    camera integrations return aspect-correct images. The old stretch (and its
    1920x1080 fallback) was a bug, kept as an opt-in for wide cameras.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:arrow-expand-horizontal"

    def __init__(
        self, secspy_object, secspy_data, server_info, device_id, stretch_snapshots
    ):
        """Initialize the switch."""
        super().__init__(
            secspy_object, secspy_data, server_info, device_id, STRETCH_SNAPSHOTS
        )
        self._stretch_snapshots = stretch_snapshots
        # Camera-name prefix like every other entity here; has_entity_name would
        # be a repo-wide migration, not a one-entity change.
        self._attr_name = f"{self._device_data['name']} Stretch Snapshots"
        self._attr_is_on = self._camera_slug in stretch_snapshots

    def _set_stretch(self, stretch: bool) -> None:
        if stretch:
            self._stretch_snapshots.add(self._camera_slug)
        else:
            self._stretch_snapshots.discard(self._camera_slug)
        self._attr_is_on = stretch

    async def async_turn_on(self, **kwargs):
        """Stretch this camera's snapshots to the requested size."""
        self._set_stretch(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Fit this camera's snapshots at their native aspect ratio."""
        self._set_stretch(False)
        self.async_write_ha_state()
