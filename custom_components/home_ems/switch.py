from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import *
from .const import *

async def async_setup_entry(hass, config_entry, async_add_entities):
    entity_id = CONF_ENTITY_ID
    name = CONF_NAME
    async_add_entities([
        PersistentConfigSwitch(hass, entity_id, name, "LoadBalancer", "loadbalancer", EntityCategory.CONFIG),
        PersistentConfigSwitch(hass, entity_id, name, "Holidays", "holidays", EntityCategory.CONFIG),
        ConfigSwitch(hass, entity_id, name, "EV Force", "ev_force"),
        ConfigSwitch(hass, entity_id, name, "EV Request", "ev_request"),
        ConfigSwitch(hass, entity_id, name, "EV HC", "ev_hc"),
        ConfigSwitch(hass, entity_id, name, "EV Tri", "ev_tri"),
        ConfigSwitch(hass, entity_id, name, "Pool Force", "pool_force"),
        ConfigSwitch(hass, entity_id, name, "WaterHeater Force", "water_heater_force"),
        ConfigSwitch(hass, entity_id, name, "WaterHeater Boost", "water_heater_boost")
    ])

class ConfigSwitch(SwitchEntity):
    def __init__(self, hass, entity_id, name, attr_name, attr_unique_id, category=None):
        self.hass = hass
        self._attr_name = attr_name
        self._attr_unique_id = f"{entity_id}_{attr_unique_id}"
        self._state = False
        if category is not None:
            self._attr_entity_category = category
        # Device info for Device Info UI
        self._attr_device_info = DeviceInfo(
            identifiers={(entity_id, DOMAIN)},
            manufacturer="Reebox Corp.",
            model="Home-EMS v1.0",
            name="Home-EMS",
            sw_version="1.0.0",
        )
    @property
    def is_on(self):
        return self._state

    async def async_turn_on(self, **kwargs):
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._state = False
        self.async_write_ha_state()

class PersistentConfigSwitch(ConfigSwitch, RestoreEntity):
    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        # Try to restore old state
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._state = last_state.state == 'on'
