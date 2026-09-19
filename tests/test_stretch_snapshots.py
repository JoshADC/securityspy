"""The stretch seed and the Stretch Snapshots switch share one set, keyed by camera slug.

The camera platform isn't imported here: HA's camera component pulls in its
stream stack (numpy, PyAV), which the test environment doesn't carry. Its side
of the contract is the single lookup `self._camera_slug in stretch_snapshots`.
"""
from types import SimpleNamespace

from custom_components.securityspy import stretch_slugs_from_restored
from custom_components.securityspy.const import slugify_camera_name
from custom_components.securityspy.switch import SecuritySpyStretchSnapshotsSwitch

SERVER = "W6vI6knoyqB8KJINBLRy"
SERVER_INFO = {
    "server_id": SERVER,
    "server_version": "6.21",
    "schedule_presets": [],
    "server_ip_address": "nvr.local",
    "server_port": 8000,
}


def _camera_data(name: str) -> dict:
    return {
        "name": name,
        "type": "camera",
        "model": "Reolink",
        "online": True,
        "live_stream": "rtsp://nvr.local/stream",
    }


def test_seed_reads_only_this_servers_stretch_switches_that_were_on():
    """Off, foreign-server, and unrelated entities are ignored; slugs keep underscores."""
    switches = [
        ("switch.garage_stretch_snapshots", f"stretch_snapshots_{SERVER}_garage"),
        ("switch.west_yard_stretch_snapshots", f"stretch_snapshots_{SERVER}_west_yard"),
        ("switch.garden_stretch_snapshots", f"stretch_snapshots_{SERVER}_garden"),
        ("switch.other_stretch_snapshots", "stretch_snapshots_OTHERSERVER_garage2"),
        ("switch.garage_record_motion", f"record_motion_{SERVER}_garage"),
    ]
    restored = {
        "switch.garage_stretch_snapshots": "on",
        "switch.west_yard_stretch_snapshots": "on",
        "switch.garden_stretch_snapshots": "off",
        "switch.other_stretch_snapshots": "on",
        "switch.garage_record_motion": "on",
    }
    assert stretch_slugs_from_restored(switches, restored, SERVER) == {
        "garage",
        "west_yard",
    }


def test_switch_starts_from_the_seed_and_mutates_the_shared_set():
    """Setup's seed decides the initial state; toggling edits the set cameras read."""
    data = SimpleNamespace(
        data={"1": _camera_data("Garage"), "11": _camera_data("West Yard")},
        last_update_success=True,
    )
    stretch = {"west_yard"}  # as seeded by setup, before any platform loads
    garage = SecuritySpyStretchSnapshotsSwitch(None, data, SERVER_INFO, "1", stretch)
    west_yard = SecuritySpyStretchSnapshotsSwitch(None, data, SERVER_INFO, "11", stretch)

    assert not garage.is_on
    assert west_yard.is_on

    garage._set_stretch(True)
    assert garage.is_on
    assert stretch == {slugify_camera_name("Garage"), slugify_camera_name("West Yard")}

    west_yard._set_stretch(False)
    west_yard._set_stretch(False)  # discard is idempotent
    assert not west_yard.is_on
    assert stretch == {"garage"}
