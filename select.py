import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import *
from .const import *

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    entity_id = CONF_ENTITY_ID
    name = CONF_NAME
    async_add_entities([
        PersistentSelectSwitch(hass, entity_id, name, "Mode", "mode", [ "Solar", "HC/HP" ])
    ])

class SelectSwitch(SelectEntity):
    def __init__(self, hass, entity_id, name, attr_name, attr_unique_id, options):
        self.hass = hass
        self._attr_name = attr_name
        self._attr_unique_id = f"{entity_id}_{attr_unique_id}"
        self._attr_options = options
        self._attr_current_option = options[0]
        self._attr_entity_category = EntityCategory.CONFIG
        # Device info for Device Info UI
        self._attr_device_info = DeviceInfo(
            identifiers={(entity_id, DOMAIN)},
            manufacturer="Reebox Corp.",
            model="Home-EMS v1.0",
            name="Home-EMS",
            sw_version="1.0.0",
        )

    @property
    def current_option(self) -> str:
        return self._attr_current_option

    async def async_select_option(self, option: str):
        if option in self._attr_options:
            self._attr_current_option = option
            self.async_write_ha_state()

class PersistentSelectSwitch(SelectSwitch, RestoreEntity):
    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        # Try to restore old state
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_current_option = last_state.state
        else:
            self._attr_current_option = self._attr_options[0]


    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
