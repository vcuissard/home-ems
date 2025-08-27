from datetime import datetime
from .device import Device
from ..utils import *

class PoolHeater(Device):

    def __init__(self, hass, phases):
        super().__init__(hass, phases)
        self.target_temperature = 29.5        
        # Wait at least 30min after activation before deactivating it
        self.delay_min_after_activation = 30
        # Wait at least 30min after deactivation before activating it
        self.delay_min_after_deactivation = 30

    def logger_name(self):
        return "[pool heater]"

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
        return self.can_activate() and temp < self.min_temperature()

    def activate_if(self, power_phases):
        if self.should_activate():
            # Need to check if we have enough
            phases = self.get_phases()
            # Mono only
            power = power_phases[get_phase(phases)]
            if power < 0 and abs(power) >= self.get_min_power():
                self.activate()
                self.info(f"start (available: {abs(power)}W)")
                return CONF_POOL_HEATER_WAITING_TIME
            now = datetime.now()
            if now.hour >= 12 and now.hour <= 15:
                self.activate()
                self.info(f"force start")
                return CONF_POOL_HEATER_WAITING_TIME
        return 0

    def update(self, power_phases):
        if self.pool_water_temperature() >= self.min_temperature():
            self.count_above += 1
        else:
            self.count_above = 0
        
        if self.count_above > 60 and self.can_deactivate():
            self.info(f"no longer needed")
            self.deactivate()
            return CONF_POOL_HEATER_WAITING_TIME

        # TODO check how to check power

        return 0
