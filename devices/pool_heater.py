from datetime import datetime
from .device import Device
from ..utils import *

class PoolHeater(Device):

    def __init__(self, hass, phases):
        super().__init__(hass, phases)
        self.target_temperature = 29.5        

    #
    # Pool info
    #

    def pool_water_temperature(self):
        return float(self.hass.states.get(f"sensor.{CONF_POOL_ID}_temp_water").state)

    def min_temperature(self):
        now = datetime.now()
        if now.hour > 20 and now.hour < 9:
            return 27
        return 29

    #
    # Loadbalancer API
    #

    def activate(self):
        super().activate()
        self.count_above = 0

    def deactivate(self):
        return super().deactivate()

    def should_activate(self):
        temp = self.pool_water_temperature()
        return temp < self.min_temperature()

    def activate_if(self, current_export):
        if not self.is_active() and self.should_activate():
            # Need to check if we have enough
            phases = self.get_phases()
            # Mono only
            max_export = current_export[get_phase(phases)]
            if max_export >= self.get_min_current():
                self.activate()
                self.info(f"[pool heater] start (available: {max_export}A)")
                return True
            now = datetime.now()
            if now.hour >= 12 and now.hour <= 15:
                self.activate()
                self.info(f"[pool heater] force start")
                return True
        return False

    def update(self, current_export, current_import):
        if self.pool_water_temperature() >= self.min_temperature():
            self.count_above += 1
        else:
            self.count_above = 0
        
        if self.count_above > 60:
            self.info(f"[pool heater] no longer needed")
            self.deactivate()
            return True

        return False
