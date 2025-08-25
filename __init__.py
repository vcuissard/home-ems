import asyncio
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.script import Script
from homeassistant.components.button import ButtonEntity
from .const import *
from .load_balancer import *

_LOGGER = logging.getLogger(__name__)

# Define the config schema
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: dict):
    
    async def handle_reset_service(call):
        sequence = [
            {"service": "ocpp.clear_profile", "data": {}},
            {"delay": {"seconds": 30}},
            {
                "service": "ocpp.set_charge_rate",
                "data": {
                    "custom_profile": {
                        "chargingProfileId": 10,
                        "stackLevel": 2,
                        "chargingProfileKind": "Relative",
                        "chargingProfilePurpose": "TxDefaultProfile",
                        "chargingSchedule": {
                            "chargingRateUnit": "A",
                            "chargingSchedulePeriod": [
                                {"startPeriod": 0, "limit": 25}
                            ]
                        }
                    }
                }
            }
        ]
        script = Script(hass, sequence, "Reset OCPP EVSE")
        await script.async_run()
    hass.services.async_register(DOMAIN, "reset_ocpp_evse", handle_reset_service)
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data[DOMAIN] = {
        "load_balancer"  : LoadBalancer(hass, entry)
    }
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch", "select"])
    async def scheduler_loop():
        hass.data[DOMAIN]["load_balancer"].late_init()
        while True:
            await asyncio.sleep(15 if CONF_PROD == True else 5)
            await hass.data[DOMAIN]["load_balancer"].run(hass)
    hass.loop.create_task(scheduler_loop())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    for domain in ["sensor", "select", "switch"]:
        await hass.config_entries.async_forward_entry_unload(entry, domain)
    hass.data[DOMAIN]["load_balancer"] = None
    return True
