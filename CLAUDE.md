# SecuritySpy HA Integration — Community Fork

## What This Is

A fixed and maintained fork of the abandoned [briis/securityspy](https://github.com/briis/securityspy) Home Assistant integration. Fork lives at [JoshADC/securityspy](https://github.com/JoshADC/securityspy).

## Setup

- **SecuritySpy:** Mac Mini (192.168.8.129), HTTPS port 8001, user `Josh` / `13897921`
- **Home Assistant:** HAOS VM at 192.168.8.212, accessible via `ssh haos`
- **Deployed to:** `/config/custom_components/securityspy/` on HAOS (via `tar cf - custom_components/securityspy/ | ssh haos 'sudo tar xf - -C /config/'`)
- **Integration configured:** Host 192.168.8.129, port 8001, SSL enabled, snapshot mode enabled
- **4 cameras:** Doorbell (.125), 3 Floodlights (.134, .150, .221)

## What We Fixed (2026-02-08)

1. **Vendored pysecspy** — bundled the abandoned `pysecspy` library directly into `custom_components/securityspy/pysecspy/` so there's no external PyPI dependency
2. **Schedule preset crash (Issue #101)** — xmltodict returns a dict instead of a list for single presets; fixed in `pysecspy/secspy_server.py`
3. **SSL/HTTPS support** — added `use_ssl` config option, propagated through all URL generation (config_flow, __init__, entity, secspy_data, secspy_server)
4. **HA compatibility** — fixed deprecated `OptionsFlowHandler.__init__` pattern, removed incorrect `@callback` on async method in button.py
5. **Schedule Preset select entity** — new `select.py` that creates a dropdown on the NVR device for activating presets (Armed, Disarmed, etc.)
6. **Renamed confusing RTSP option** — "Disable the RTSP stream" → "Use snapshot mode instead of RTSP (recommended for HTTPS)"
7. **Minor:** fixed "Max OSX" typo, removed orphaned `enable_disable_camera` service definition

## Architecture Notes

- Integration uses a custom pub/sub data coordinator (`data.py`), NOT HA's `DataUpdateCoordinator`
- SecuritySpy API: HTTP REST (XML via xmltodict) for device list + long-lived event stream for real-time updates (ARM/DISARM/MOTION/CLASSIFY events)
- Arm/disarm switches call `/setSchedule?cameraNum={id}&schedule={0|1}&mode={A|M|C}`
- Schedule presets call `/setPreset?id={preset_id}`
- RTSP streams don't work over HTTPS (URL uses HTTP port for RTSP). Snapshot mode (JPEG refresh) works fine.
- SecuritySpy recompresses audio to AAC, so RTSP audio *would* work if the RTSP connection issue were fixed

## Known Remaining Issues

- **RTSP over HTTPS:** The RTSP URL uses the HTTPS port, but RTSP is a separate protocol. Would need to discover/configure the correct RTSP port.
- **Websocket reconnection:** If SecuritySpy restarts, the event stream may not reconnect reliably (pysecspy only checks every 120s). No polling fallback.
- **Global event scores:** AI detection scores (human/vehicle/animal) use global state that can cross-contaminate between cameras during simultaneous events.

## Deploying Changes

```bash
# From ~/securityspy-ha-fix/
tar cf - custom_components/securityspy/ | ssh haos 'sudo tar xf - -C /config/'
# Then restart HA or reload the integration
```

## TODO

- [ ] Test motion sensors with automations
- [ ] Explore moving camera analysis (security-mcp-server) automations to HA
- [ ] Share fork on HA Community Forums and Ben Software Forum once tested
- [ ] Consider fixing RTSP port for proper video streaming with audio
