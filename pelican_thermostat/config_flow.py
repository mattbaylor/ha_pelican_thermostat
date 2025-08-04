from homeassistant import config_entries
import voluptuous as vol

@config_entries.HANDLERS.register("pelican_thermostat")
class PelicanConfigFlow(config_entries.ConfigFlow, domain="pelican_thermostat"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title="Pelican Thermostat",
                data=user_input,
            )
        data_schema = vol.Schema({
            vol.Required("username"): str,
            vol.Required("password"): str,
            vol.Required("host"): str,
            vol.Optional("thermostat_name", default="Thermostat"): str,
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
