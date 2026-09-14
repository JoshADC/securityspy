#!/usr/bin/env bash
# Local Home Assistant testbed: runs HA in Docker with this repo's integration
# bind-mounted read-only, so code edits go live on `restart`. HA state lives in
# ./config (gitignored). Onboard at http://localhost:8123, then add the
# SecuritySpy integration and point it at your NVR.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
NAME="${HA_TESTBED_NAME:-ha-securityspy-testbed}"
PORT="${HA_TESTBED_PORT:-8123}"
IMAGE="${HA_TESTBED_IMAGE:-ghcr.io/home-assistant/home-assistant:stable}"
CONFIG="${HA_TESTBED_CONFIG:-$REPO/config}"
# Host timezone so HA's clock and log timestamps match the machine.
TZ_NAME="${TZ:-$(readlink /etc/localtime 2>/dev/null | sed 's|.*/zoneinfo/||' || true)}"

case "${1:-}" in
  up)
    mkdir -p "$CONFIG"
    docker run -d --name "$NAME" \
      -p "$PORT:8123" \
      -e TZ="${TZ_NAME:-UTC}" \
      -v "$CONFIG:/config" \
      -v "$REPO/custom_components/securityspy:/config/custom_components/securityspy:ro" \
      "$IMAGE" >/dev/null
    echo "Home Assistant starting at http://localhost:$PORT (first boot takes a minute)"
    ;;
  down) docker rm -f "$NAME" >/dev/null && echo "removed $NAME (config/ kept)" ;;
  restart) docker restart "$NAME" >/dev/null && echo "restarted $NAME" ;;
  logs) docker logs -f --tail 200 "$NAME" ;;
  *) echo "usage: $0 up|down|restart|logs" >&2; exit 1 ;;
esac
