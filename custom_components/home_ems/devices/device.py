import logging
from ..utils import *

class Device:

    def __init__(self, hass, phases):
        self.hass = hass
        self.active = False
        self.max_current = 0
        self.min_current = 0
        self.priority = 99
        self.phases = phases
        self.logger = logging.getLogger(__name__)

    def late_init(self):
        self.is_hc_hp = config_loadbalancer_mode_is_hc_hp(self.hass)

    def debug(self, info):
        self.logger.debug(info)

    def info(self, info):
        self.logger.info(info)

    def get_state(self, domain, field):
        return self.hass.states.get(f"{domain}.{self.entity}_{field}").state

    def get_phases(self):
        return self.phases

    def get_priority(self):
        return self.priority;

    def set_priority(self, priority):
        self.priority = priority
    
    def get_max_current(self):
        return self.max_current
            
    def get_min_current(self):
        return self.min_current

    def activate(self):
        self.active = True

    def deactivate(self):
        self.active = False

    def should_activate(self):
        pass

    def is_forced(self):
        pass

    def is_active(self):
        return self.active
    
    def still_needed(self):
        pass