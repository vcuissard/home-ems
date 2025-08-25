from datetime import datetime, timedelta
from .device import Device
from ..utils import *

class Boiler(Device):

    def __init__(self, hass, entity, entity_resistor, phases):
        super().__init__(hass, phases)
        self.entity = entity
        self.entity_resistor = entity_resistor
        self.phases = phases
        self.min_current = 3
        self.max_current = 5
        self.force_pv = None
        self.needed_temperature = 0
        self.boost = 0
    
    def late_init(self):
        super().late_init()
        self.set_force_pv(False)

    #
    # Boiler info
    #

    def get_water_temperature(self):
        return float(self.get_state("sensor", "middle_water_temperature"))

    def set_wanted_temperature(self, value):
        if CONF_PROD == True:
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
                "entity_id": f"{domain}.{CONF_BOILER_ID}",
                key: self.needed_temperature
            })
    
    def set_boost(self, value):
        if self.boost != value:
            self.info(f"[boiler] set boost {value}")
            self.boost = value
            domain = "number" if CONF_PROD == True else "input_number"
            action = "set_value"
            key = "value"
            call_async(
                self.hass,
                domain,
                action,
                {
                    "entity_id": f"{domain}.{CONF_BOILER_ID}_boost_mode_duration",
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
        # Compute at what time water should be OK if we start now
        ready = now + timedelta(minutes=self.time_to_reach(CONF_BOILER_MAX_TEMP))
        # Boost ? => max
        if self.boost:
            return CONF_BOILER_MAX_TEMP
        if self.is_hc_hp:
            #
            # In HC/HP, we wait for HC signal and we compute when water will be
            # at the right temperature if we start now. If this is after 7am (end of HC)
            # then we start now.
            #
            if loadbalancer_instance(self.hass).linky.is_hc():
                if now.hour >= 0 and now.hour < 8:                
                    if ready.hour > 7:
                        self.info(f"[boiler] now it is time to boil water because we need {self.time_to_reach(CONF_BOILER_MAX_TEMP)} min")
                        return CONF_BOILER_MAX_TEMP
        elif self.get_force_pv():
            # In solar mode, if force pv signal is on then we need max
            return CONF_BOILER_MAX_TEMP
        
        # In any case if forced => max
        if self.is_forced():
            return CONF_BOILER_MAX_TEMP

        #
        # Last resort: we need at least 55 @ 18h00
        #
        if self.get_water_temperature() < 55.0 and now.hour > 14 and ready.hour > 18:
            self.info(f"[boiler] 6pm rule: now it is time to boil water because we need {self.time_to_reach(CONF_BOILER_MAX_TEMP)} min")
            return CONF_BOILER_MAX_TEMP
            
        return CONF_BOILER_MIN_TEMP

    def get_needed_temperature(self):
        return self.needed_temperature
    
    def set_needed_temperature(self, needed_temperature):
        if needed_temperature != self.needed_temperature:
            self.debug(f"[boiler] set_temp:{needed_temperature}")
            self.needed_temperature = needed_temperature
            self.set_wanted_temperature(self.needed_temperature)

    def get_force_pv(self):
        return self.force_pv

    def set_force_pv(self, force):
        if force != self.force_pv:
            self.force_pv = force
            domain = "switch" if CONF_PROD == True else "input_boolean"
            call_async(
                self.hass,
                domain,
                f"turn_{'on' if force else 'off'}",
                { "entity_id": f"{domain}.{CONF_BOILER_ID}_pv" })

    #
    # Logic
    #

    def still_needed(self):
        return self.get_water_temperature() < self.needed_temperature

    def activate(self):
        super().activate()
        self.set_needed_temperature(self.compute_needed_temp())

    def deactivate(self):
        super().deactivate()
        self.set_force_pv(False)
        self.set_needed_temperature(CONF_BOILER_MIN_TEMP)
        config_boiler_set_forced(self.hass, False)
        self.set_boost(0)
        config_boiler_set_boost(self.hass, False)

    def should_activate(self):
        temp = self.get_water_temperature()
        needed_temp = self.compute_needed_temp()
        if temp < needed_temp:
            return True
        return False

    def is_forced(self):
        return config_boiler_forced(self.hass)

    #
    # Interface with LoadBalancer
    #

    def activate_if(self, current_export):
        if config_boiler_boost(self.hass) and not self.boost > 0:
            self.set_boost(1)
            config_boiler_set_forced(self.hass, True)
        if not self.is_active() and (self.should_activate() or self.is_forced()):
            if self.is_forced():
                self.activate()
                self.info("[boiler] start (forced)")
                return True
            elif self.is_hc_hp and loadbalancer_instance(self.hass).linky.is_hc():
                self.activate()
                self.info(f"[boiler] start (HC)")
            elif not self.is_hc_hp:
                # Need to check if we have enough
                phases = self.get_phases()
                # Mono only
                max_export = current_export[get_phase(phases)]
                if max_export >= self.get_min_current():
                    self.activate()
                    self.info(f"[boiler] start (available: {max_export}A)")
                    return True
        return False

    def update(self, current_export, current_import):
        # Update needed temp
        self.set_needed_temperature(self.compute_needed_temp())

        if config_boiler_boost(self.hass) and not self.boost > 0:
            self.set_boost(1)
            config_boiler_set_forced(self.hass, True)

        # Still needed?
        if not self.still_needed():
            self.info(f"[boiler] no longer needed, deactivate")
            self.deactivate()
            return True            

        # Nothing more in HC/HP mode or if mode is forced
        if self.is_hc_hp or self.is_forced():
            return False

        #
        # Trigger PV only when we export enough power
        #
        
        phases = self.get_phases()
        
        # Mono only
        max_export = current_export[get_phase(phases)]
        
        # Check that we do not import to much        
        actual_import = current_import[get_phase(phases)]
        if actual_import > 6 and self.get_force_pv():
            self.info(f"[boiler] disable pv - importing to much")
            self.set_force_pv(False)
            return True
        elif actual_import < 6 and max_export >= self.get_max_current() and not self.get_force_pv():
            self.set_force_pv(True)            
            self.info(f"[boiler] force pv")
            return True

        return False