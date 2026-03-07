# SecuritySpy HA Integration — Community Fork

## What This Is

A fixed and maintained fork of the abandoned [briis/securityspy](https://github.com/briis/securityspy) Home Assistant integration. Fork lives at [JoshADC/securityspy](https://github.com/JoshADC/securityspy).

## Setup

- **SecuritySpy:** Mac Mini (192.168.8.129), HTTPS port 8001, user `Josh` / `13897921`
- **Home Assistant:** HAOS VM at 192.168.8.212, accessible via `ssh haos`
- **Deployed to:** `/config/custom_components/securityspy/` on HAOS (via `tar cf - custom_components/securityspy/ | ssh haos 'sudo tar xf - -C /config/'`)
- **Integration configured:** Host 192.168.8.129, port 8001, SSL enabled, snapshot mode enabled
- **SecuritySpy version:** 6.18 (updated 2026-02-12)
- **10 cameras active:** Porch East (.247), East corner S (.127), Back 5mpnl, Front doorbell (.125 via go2rtc), W porch 5mpnl (.234), SW Corner (.182), Back West (.155), East Floodlight (.150 via go2rtc), West Floodlight (.134 via go2rtc), Front Floodlight (.221 via go2rtc)
- **HA integration configured for:** Host 192.168.8.129, port 8001, SSL enabled, snapshot mode enabled

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

## SecuritySpy 6.18 Changes (2026-02-12)

Updated remotely. Key API changes vs 6.17:

- **New trigger types:** `aTriggerArrives` / `aTriggerDeparts` (with H/V/A subtypes) — arrives-in-frame vs departs-from-frame, not just generic motion
- **`<shortcutlist>`** per camera in systemInfo (camera shortcuts feature)
- **`homeShortcut0-7`** — 8 Home Helper shortcut slots per camera
- **`cmd0-3` / `cmdName0-3`** — camera shell/URL shortcuts (re-indexed from 1-based to 0-based)
- **`brightness`/`contrast`** reset from 50 to 0 — Metal-accelerated image adjustments changed defaults
- **`aHomeId`** — HomeKit action selector (already populated with existing scenes)
- **No new API endpoints** — checked for /actions, /triggers, /homeassistant, /webhook, etc. All 404.
- **No HA-specific strings** in any web UI JS files — zero matches across all 9 JS files

### Home Helper + Home Assistant

The "Home Assistant integration for Actions and Triggers" from the release notes is in **Home Helper** (the companion macOS app), NOT in SecuritySpy itself. Home Helper bridges SecuritySpy triggers to HomeKit and now also to HA via long-lived access token. Configured and working (2026-02-12).

Push/pull architecture:
- **Push:** SecuritySpy → Action fires → Home Helper → HA (via long-lived access token)
- **Pull (our fork):** HA → SecuritySpy API (state, control, snapshots)

Home Helper config requires the native macOS app (no web UI), so it's a one-time local setup per camera.

## Unexposed API Capabilities

The `settings-cameras?cameraNum=X&format=xml` endpoint exposes a lot that the integration doesn't surface yet:

| Category | Fields | Potential HA Entity |
|----------|--------|---------------------|
| Action trigger config | `aTriggerMotion`, `aTriggerMotionH/V/A`, `aTriggerArrives*`, `aTriggerDeparts*`, `aTriggerAudio`, `aTriggerCamMd` | Switches |
| Shell command | `aShellCommand` | Text entity or service |
| Camera shortcuts | `cmd0-3`, `cmdName0-3` | Button entities |
| Image adjustments | `brightness`, `contrast` | Number entities (sliders) |
| AI sensitivities | `humanSensitivity`, `vehicleSensitivity`, `animalSensitivity` | Number entities |
| Motion sensitivity | `motionSensitivity` | Number entity |
| Animal subtypes | `animalBird`, `animalFish`, `animalQuadruped` | Switches |
| Recording settings | `mcMoviePre/Post`, `ccFreq`, `mcRemoveAge` | Number entities |
| Schedule overrides | 15 override options per camera | Select entity per camera |
| Available scripts | 18 AppleScripts via `/scripts` endpoint | Select + execute |
| Available sounds | 40 sounds via `/sounds` endpoint | Select + play |

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

## Outreach

- **Emailed Ben (Ben Software)** on 2026-02-12 offering the fork. Waiting for response.
- Plan to share on HA Community Forums and Ben Software Forum once tested further.

## TODO

- [ ] Test motion sensors with automations
- [ ] Explore moving camera analysis (security-mcp-server) automations to HA
- [ ] Wait for Ben's response re: taking over the fork
- [ ] Consider exposing more API capabilities (image adjustments, AI sensitivities, arrive/depart triggers)
- [ ] Consider fixing RTSP port for proper video streaming with audio
