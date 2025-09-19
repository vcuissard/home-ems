from .power_info import PowerInfo
from ..utils import *

class Enphase(PowerInfo):

    def __init__(self, hass, entity):
        super().__init__(hass, entity)
        self.last_power = 0.0

    def logger_name(self):
        return "[enphase]"

    def get_power(self):
        ret = 0.0
        try:
            ret = float(self.get_state('sensor', 'balanced_net_power_consumption')) * 1000.0
        except ValueError:
            ret = self.last_power
        self.last_power = ret
        return ret
