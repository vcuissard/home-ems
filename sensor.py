import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from datetime import timedelta, datetime
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import *

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """Set up the Home EMS Sensor from a config entry."""
    name = CONF_NAME
    entity_id = CONF_ENTITY_ID
    load_balancer = hass.data[DOMAIN]["load_balancer"]

    # Create the sensor entity
    sensor = HomeEMSSensor(hass, config_entry, name, entity_id, load_balancer)
    async_add_entities([sensor])


class HomeEMSSensor(SensorEntity):
    """Representation of a Home EMS Sensor."""

    def __init__(self, hass, config_entry, name, entity_id, load_balancer):
        self.hass = hass
        self.config_entry = config_entry
        self._state = None
        self._attr_name = name
        self._attr_unique_id = entity_id  # Set a unique ID for the entity
        self.load_balancer = load_balancer

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:transmission-tower"

    async def async_update(self):
        """Fetch new state data for the sensor asynchronously."""
        _LOGGER.info("Async update of Sensor")
