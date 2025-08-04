"""Pelican Thermostat climate platform."""

import asyncio
import logging
import ssl
import certifi
import httpx


from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACMode,
    ClimateEntityFeature,
)
from homeassistant.const import UnitOfTemperature

_LOGGER = logging.getLogger(__name__)

# --- Both setup entrypoints: YAML & UI/config_flow

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Support classic YAML config (deprecated)."""
    conf = config.get("pelican_thermostat") if config else {}
    if not conf:
        _LOGGER.error("No pelican_thermostat configuration found.")
        return
    device = PelicanDevice(
        conf["username"],
        conf["password"],
        conf["host"],
        conf.get("thermostat_name", "Thermostat"),
    )
    async_add_entities([PelicanClimate(device)])

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Support config flow (UI) setup."""
    data = config_entry.data
    device = PelicanDevice(
        data["username"],
        data["password"],
        data["host"],
        data.get("thermostat_name", "Thermostat"),
    )
    async_add_entities([PelicanClimate(device)])

# --- Device Helper

class PelicanDevice:
    def __init__(self, username, password, host, thermostat_name):
        self._username = username
        self._password = password
        self._host = host
        self._thermostat_name = thermostat_name

        # Create an SSL context and preload certifi's CA bundle once
        ssl_context = ssl.create_default_context()
        ssl_context.load_verify_locations(certifi.where())
        # Create one client to use for all requests
        self._client = httpx.AsyncClient(verify=ssl_context)

    async def _request(self, params):
        import httpx
        import xmltodict
        url = f"https://{self._host}/api.cgi"
        
        resp = await self._client.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return xmltodict.parse(resp.text)

    async def poll_status(self):
        params = {
            "username": self._username,
            "password": self._password,
            "request": "get",
            "object": "Thermostat",
            "selection": f"name:{self._thermostat_name}",
            "value": ";".join([
                "temperature", "system", "heatSetting", "coolSetting", "runStatus",
                "fan", "humidity", "co2Level", "status", "humidifySetting",
                "dehumidifySetting", "co2Setting", "frontKeypad"
            ]),
        }
        return await self._request(params)

    async def set_value(self, key, value):
        import httpx
        import xmltodict
        url = f"https://{self._host}/api.cgi"
        data = {
            "username": self._username,
            "password": self._password,
            "request": "set",
            "object": "Thermostat",
            "selection": f"name:{self._thermostat_name}",
            "value": f"{key}:{value}",
        }
        # Use multipart/form-data by passing data as files=
        resp = await self._client.post(url, files=data, timeout=15)
        resp.raise_for_status()
        return xmltodict.parse(resp.text)

# --- Climate Entity

class PelicanClimate(ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )
    _attr_hvac_modes = [
        HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.HEAT_COOL
    ]

    def __init__(self, device):
        self._device = device
        self._attr_name = "Pelican Thermostat"
        self._current_temperature = None
        self._target_temperature_low = None
        self._target_temperature_high = None
        self._hvac_mode = HVACMode.OFF

    @property
    def current_temperature(self):
        return self._current_temperature

    @property
    def target_temperature_low(self):
        return self._target_temperature_low

    @property
    def target_temperature_high(self):
        return self._target_temperature_high

    @property
    def hvac_mode(self):
        return self._hvac_mode

    async def async_update(self):
        try:
            data = await self._device.poll_status()
            t = data.get('result', {}).get('Thermostat', {})
            self._current_temperature = float(t.get('temperature', 0))
            self._target_temperature_low = float(t.get('heatSetting', 0))
            self._target_temperature_high = float(t.get('coolSetting', 0))
            mode = t.get('system', '').lower()
            self._hvac_mode = {
                'off': HVACMode.OFF,
                'heat': HVACMode.HEAT,
                'cool': HVACMode.COOL,
                'auto': HVACMode.HEAT_COOL,
            }.get(mode, HVACMode.OFF)
        except Exception as e:
            _LOGGER.error(f"Pelican state update error: {e}")

    async def async_set_temperature(self, **kwargs):
        tasks = []
        if "temperature" in kwargs:
            if self.hvac_mode == HVACMode.HEAT:
                tasks.append(self._device.set_value('heatSetting', kwargs["temperature"]))
            elif self.hvac_mode == HVACMode.COOL:
                tasks.append(self._device.set_value('coolSetting', kwargs["temperature"]))
        if "target_temperature_low" in kwargs:
            tasks.append(self._device.set_value('heatSetting', kwargs["target_temperature_low"]))
        if "target_temperature_high" in kwargs:
            tasks.append(self._device.set_value('coolSetting', kwargs["target_temperature_high"]))
        if tasks:
            await asyncio.gather(*tasks)
        await self.async_update()

    async def async_set_hvac_mode(self, hvac_mode):
        value_map = {
            HVACMode.OFF: "Off",
            HVACMode.HEAT: "Heat",
            HVACMode.COOL: "Cool",
            HVACMode.HEAT_COOL: "Auto",
        }
        val = value_map.get(hvac_mode, "Off")
        await self._device.set_value("system", val)
        await self.async_update()
