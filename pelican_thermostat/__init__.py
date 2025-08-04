"""Pelican Thermostat Integration"""
import ssl
import certifi
import httpx

from homeassistant.helpers import discovery

async def async_setup(hass, config):
    return True

async def async_setup_entry(hass, entry):
    await hass.config_entries.async_forward_entry_setups(entry, ["climate"])
    return True
