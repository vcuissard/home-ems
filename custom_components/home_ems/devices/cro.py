from .device import Device
from ..utils import *

class CRO(Device):

    def __init__(self, hass, entity, phases):
        super().__init__(hass, phases)
        self.entity = entity
        self.phases = phases
        self.max_power = 0
        self.min_power = CONF_CRO_POWER
        self.can_auto_request = True
        # Wait at least 10min after activation before deactivating it
        self.delay_min_after_activation = 10
        # Wait at least 10min after deactivation before activating it
        self.delay_min_after_deactivation = 10
        self.last_cro_power = 0.0

    def logger_name(self):
        return "[cro]"

    #
    # CRO management
    #

    def cro_get_power(self):
        ret = 0.0
        try:
            ret = float(self.get_state("number" if not config_dev(self.hass) else "input_number", "power"))
        except ValueError:
            ret = self.last_cro_power
        self.last_cro_power = ret
        return ret

    def cro_set_status(self, status):
        domain = "switch" if not config_dev(self.hass) == True else "input_boolean"
        call_async(
            self.hass,
            domain,
            f"turn_{'on' if status else 'off'}",
            { "entity_id": f"{domain}.{self.entity}_charge_control" }
        )

    def compute_max_available_power(self, power_phases):

        # Max if HC/HP or is_forced        
        if self.is_hc_hp or config_cro_hc(self.hass) or self.is_forced():
            return CONF_CRO_POWER

        #
        # Check current import / export and max
        #

        # Mono
        power = power_phases[get_phase(self.phases)]

        #
        # Compute max avail current
        #

        #
        # Here we check for update which means we need to include current power
        # and check if we import energy from grids
        #
        if power < 0 and abs(power) >= CONF_CRO_POWER:
            return CONF_CRO_POWER
        elif self.is_active() and (abs(power) <= CONF_CRO_MIN_DELTA):
            return CONF_CRO_POWER
        else:
            return 0

    #
    # Logic
    #

    def activate(self):
        super().activate()
        self.cro_set_status(True)

    def deactivate(self):
        super().deactivate()
        self.cro_set_status(False)
        config_cro_set_forced(self.hass, False)
        config_cro_set_hc(self.hass, False)
        self.max_power = 0

    def still_needed(self):
        if self.cro_get_power() <= 0:
            return False
        if self.is_forced():
            return True
        if self.is_hc_hp or config_cro_hc(self.hass):
            if not loadbalancer_instance(self.hass).linky.is_hc():
                self.info(f"HP => deactivate")
                return False
        return config_cro_requested(self.hass)

    def should_activate(self):
        return self.can_activate() and config_cro_requested(self.hass)

    def is_forced(self):
        return config_cro_forced(self.hass)

    #
    # Interface with LoadBalancer
    #

    def activate_if(self, power_phases):
        if not config_dev(self.hass):
            # Not prod ready
            return False
        if not self.should_activate():
            return 0
        if self.is_forced():
            self.max_power = CONF_CRO_POWER
            self.activate()
            self.info(f"start charging (forced) @ {CONF_CRO_POWER}W")
            return CONF_CRO_WAITING_TIME
        elif self.is_hc_hp or config_cro_hc(self.hass):
            # If mode is HP/HC or requested to do HC, force it if HC
            if loadbalancer_instance(self.hass).linky.is_hc():
                self.info("activate due to HC")
                self.max_power = CONF_CRO_POWER
                self.activate()
                return CONF_CRO_WAITING_TIME
        else:
            power = self.compute_max_available_power(power_phases)
            if power >= self.get_min_power():
                self.max_power = power
                self.activate()
                self.info(f"start charging @ {power}W")
                return CONF_CRO_WAITING_TIME
            else:
                self.info(f"cannot charge because available current is below {self.get_min_power()}W")
        return 0

    def update(self, power_phases):
        if not self.still_needed() and self.can_deactivate():
            self.info(f"no longer needed, deactivate")
            self.deactivate()
            config_cro_set_requested(self.hass, False)
            return CONF_CRO_WAITING_TIME

        # Nothing to be done if HC/HP or is_forced        
        if self.is_hc_hp or config_cro_hc(self.hass) or self.is_forced():
            return 0

        # Need to check if we have enough
        new_power = self.compute_max_available_power(power_phases)        
        if new_power != CONF_CRO_POWER and self.can_deactivate():
            self.info(f"disable due to missing solar power")
            self.deactivate()
            return CONF_CRO_WAITING_TIME

        return 0
