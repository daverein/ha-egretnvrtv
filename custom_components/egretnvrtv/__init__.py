"""The Egret NVR TV integration.

This integration exists purely to pair a TV running the Egret NVR TV Android app with this
Home Assistant instance without the user having to generate or copy a Long-Lived Access
Token by hand, or type this instance's URL into the TV — see config_flow.py for the actual
discovery/PIN-verified pairing exchange.

Once paired, the TV talks to Home Assistant's existing REST/WebSocket APIs directly using
the token it was given, exactly as if the user had entered it manually. This integration has
nothing further to do at runtime, so it sets up no platforms/entities of its own — the config
entry it creates is just a record that a given TV was paired.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Egret NVR TV from a config entry."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Nothing to tear down here — the TV keeps whatever host/token it was given regardless of
    what happens to this config entry. Removing the entry is just Home Assistant forgetting
    the pairing record; re-pairing (which mints a fresh token and revokes the old one, see
    config_flow.py) is how you'd actually disconnect a specific TV.
    """
    return True
