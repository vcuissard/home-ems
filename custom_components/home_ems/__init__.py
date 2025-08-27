import asyncio
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv
from homeassistant.core import Context
from homeassistant.components.button import ButtonEntity
from .const import *
from .load_balancer import *

_LOGGER = logging.getLogger(__name__)

# Define the config schema
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data[DOMAIN] = {
        "load_balancer"  : LoadBalancer(hass, entry)
    }
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch", "select"])
    async def scheduler_loop():
        hass.data[DOMAIN]["load_balancer"].late_init()
        while True:
            await asyncio.sleep(15 if not config_dev(hass) == True else 5)
            await hass.data[DOMAIN]["load_balancer"].run(hass)
    hass.loop.create_task(scheduler_loop())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    for domain in ["sensor", "select", "switch"]:
        await hass.config_entries.async_forward_entry_unload(entry, domain)
    hass.data[DOMAIN]["load_balancer"] = None
    return True
