"""SecuritySpy Data."""
import datetime
import json
import logging
import time
from collections import OrderedDict

_LOGGER = logging.getLogger(__name__)

CAMERA_KEYS = {
    "state",
    "recordingSettings_A",
    "recordingSettings_C",
    "recordingSettings_M",
    "recording_mode_a",
    "recording_mode_c",
    "recording_mode_m",
    "isOnline",
    "enabled",
    "reason",
    "lastMotion",
    "isMotionDetected",
}

EVENT_SMART_DETECT_ZONE = "smart"
EVENT_MOTION = "motion"
EVENT_DISCONNECT = "disconnect"

EVENT_LENGTH_PRECISION = 3

MAX_SUPPORTED_CAMERAS = 256
MAX_EVENT_HISTORY_IN_STATE_MACHINE = MAX_SUPPORTED_CAMERAS * 2

PROCESSED_EVENT_EMPTY = {
    "event_start": None,
    "event_on": False,
    "event_type": None,
    "event_online": True,
    "event_length": 0,
    "event_object": None,
    "event_score_human": 0,
    "event_score_vehicle": 0,
    "event_score_animal": 0,
}

REASON_CODES = {"128": "Human", "256": "Vehicle", "512": "Animal"}


def process_camera(server_id, server_credential, camera, include_events):
    """Process the camera json."""

    # If addtional keys are checked, update CAMERA_KEYS
    camera_id = camera["number"]
    # Get if camera is online
    online = camera["connected"] == "yes"
    # Get if camera is enabled
    enabled = camera.get("enabled")
    # Get Recording Mode
    if camera.get("recordingSettings_A") is not None:
        recording_mode_a = camera.get("recordingSettings_A")
    else:
        recording_mode_a = camera["mode-a"] == "armed"
    if camera.get("recordingSettings_C") is not None:
        recording_mode_c = camera.get("recordingSettings_C")
    else:
        recording_mode_c = camera["mode-c"] == "armed"
    if camera.get("recordingSettings_M") is not None:
        recording_mode_m = camera.get("recordingSettings_M")
    else:
        recording_mode_m = camera["mode-m"] == "armed"
    # Live Image
    use_ssl = server_credential.get("use_ssl", False)
    http_scheme = "https" if use_ssl else "http"
    base_url = f"{server_credential['host']}:{server_credential['port']}"
    base_stream = f"rtsp://{base_url}/stream?auth={server_credential['token']}"
    live_stream = f"{base_stream}&cameraNum={camera_id}&codec=h264"
    # Jpeg Image
    image_width = str(camera["width"])
    image_height = str(camera["height"])
    latest_image = f"{http_scheme}://{base_url}/image?auth={server_credential['token']}&cameraNum={camera_id}&width={image_width}&height={image_height}&quality=75"
    # PTZ
    ptz_capabilities = camera.get("ptzcapabilities")
    preset_list = []
    if ptz_capabilities is not None and int(ptz_capabilities) > 0:
        # Build a list of PTZ Presets
        for preset in range(1, 10):
            if camera.get(f"preset-name-{preset}") is not None:
                preset_list.append(camera.get(f"preset-name-{preset}"))

    # Other Settings
    ip_address = "Local" if camera["devicetype"] == "Local" else camera.get("address")

    camera_update = {
        "name": str(camera["name"]),
        "type": "camera",
        "model": str(camera["devicename"]),
        "online": online,
        "enabled": enabled,
        "recording_mode_a": recording_mode_a,
        "recording_mode_c": recording_mode_c,
        "recording_mode_m": recording_mode_m,
        "ip_address": ip_address,
        "live_stream": live_stream,
        "latest_image": latest_image,
        "image_width": image_width,
        "image_height": image_height,
        "fps": str(camera["current-fps"]),
        "video_format": str(camera["video-format"]),
        "ptz_capabilities": ptz_capabilities,
        "ptz_presets": preset_list,
    }

    if server_id is not None:
        camera_update["server_id"] = server_id
    if include_events:
        # Get the last time motion occured
        if camera.get("timesincelastmotion") is not None:
            last_update = int(time.time()) + int(camera["timesincelastmotion"])
            camera_update["last_motion"] = datetime.datetime.fromtimestamp(
                last_update / 1000
            ).strftime("%Y-%m-%d %H:%M:%S")
        else:
            camera_update["last_motion"] = None

    return camera_update


def camera_update_from_ws_frames(
    state_machine, server_credential, action_json, data_json
):
    """Convert a websocket frame to internal format."""

    if action_json["modelKey"] != "camera":
        raise ValueError("Model key must be camera")

    camera_id = action_json["id"]

    if not state_machine.has_device(camera_id):
        _LOGGER.debug("Skipping non-adopted camera: %s", data_json)
        return None, None

    camera = state_machine.update(camera_id, data_json)

    if data_json.keys().isdisjoint(CAMERA_KEYS):
        _LOGGER.debug("Skipping camera data: %s", data_json)
        return None, None

    _LOGGER.debug("Processing camera: %s", camera)
    processed_camera = process_camera(None, server_credential, camera, True)

    return camera_id, processed_camera


