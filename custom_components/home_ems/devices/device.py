import logging
from datetime import datetime, timedelta
from ..utils import *

class Device:

    def __init__(self, hass, phases):
        self.hass = hass
        self.active = False
        self.max_power = 0
        self.min_power = 0
        self.phases = phases
        self.logger = logging.getLogger(__name__)
        self.next_possible_activation = datetime.now()
        self.next_possible_deactivation = datetime.now()
        self.delay_min_after_activation = 0
        self.delay_min_after_deactivation = 0
        self.no_delay = False

    def late_init(self):
        self.is_hc_hp = config_loadbalancer_mode_is_hc_hp(self.hass)

    def logger_name(self):
        return "[device]"

    def debug(self, info):
        self.logger.debug(self.logger_name() + " " + info)

    def info(self, info):
        self.logger.info(self.logger_name() + " " + info)

    def get_state(self, domain, field):
        return self.hass.states.get(f"{domain}.{self.entity}_{field}").state

    def get_phases(self):
        return self.phases

    def get_max_power(self):
        return self.max_power
            
    def get_min_power(self):
        return self.min_power

    def activate(self):
        self.active = True
        self.info("activate")
        self.next_possible_deactivation = datetime.now() + timedelta(minutes=self.delay_min_after_activation)

    def deactivate(self):
        self.active = False
        self.info("deactivate")
        if self.no_delay:
            self.next_possible_activation = datetime.now()
            self.next_possible_deactivation = datetime.now()
            self.no_delay = False
        else:
            self.next_possible_activation = datetime.now() + timedelta(minutes=self.delay_min_after_deactivation)

    def should_activate(self):
        pass

    def can_activate(self):
        if self.active:
            # Already active
            return False
        if not self.is_forced() and datetime.now() < self.next_possible_activation:
            # Not allowed - need to wait a minimum amount of time before reactivation
            if config_dev(self.hass):
                self.debug("to early to activate")
                self.next_possible_activation = datetime.now()
            return False
        return True

    def can_deactivate(self):
        if not self.active:
            # Already inactive
            return False
        if datetime.now() < self.next_possible_deactivation:
            # Not allowed - need to wait a minimum amount of time before deactivation
            if config_dev(self.hass):
                self.debug("to early to deactivate")
                self.next_possible_deactivation = datetime.now()
            return False
        return True

    def is_forced(self):
        return False

    def is_active(self):
        return self.active
    
    def still_needed(self):
        pass