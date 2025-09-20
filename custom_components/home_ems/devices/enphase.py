from .power_info import PowerInfo
from ..utils import *

class Enphase(PowerInfo):

    def __init__(self, hass, entity):
        super().__init__(hass, entity)
        self.last_power = 0.0
        self.last_power_5min = 0.0

    def logger_name(self):
        return "[enphase]"

    def get_power(self):
        ret = 0.0
        try:
            ret = float(self.get_state('sensor', 'power_net_1min'))
        except ValueError:
            ret = self.last_power
        self.last_power = ret
        return ret

    def get_power_5min(self):
        ret = 0.0
        try:
            ret = float(self.get_state('sensor', 'power_net_5min'))
        except ValueError:
            ret = self.last_power_5min
        self.last_power_5min = ret
        return ret
