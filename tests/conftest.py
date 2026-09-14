"""Make the vendored pysecspy importable without a Home Assistant install.

custom_components/securityspy/__init__.py imports homeassistant, so importing
through the package would need a full HA install just to test the library.
"""
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "custom_components" / "securityspy")
)
