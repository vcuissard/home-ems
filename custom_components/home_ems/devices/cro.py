from datetime import datetime, timedelta
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
        self.next_auto_activation = datetime.now()

    def logger_name(self):
        return "[cro]"

    def late_init(self):
        super().late_init()
        if config_dev(self.hass):
            self.auto_activation_delta = timedelta(seconds=30)
        else:
            self.auto_activation_delta = timedelta(minutes=30)

    #
    # CRO management
    #

    def cro_get_power(self):
        ret = 0.0
        try:
            ret = float(self.get_state("sensor" if not config_dev(self.hass) else "input_number", "tpl_power"))
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
            { "entity_id": f"{domain}.{self.entity}" }
        )

    def compute_max_available_power(self, power):
        # Allow if HC is set in solar mode and hc in progress
        if config_cro_hc(self.hass) and loadbalancer_instance(self.hass).linky.is_hc():
            return CONF_CRO_POWER
        # Allow if we are below the min delta
        if power > CONF_CRO_MIN_DELTA:
            return 0
        # Disable
        return CONF_CRO_POWER

    #
    # Logic
    #

    def activate(self):
        super().activate()
        self.cro_set_status(True)

    def deactivate(self):
        super().deactivate()
        self.cro_set_status(False)
#        if not self.is_hc_hp:
#            self.next_auto_activation = datetime.now() + self.auto_activation_delta
        self.max_power = 0

    def still_needed(self, power):
        if self.cro_get_power() < 10:
            config_cro_set_requested(self.hass, False)
            config_cro_set_forced(self.hass, False)
            config_cro_set_hc(self.hass, False)
            return False
        if self.is_forced():
            return True
        if self.is_hc_hp:
            if not loadbalancer_instance(self.hass).linky.is_hc():
                self.info(f"HP => deactivate")
                return False
        elif config_cro_hc(self.hass):
            if not loadbalancer_instance(self.hass).linky.is_hc() and power > 0:
                self.info(f"HP => deactivate")
                return False
        return config_cro_requested(self.hass)

    def should_activate(self):
#        if not self.is_hc_hp and datetime.now() > self.next_auto_activation:
#            config_cro_set_requested(self.hass, True)
        return self.can_activate() and config_cro_requested(self.hass)

    def is_forced(self):
        return config_cro_forced(self.hass)

    #
    # Interface with LoadBalancer
    #

    def activate_if(self, power):
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
        
        # Solar management
        if not self.is_hc_hp:
            if power < 0 and abs(power) >= self.get_min_power():
                self.max_power = CONF_CRO_POWER
                self.activate()
                self.info(f"start charging @ {self.max_power}W")
                return CONF_CRO_WAITING_TIME

        return 0

    def update(self, power):
        if not self.still_needed(power) and self.can_deactivate():
            self.info(f"no longer needed, deactivate")
            self.deactivate()
            return CONF_CRO_WAITING_TIME

        # Nothing to be done if HC/HP or is_forced        
        if self.is_hc_hp or self.is_forced():
            return 0

        # Need to check if we have enough
        new_power = self.compute_max_available_power(power)        
        if new_power != CONF_CRO_POWER and self.can_deactivate():
            self.info(f"disable due to missing solar power")
            self.deactivate()
            return CONF_CRO_WAITING_TIME

        return 0
