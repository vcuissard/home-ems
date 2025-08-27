from .device import Device

class PowerInfo(Device):

    def __init__(self, hass, entity):
        super().__init__(hass, 0)
        self.entity = entity

    def logger_name(self):
        return "[power info]"

    def get_phases_power(self):
        return [ 0.0, 0.0, 0.0 ]
