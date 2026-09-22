"""Snapshot sizing must preserve the camera's aspect ratio."""
import asyncio

import pytest

from pysecspy.secspy_server import SecSpyServer, _as_int, fit_snapshot_size


@pytest.mark.parametrize(
    ("native", "box", "expected"),
    [
        # Same aspect: exact fit.
        ((1920, 1080), (1280, 720), (1280, 720)),
        # 4:3 camera in the frontend's default 16:9 box: height-bound.
        ((1280, 960), (1280, 720), (960, 720)),
        # 16:9 camera in a 4:3 card: width-bound.
        ((1920, 1080), (640, 480), (640, 360)),
        # Portrait camera in a landscape box.
        ((1080, 1920), (1280, 720), (405, 720)),
    ],
)
def test_fits_inside_box_preserving_aspect(native, box, expected):
    """Fitted size is bounded by the box and keeps the native aspect."""
    assert fit_snapshot_size(*native, *box) == expected


def test_single_dimension_hint_derives_the_other():
    """A lone width or height hint derives the other from the native aspect."""
    assert fit_snapshot_size(1920, 1080, 640, None) == (640, 360)
    assert fit_snapshot_size(1920, 1080, None, 270) == (480, 270)


@pytest.mark.parametrize(
    ("native", "box"),
    [
        ((1920, 1080), (None, None)),  # no hints: native resolution
        ((1920, 1080), (3840, 2160)),  # box larger than native: never upscale
        ((1920, 1080), (1920, 1080)),  # exactly native
        ((0, 0), (640, 360)),  # native unknown (camera offline at startup)
    ],
)
def test_returns_none_when_no_size_params_should_be_sent(native, box):
    """No hints, unknown native size, or no downscale needed means send nothing."""
    assert fit_snapshot_size(*native, *box) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1920", 1920), (1080, 1080), (None, 0), ("", 0), ("n/a", 0)],
)
def test_as_int_treats_garbage_as_unknown(value, expected):
    """Dimensions from systemInfo arrive as strings; anything unparsable is unknown."""
    assert _as_int(value) == expected


class _FakeResponse:
    status = 200
    reason = "OK"

    async def read(self):
        return b"jpeg"


class _FakeSession:
    def __init__(self):
        self.urls = []

    async def get(self, url, **_kwargs):
        self.urls.append(url)
        return _FakeResponse()


def test_default_url_is_unchanged_from_earlier_releases():
    """Untouched cameras must request exactly what every earlier release did.

    An upgrade may not alter a single snapshot: HA's box verbatim when it gives
    hints, and the 1920x1080 fallback when it gives none. Anyone relying on the
    old look keeps it until they turn a camera's Fit Snapshots switch on.
    """
    session = _FakeSession()
    server = SecSpyServer(session, "nvr.local", 8000, "user", "pass")
    server._update_device("1", {"image_width": "1280", "image_height": "960"})

    asyncio.run(server.get_snapshot_image("1", 1280, 720))
    asyncio.run(server.get_snapshot_image("1", 640, None))
    asyncio.run(server.get_snapshot_image("1"))
    asyncio.run(server.get_snapshot_image("9", 640, 480))  # camera not yet seen

    assert "/image?cameraNum=1&width=1280&height=720&quality=75&auth=" in session.urls[0]
    assert "/image?cameraNum=1&width=640&height=1080&quality=75&auth=" in session.urls[1]
    assert "/image?cameraNum=1&width=1920&height=1080&quality=75&auth=" in session.urls[2]
    assert "/image?cameraNum=9&width=640&height=480&quality=75&auth=" in session.urls[3]


def test_fit_url_uses_fitted_size_and_omits_size_when_unknown():
    """With Fit Snapshots on, the URL carries the fitted size, or no size at all."""
    session = _FakeSession()
    server = SecSpyServer(session, "nvr.local", 8000, "user", "pass")
    server._update_device("1", {"image_width": "1280", "image_height": "960"})

    asyncio.run(server.get_snapshot_image("1", 1280, 720, fit=True))
    asyncio.run(server.get_snapshot_image("1", 640, None, fit=True))
    asyncio.run(server.get_snapshot_image("1", fit=True))
    asyncio.run(server.get_snapshot_image("9", 640, 480, fit=True))  # camera unseen

    assert "/image?cameraNum=1&width=960&height=720&quality=75&auth=" in session.urls[0]
    assert "/image?cameraNum=1&width=640&height=480&quality=75&auth=" in session.urls[1]
    assert "/image?cameraNum=1&quality=75&auth=" in session.urls[2]
    assert "/image?cameraNum=9&quality=75&auth=" in session.urls[3]
