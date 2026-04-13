"""SecuritySpy Platform."""
from __future__ import annotations

import logging

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers import entity_registry as er
from .const import slugify_camera_name
from .pysecspy.errors import InvalidCredentials, RequestError
from .pysecspy.secspy_server import SecSpyServer
from .pysecspy.const import SERVER_ID

from .const import (
    CONF_DISABLE_RTSP,
    CONF_MIN_SCORE,
    CONF_USE_SSL,
    CONF_VERIFY_SSL,
    CONFIG_OPTIONS,
    DEFAULT_BRAND,
    DEFAULT_MIN_SCORE,
    DOMAIN,
    SECURITYSPY_PLATFORMS,
    SERVICE_ENABLE_SCHEDULE_PRESET,
    ENABLE_SCHEDULE_PRESET_SCHEMA,
    MIN_SECSPY_VERSION,
)
from .data import SecuritySpyData

_LOGGER = logging.getLogger(__name__)


@callback
def _async_import_options_from_data_if_missing(hass: HomeAssistant, entry: ConfigEntry):
    options = dict(entry.options)
    data = dict(entry.data)
    modified = False
    for importable_option in CONFIG_OPTIONS:
        if importable_option not in entry.options and importable_option in entry.data:
            options[importable_option] = entry.data[importable_option]
            del data[importable_option]
            modified = True

    if modified:
        hass.config_entries.async_update_entry(entry, data=data, options=options)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SecuritySpy config entries."""
    _async_import_options_from_data_if_missing(hass, entry)

    session = async_create_clientsession(hass)
    securityspyserver = SecSpyServer(
        session,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.options.get(CONF_MIN_SCORE, DEFAULT_MIN_SCORE),
        use_ssl=entry.data.get(CONF_USE_SSL, False),
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, False),
    )

    secspy_data = SecuritySpyData(hass, securityspyserver)

    try:
        server_info = await securityspyserver.get_server_information()
    except InvalidCredentials as unauthex:
        _LOGGER.error("Could not authorize against SecuritySpy. Error: %s.", unauthex)
        return False
    except (RequestError, ClientError) as notreadyerror:
        raise ConfigEntryNotReady from notreadyerror

    if server_info["server_version"] < MIN_SECSPY_VERSION:
        _LOGGER.error(
            "This version of SecuritySpy is too old. Please upgrade to minimum V%s and try again.",
            MIN_SECSPY_VERSION,
        )
        return False

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=server_info[SERVER_ID])

    await secspy_data.async_setup()
    if not secspy_data.last_update_success:
        raise ConfigEntryNotReady

    await _async_migrate_unique_ids(hass, entry, server_info, secspy_data)

    update_listener = entry.add_update_listener(_async_options_updated)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = securityspyserver
    hass.data[DOMAIN][entry.entry_id] = {
        "secspy_data": secspy_data,
        "nvr": securityspyserver,
        "server_info": server_info,
        "update_listener": update_listener,
        "disable_stream": entry.options.get(CONF_DISABLE_RTSP, False),
    }

    await _async_get_or_create_nvr_device_in_registry(hass, entry, server_info)
    await hass.config_entries.async_forward_entry_setups(entry, SECURITYSPY_PLATFORMS)

    # hass.config_entries.async_setup_platforms(entry, SECURITYSPY_PLATFORMS)

    async def async_enable_schedule_preset(service_entries):
        """Call Enable Schedule Preset Handler."""
        await async_handle_enable_schedule_preset(hass, entry, service_entries)

    _LOGGER.debug("Creating Service: Enable Schedule Preset")
    hass.services.async_register(
        DOMAIN,
        SERVICE_ENABLE_SCHEDULE_PRESET,
        async_enable_schedule_preset,
        schema=ENABLE_SCHEDULE_PRESET_SCHEMA,
    )

    return True


async def _async_migrate_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, server_info, secspy_data
) -> None:
    """Migrate entity unique_ids from camera-number-based to camera-name-based format.

    Before March 7 2026, unique_ids used the mutable SecuritySpy camera index number.
    They now use a stable slug derived from the camera name. This migration updates any
    existing registry entries so users don't end up with orphaned entities after updating.
    """
    entity_registry = er.async_get(hass)
    server_id = server_info["server_id"]
    migrated = 0

    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        uid = entity_entry.unique_id
        new_uid = None

        for device_id, camera_data in secspy_data.data.items():
            camera_slug = slugify_camera_name(camera_data["name"])

            # Camera entity format: "{device_id}_{server_id}"
            if uid == f"{device_id}_{server_id}":
                new_uid = f"{camera_slug}_{server_id}"
                break

            # Sensor/switch/binary_sensor/button format: "{sensor_type}_{server_id}_{device_id}"
            old_suffix = f"_{server_id}_{device_id}"
            if uid.endswith(old_suffix):
                sensor_type = uid[: -len(old_suffix)]
                new_uid = f"{sensor_type}_{server_id}_{camera_slug}"
                break

        if new_uid and new_uid != uid:
            existing = entity_registry.async_get_entity_id(
                entity_entry.domain, entity_entry.platform, new_uid
            )
            if existing is None:
                entity_registry.async_update_entity(
                    entity_entry.entity_id, new_unique_id=new_uid
                )
                migrated += 1
                _LOGGER.debug("Migrated entity %s: %s -> %s", entity_entry.entity_id, uid, new_uid)
            else:
                # New-format entity already exists; remove the orphaned old one
                entity_registry.async_remove(entity_entry.entity_id)
                _LOGGER.debug("Removed orphaned entity %s (replaced by %s)", entity_entry.entity_id, existing)

    if migrated:
        _LOGGER.info(
            "SecuritySpy: migrated %d entity unique IDs to name-based format", migrated
        )


async def _async_get_or_create_nvr_device_in_registry(
    hass: HomeAssistant, entry: ConfigEntry, nvr
) -> None:
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, nvr["server_id"])},
        identifiers={(DOMAIN, nvr["server_id"])},
        manufacturer=DEFAULT_BRAND,
        name=entry.data[CONF_ID],
        model="Mac OS X Computer",
        sw_version=nvr["server_version"],
    )


async def async_handle_enable_schedule_preset(hass, entry, service_entries):
    """Enable Schedule Preset."""

    _LOGGER.debug("Setting Schedule Preset ID: %s", service_entries.data["preset_id"])
    preset_id = service_entries.data["preset_id"]
    entry_data = hass.data[DOMAIN][entry.entry_id]
    secspy = entry_data["nvr"]

    await secspy.enable_schedule_preset(preset_id)



async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow device removal from the UI.

    Returning True tells HA it's OK to delete this device and its entities.
    We also clean up the data coordinator's internal state so the device
    doesn't reappear on the next poll (if it's still in SecuritySpy, the
    next full refresh will re-create it — same as the service call).
    """
    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    if entry_data:
        secspy_data = entry_data["secspy_data"]
        server_id = entry_data["server_info"]["server_id"]
        for device_id, cam_data in list(secspy_data.data.items()):
            cam_slug = slugify_camera_name(cam_data["name"])
            mac = f"{server_id}_{cam_slug}"
            if (dr.CONNECTION_NETWORK_MAC, mac) in device_entry.connections:
                secspy_data.data.pop(device_id, None)
                secspy_data._subscriptions.pop(device_id, None)
                _LOGGER.info(
                    "Camera '%s' removed via UI", cam_data.get("name", device_id)
                )
                break

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry):
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload SecuritySpy config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, SECURITYSPY_PLATFORMS
    )

    if unload_ok:
        hass.services.async_remove(DOMAIN, SERVICE_ENABLE_SCHEDULE_PRESET)
        entry_data = hass.data[DOMAIN][entry.entry_id]
        await entry_data["secspy_data"].async_stop()
        entry_data["update_listener"]()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
