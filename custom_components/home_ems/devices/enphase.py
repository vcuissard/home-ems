from .power_info import PowerInfo
from ..utils import *

class Enphase(PowerInfo):

    def __init__(self, hass, entity):
        super().__init__(hass, entity)

    def logger_name(self):
        return "[enphase]"

    def get_phases_power(self):
        if config_dev(self.hass):
            return [
                float(self.get_state('sensor', 'pinst1')),
                float(self.get_state('sensor', 'pinst2')),
                float(self.get_state('sensor', 'pinst3'))
            ]
        else:
            return super().get_phases_power()