def event_from_ws_frames(state_machine, action_json, data_json):
    """Convert a websocket frame to internal format.

    20140927091955 1 3 ARM_C
    20190927091955 2 3 ARM_M
    20190927092026 3 3 MOTION 760 423 320 296
    20190927092026 4 3 CLASSIFY HUMAN 99
    20190927092026 5 3 TRIGGER_M 9
    20190927092036 6 3 MOTION 0 432 260 198
    20190927092036 7 3 CLASSIFY HUMAN 5 VEHICLE 95
    20190927092040 8 X NULL
    20190927092050 9 3 FILE /Volumes/VolName/Cam/2019-07-26/26-07-2019 15-52-00 C Cam.m4v
    20190927092055 10 3 DISARM_M
    20190927092056 11 3 OFFLINE
    20210519172650 24 0 MOTION_END

    """

    if action_json["modelKey"] != "event":
        raise ValueError("Model key must be event")

    action = action_json["action"]
    event_id = action_json["id"]

    if action == "add":
        device_id = data_json.get("camera")
        if device_id is None:
            return None, None
        state_machine.add(event_id, data_json)
        event = data_json
    elif action == "update":
        event = state_machine.update(event_id, data_json)
        if not event:
            return None, None
        device_id = event.get("camera")
    else:
        raise ValueError("The action must be add or update")

    _LOGGER.debug("Processing event: %s", event)
    processed_event = process_event(event)

    return device_id, processed_event


def camera_event_from_ws_frames(state_machine, action_json, data_json):
    """Create processed events from the camera model."""

    if "isMotionDetected" not in data_json and "timesincelastmotion" not in data_json and "isOnline" not in data_json:
        return None

    camera_id = action_json["id"]
    start_time = None
    event_length = 0
    event_on = False
    is_online = data_json.get("isOnline")

    last_motion = int(time.time()) + int(data_json["timesincelastmotion"])
    is_motion_detected = data_json.get("isMotionDetected")

    if is_motion_detected is None:
        start_time = state_machine.get_motion_detected_time(camera_id)
        event_on = start_time is not None
    else:
        if is_motion_detected:
            event_on = True
            start_time = last_motion
            state_machine.set_motion_detected_time(camera_id, start_time)
        else:
            start_time = state_machine.get_motion_detected_time(camera_id)
            state_machine.set_motion_detected_time(camera_id, None)
            if last_motion is None:
                last_motion = round(time.time() * 1000)

    if start_time is not None and last_motion is not None:
        event_length = round(
            (float(last_motion) - float(start_time)) / 1000, EVENT_LENGTH_PRECISION
        )

    return {
        "event_on": event_on,
        "event_type": "motion",
        "event_start": start_time,
        "event_length": event_length,
        "event_online": is_online,
    }


def process_event(event):
    """Convert an event to our format."""
    start = event.get("start")
    end = event.get("end")
    event_type = event.get("type")
    event_reason = event.get("reason")
    event_online = event.get("isOnline")
    event_score_human = 0 if not event.get("event_score_human") else event.get("event_score_human")
    event_score_vehicle = 0 if not event.get("event_score_vehicle") else event.get("event_score_vehicle")
    event_score_animal = 0 if not event.get("event_score_animal") else event.get("event_score_animal")

    event_length = 0
    start_time = None

    if start:
        start_time = _process_timestamp(start)
    if end:
        event_length = round(
            (float(end) / 1000) - (float(start) / 1000), EVENT_LENGTH_PRECISION
        )

    event_object = (
        "None" if event_reason not in REASON_CODES else REASON_CODES.get(event_reason)
    )

    processed_event = {
        "event_on": False,
        "event_type": event_type,
        "event_start": start_time,
        "event_length": event_length,
        "event_object": event_object,
        "event_score_human": event_score_human,
        "event_score_vehicle": event_score_vehicle,
        "event_score_animal": event_score_animal,
        "event_online": event_online,
    }

    if event_type in (EVENT_MOTION, EVENT_SMART_DETECT_ZONE):
        processed_event["last_motion"] = start_time
        if not end:
            processed_event["event_on"] = True

    return processed_event


def _process_timestamp(time_stamp):
    return datetime.datetime.strptime(time_stamp, "%Y%m%d%H%M%S").strftime(
        "%Y-%m-%d %H:%M:%S"
    )


class SecspyDeviceStateMachine:
    """A simple state machine for events."""

    def __init__(self):
        """Init the state machine."""
        self._devices = {}
        self._motion_detected_time = {}

    def has_device(self, device_id):
        """Check to see if a device id is in the state machine."""
        return device_id in self._devices

    def update(self, device_id, new_json):
        """Update an device in the state machine."""
        self._devices.setdefault(device_id, {}).update(new_json)
        return self._devices[device_id]

    def set_motion_detected_time(self, device_id, timestamp):
        """Set device motion start detected time."""
        self._motion_detected_time[device_id] = timestamp

    def get_motion_detected_time(self, device_id):
        """Get device motion start detected time."""
        return self._motion_detected_time.get(device_id)


class SecspyEventStateMachine:
    """A simple state machine for cameras."""

    def __init__(self):
        """Init the state machine."""
        self._events = FixSizeOrderedDict(max_size=MAX_EVENT_HISTORY_IN_STATE_MACHINE)

    def add(self, event_id, event_json):
        """Add an event to the state machine."""
        self._events[event_id] = event_json

    def update(self, event_id, new_event_json):
        """Update an event in the state machine and return the merged event."""
        event_json = self._events.get(event_id)
        if event_json is None:
            return None
        event_json.update(new_event_json)
        return event_json


class FixSizeOrderedDict(OrderedDict):
    """A fixed size ordered dict."""

    def __init__(self, *args, max_size=0, **kwargs):
        """Create the FixSizeOrderedDict."""
        self._max_size = max_size
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        """Set an update up to the max size."""
        OrderedDict.__setitem__(self, key, value)
        if self._max_size > 0:
            if len(self) > self._max_size:
                self.popitem(False)
