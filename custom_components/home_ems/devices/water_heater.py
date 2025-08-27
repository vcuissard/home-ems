from datetime import datetime, timedelta
from .device import Device
from ..utils import *

class WaterHeater(Device):

    def __init__(self, hass, entity, phases):
        super().__init__(hass, phases)
        self.entity = entity
        self.phases = phases
        self.min_power = CONF_WATER_HEATER_MIN_POWER
        self.max_power = CONF_WATER_HEATER_MAX_POWER
        self.force_pv = None
        self.needed_temperature = 0
        self.boost = 0
        self.suspended = False
        # Wait at least 10min after activation before deactivating it
        self.delay_min_after_activation = 10
        # Wait at least 10min after deactivation before activating it
        self.delay_min_after_deactivation = 10
        self.next_force_pv = datetime.now()

    def logger_name(self):
        return "[water heater]"

    def late_init(self):
        super().late_init()
        self.set_force_pv(False)

    #
    # WaterHeater info
    #

    def get_water_temperature(self):
        return float(self.get_state("sensor", "middle_water_temperature"))

    def set_wanted_temperature(self, value):
        if not config_dev(self.hass) == True:
            domain = "water_heater"
            action = "set_temperature"
            key = "temperature"
        else:
            domain = "input_number"
            action = "set_value"
            key = "value"
        call_async(
            self.hass,
            domain,
            action,
            {
                "entity_id": f"{domain}.{self.entity}",
                key: self.needed_temperature
            })
    
    def set_boost(self, value):
        if self.boost != value:
            self.info(f"set boost {value}")
            self.boost = value
            domain = "number" if not config_dev(self.hass) == True else "input_number"
            action = "set_value"
            key = "value"
            call_async(
                self.hass,
                domain,
                action,
                {
                    "entity_id": f"{domain}.{self.entity}_boost_mode_duration",
                    key: value
                })
        
    def time_to_reach(self, value):
        # 10deg = 100min
        # 1deg = 10min
        need = value - self.get_water_temperature()
        if need < 0:
            return 0
        return need * 10

    #
    #
    #

    def compute_needed_temp(self):
        now = datetime.now()
        #
        # Compute at what time water should be OK if we start now
        #
        ready = now + timedelta(minutes=self.time_to_reach(CONF_WATER_HEATER_MAX_TEMP))

        if self.boost:
            # If Boost ? => max
            return CONF_WATER_HEATER_MAX_TEMP            

        if self.is_hc_hp:
            #
            # In HC/HP, we wait for HC signal and we compute when water will be
            # at the right temperature if we start now. If this is after 7am (end of HC)
            # then we start now.
            #
            if loadbalancer_instance(self.hass).linky.is_hc():
                if now.hour >= 0 and now.hour < 8:                
                    if ready.hour > 7:
                        self.info(f"now it is time to boil water because we need {self.time_to_reach(CONF_WATER_HEATER_MAX_TEMP)} min")
                        return CONF_WATER_HEATER_MAX_TEMP
        elif self.get_force_pv():
            # In solar mode, if force pv signal is on then we need max
            return CONF_WATER_HEATER_MAX_TEMP
        
        # In any case if forced => max
        if self.is_forced():
            return CONF_WATER_HEATER_MAX_TEMP

        #
        # Last resort: we need at least 55 @ 18h00
        #
        if self.get_water_temperature() < 55.0 and now.hour > 14 and (ready.hour > 18 or ready.hour < 14):
            if self.get_needed_temperature() != CONF_WATER_HEATER_MAX_TEMP:
                self.info(f"6pm rule: now it is time to boil water because we need {self.time_to_reach(CONF_WATER_HEATER_MAX_TEMP)} min")
            return CONF_WATER_HEATER_MAX_TEMP
            
        return CONF_WATER_HEATER_MIN_TEMP

    def get_needed_temperature(self):
        return self.needed_temperature
    
    def set_needed_temperature(self, needed_temperature):
        if needed_temperature != self.needed_temperature:
            self.debug(f"set_temp:{needed_temperature}")
            self.needed_temperature = needed_temperature
            self.set_wanted_temperature(self.needed_temperature)

    def get_force_pv(self):
        return self.force_pv

    def set_force_pv(self, force):
        if force != self.force_pv:
            self.force_pv = force
            if force:
                self.next_force_pv = datetime.now() + timedelta(hours=14)
            domain = "switch" if not config_dev(self.hass) == True else "input_boolean"
            call_async(
                self.hass,
                domain,
                f"turn_{'on' if force else 'off'}",
                { "entity_id": f"{domain}.{self.entity}_pv" })

    def can_force_pv(self):
        return datetime.now() > self.next_force_pv

    #
    # Logic
    #

    def still_needed(self):
        # Always ON
        return True

    def activate(self):
        super().activate()
        self.set_needed_temperature(self.compute_needed_temp())
        self.suspended = False


    def deactivate(self):
        super().deactivate()
        self.set_force_pv(False)
        self.set_needed_temperature(CONF_WATER_HEATER_MIN_TEMP)
        config_water_heater_set_forced(self.hass, False)
        self.set_boost(0)
        config_water_heater_set_boost(self.hass, False)
        self.suspended = False

    def should_activate(self):
        # Always ON
        return True

    def is_forced(self):
        return config_water_heater_forced(self.hass)

    #
    # Interface with LoadBalancer
    #

    def activate_if(self, power_phases):
        # Always ON
        if not self.is_active():
            self.activate()
            return CONF_WATER_HEATER_WAITING_TIME
        return 0

    def update(self, power_phases):        
        if not self.suspended and self.get_water_temperature() >= self.needed_temperature:
            self.set_force_pv(False)
            self.set_needed_temperature(CONF_WATER_HEATER_MIN_TEMP)
            config_water_heater_set_forced(self.hass, False)
            self.set_boost(0)
            config_water_heater_set_boost(self.hass, False)
            self.suspended = True
            return CONF_WATER_HEATER_WAITING_TIME

        if not self.is_hc_hp:
            #
            # Solar mode: manage pv signal
            #
            phases = self.get_phases()        
            # Mono only
            power = power_phases[get_phase(phases)]        
            #
            # Check import/export status
            #
            if power > 3000 and self.get_force_pv():
                # If we import too much let's remove the force pv signal
                # This will stop water heater only in 30min (Aeromax 5)
                self.info(f"disable pv - importing to much")
                self.set_force_pv(False)
                return CONF_WATER_HEATER_WAITING_TIME
            elif not self.get_force_pv() and self.can_force_pv() and power < 0 and abs(power) >= self.get_max_power():
                # We have now enough solar production, let's raise PV signal. (once per day)
                self.set_force_pv(True)            
                self.info(f"force pv")
                return CONF_WATER_HEATER_WAITING_TIME

        #
        # Is boost needed?
        #
        if config_water_heater_boost(self.hass) and not self.boost > 0:
            self.set_boost(1)
            config_water_heater_set_forced(self.hass, True)

        #
        # Now we can update needed temperature
        #
        self.set_needed_temperature(self.compute_needed_temp())

        if self.get_water_temperature() < self.needed_temperature:
            self.suspended = False

        return 0