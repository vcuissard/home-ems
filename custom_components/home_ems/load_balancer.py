import logging
import copy
from datetime import datetime, timedelta
from .devices.water_heater import WaterHeater
from .devices.linky import Linky
from .devices.enphase import Enphase
from .devices.evcharger import EVCharger
from .devices.pool_heater import PoolHeater
from .devices.cro import CRO
from .utils import *
from .const import *

_LOGGER = logging.getLogger(__name__)

class LoadBalancer:

    def __init__(self, hass, config_entry):
        self.hass = hass
        self.config_entry = config_entry
        self.water_heater = WaterHeater(hass, CONF_WATER_HEATER_ID, CONF_WATER_HEATER_PHASE)
        self.linky = Linky(hass, CONF_LINKY_ID)
        self.enphase = Enphase(hass, CONF_ENHPASE_ID)
        self.evcharger = EVCharger(hass, CONF_EV_CHARGER_ID, CONF_EV_CHARGER_PHASE_MONO)
        self.cro = CRO(hass, CONF_CRO_ID, CONF_CRO_PHASE)
        self.pool_heater = PoolHeater(hass, CONF_POOL_HEATER_PHASE)        
        self.devices = [ self.water_heater, self.evcharger, self.cro, self.pool_heater ]
        self.devices_for_update = self.devices.copy()
        self.loop_count = 0
        self.next_run = datetime.now()

    def late_init(self):
        for device in self.devices:
            device.late_init()

    def activate_if(self, power_phases):
        for device in self.devices:
            next_run = device.activate_if(power_phases)
            if next_run > 0:
                _LOGGER.info(f"[loadbalancer]{device.logger_name()} activated => wait for {next_run}min before taking any new decision")
                return next_run
        return 0

    def update(self, power_phases):
        if len(self.devices_for_update) == 0:            
            self.devices_for_update = self.devices.copy()
        while len(self.devices_for_update) > 0:
            device = self.devices_for_update.pop()
            if device.is_active():
                next_run = device.update(power_phases)
                if next_run > 0:
                    _LOGGER.info(f"[loadbalancer]{device.logger_name()} updated => wait for {next_run}min before taking any new decision")
                    return next_run        
        return 0

    async def run(self, hass):

        if config_loadbalancer_enabled(hass) != True:
            # Disabled
            return

        now = datetime.now()

        # All logic need device and linky to update. Depending on the action
        # a longer wait might be required
        if now < self.next_run:
            _LOGGER.debug(f"[loadbalancer] too early next_run={self.next_run})")
            if config_dev(hass):
                self.next_run = now
            return

        # Extract current import/export from Enphase
        power_phases = self.enphase.get_phases_power()             

        if self.loop_count % 10 == 0:
            _LOGGER.info(f"[loadbalancer] eletrical state: power={power_phases}W")
        self.loop_count += 1

        next_delta_min = self.activate_if(power_phases)
        if next_delta_min > 0:
            self.next_run = now + timedelta(minutes=next_delta_min)
            return

        next_delta_min = self.update(power_phases)
        if next_delta_min > 0:
            self.next_run = now + timedelta(minutes=next_delta_min)
            return
