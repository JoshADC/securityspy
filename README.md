# SecuritySpy for Home Assistant (Community Fork)

This is a maintained fork of [briis/securityspy](https://github.com/briis/securityspy), the Home Assistant integration for [Ben Software](https://www.bensoftware.com)'s SecuritySpy surveillance system. The original integration was abandoned by its author. This fork fixes several blocking bugs and adds new features.

**Original author:** [@briis](https://github.com/briis) — thank you for building this integration and open-sourcing it.

## What's Fixed in This Fork

- **SSL/HTTPS support** — the original only worked over HTTP. This fork adds a "Use SSL" checkbox in the config flow, so it works with SecuritySpy's HTTPS web server.
- **Schedule preset crash (Issue [#101](https://github.com/briis/securityspy/issues/101))** — the integration would fail to load if SecuritySpy had only one schedule preset. Fixed.
- **Vendored pysecspy library** — the `pysecspy` dependency (also abandoned) is now bundled directly, so there are no external PyPI dependencies to break.
- **Home Assistant compatibility** — fixed deprecated `OptionsFlowHandler` pattern and incorrect `@callback` decorator that caused warnings on modern HA versions.
- **Schedule Preset select entity** — new dropdown entity on the NVR device that lets you activate schedule presets (arm/disarm all cameras at once) directly from your dashboard or automations.

## Features

This integration provides the following entity types:

| Entity Type | What It Does |
|-------------|-------------|
| **Camera** | Live RTSP streams and snapshot images |
| **Binary Sensor** | Motion detection and online/offline status per camera |
| **Switch** | Arm/disarm motion recording, continuous recording, and actions per camera |
| **Select** | Activate SecuritySpy schedule presets (master arm/disarm across all cameras) |
| **Sensor** | Recording mode status and detected object type per camera |
| **Button** | PTZ controls for cameras with pan/tilt/zoom |

**Note:** There is no audio on live streams, as Home Assistant only supports AAC audio and SecuritySpy sends audio in uLaw format.

## Prerequisites

1. **Enable the Web Server** in SecuritySpy: Preferences > Web. Note the port number (default 8000). SSL is now supported.
2. **Add a Web Server User** with *Administrator* privileges, or at minimum *Get Live Video and Images* and *Arm and Disarm, set schedules* privileges.
3. SecuritySpy version **5.3.4 or newer** is required.

![Web Server Setup](https://github.com/briis/securityspy/blob/master/support_files/secspy_webserver_sm.png) ![User Setup](https://github.com/briis/securityspy/blob/master/support_files/secspy_users_sm.png)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three-dot menu (top right) > **Custom Repositories**
3. Paste: `https://github.com/JoshADC/securityspy`
4. Select category: **Integration**
5. Click Add, then install **SecuritySpy for Home Assistant**
6. Restart Home Assistant

### Manual Installation

Copy the `custom_components/securityspy` folder (including the `pysecspy` and `translations` subdirectories) into your Home Assistant `/config/custom_components/` directory and restart.

## Configuration

Go to **Settings > Devices & Services > Add Integration** and search for **SecuritySpy**.

| Field | Description |
|-------|-------------|
| **Host** | IP address of your SecuritySpy Mac (e.g. `192.168.1.10`) |
| **Port** | Web server port (e.g. `8000` or `8001`) |
| **Username** | Web server username |
| **Password** | Web server password |
| **Use SSL** | Check this if your SecuritySpy web server uses HTTPS |

## Schedule Presets

If you have schedule presets configured in SecuritySpy (Preferences > Scheduling > Schedule Presets), they will appear as a **Select** entity on the NVR device. You can use this as a master arm/disarm control on your dashboard or in automations:

```yaml
# Example: Arm all cameras at sunset
automation:
  - alias: Arm cameras at sunset
    trigger:
      - platform: sun
        event: sunset
    action:
      - action: select.select_option
        target:
          entity_id: select.securityspy_schedule_preset
        data:
          option: "Armed"
```

## Automation Examples

### Capture Image When Person Is Detected

```yaml
alias: Capture snapshot when person is detected
trigger:
  - platform: state
    entity_id: binary_sensor.motion_outdoor
    attribute: event_object
    to: human
action:
  - action: camera.snapshot
    target:
      entity_id: camera.outdoor
    data:
      filename: /config/www/camera_outdoor.jpg
```

### Download Video Recording After Motion

```yaml
alias: Download Recording after motion
trigger:
  - platform: state
    entity_id: binary_sensor.motion_outdoor
    from: "on"
    to: "off"
action:
  - action: securityspy.download_latest_motion_recording
    data:
      entity_id: camera.outdoor
      filename: /media/outdoor_latest.m4v
mode: restart
```

## Debug Logging

```yaml
logger:
  default: error
  logs:
    custom_components.securityspy: debug
```

## Credits

- Original integration by [@briis](https://github.com/briis) ([original repo](https://github.com/briis/securityspy))
- Fork maintained by [@JoshADC](https://github.com/JoshADC)
- Bug fixes and new features developed with assistance from [Claude Code](https://claude.ai/claude-code)
