import logging
import copy
from .devices.boiler import Boiler
from .devices.linky import Linky
from .devices.evcharger import EVCharger
from .devices.pool_heater import PoolHeater
from .utils import *
from .const import *

_LOGGER = logging.getLogger(__name__)

class LoadBalancer:

    def __init__(self, hass, config_entry):
        self.hass = hass
        self.config_entry = config_entry
        self.boiler = Boiler(hass, CONF_BOILER_ID, CONF_BOILER_ALLOW_RESISTOR_ID, CONF_BOILER_PHASE)
        self.linky = Linky(hass, CONF_LINKY_ID)
        self.evcharger = EVCharger(hass, CONF_EV_CHARGER_ID, CONF_EV_CHARGER_PHASE_MONO)
        self.pool_heater = PoolHeater(hass, CONF_POOL_HEATER_PHASE)        
        self.devices = [ self.boiler, self.evcharger, self.pool_heater ]
        self.devices_for_update = [ self.boiler, self.evcharger, self.pool_heater ]

    def late_init(self):
        for device in self.devices:
            device.late_init()

    def activate_if(self, current_export):
        for device in self.devices:
            if device.activate_if(current_export):
                return True
        return False

    def update(self, current_export, current_import):
        for device in self.devices_for_update:
            if device.is_active():
                if device.update(current_export, current_import):
                    return True
        return False

    async def run(self, hass):

        if config_loadbalancer_enabled(hass) != True:
            return

        current_export = self.linky.get_phases_current_export()                
        current_import = self.linky.get_phases_current_import()                

        _LOGGER.debug(f"Injection available: export={current_export}A import={current_import}A")

        if self.activate_if(current_export):
            _LOGGER.info("new device activated, wait for 5min before taking any new decision")
            # TODO: timer management
            return

        if self.update(current_export, current_import):
            _LOGGER.info("device config updated, wait for 5min before taking any new decision")
            # TODO: timer management
            return
