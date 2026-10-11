"""PTZ buttons a camera no longer offers are removed, but only for online cameras."""
from custom_components.securityspy.button import stale_button_entity_ids

SERVER = "W6vI6knoyqB8KJINBLRy"


def _uid(name: str, slug: str) -> str:
    return f"{name}_{SERVER}_{slug}"


REGISTERED = [
    ("button.garage_left", _uid("Left", "garage")),
    ("button.garage_zoom_in", _uid("Zoom In", "garage")),
    ("button.garden_left", _uid("Left", "garden")),
    ("button.attic_left", _uid("Left", "attic")),
]


def test_removes_buttons_an_online_camera_no_longer_reports():
    """Garage dropped to ptzcapabilities 0: its buttons go, Garden's expected one stays."""
    expected = {_uid("Left", "garden")}
    online = {f"_{SERVER}_garage", f"_{SERVER}_garden"}
    assert stale_button_entity_ids(REGISTERED, expected, online) == [
        "button.garage_left",
        "button.garage_zoom_in",
    ]


def test_keeps_buttons_of_offline_or_vanished_cameras():
    """Attic is offline or gone, so its button is untouched even though unexpected."""
    online = {f"_{SERVER}_garden"}
    assert stale_button_entity_ids(REGISTERED, set(), online) == ["button.garden_left"]


def test_no_expected_buttons_clears_every_online_camera():
    """No camera reports PTZ any more: every online camera's buttons are removed."""
    online = {f"_{SERVER}_garage", f"_{SERVER}_garden", f"_{SERVER}_attic"}
    assert stale_button_entity_ids(REGISTERED, set(), online) == [
        entity_id for entity_id, _ in REGISTERED
    ]


def test_camera_suffix_needs_the_full_slug():
    """A slug that merely ends like another's ("yard" vs "backyard") does not match."""
    registered = [("button.backyard_left", _uid("Left", "backyard"))]
    assert stale_button_entity_ids(registered, set(), {f"_{SERVER}_yard"}) == []
