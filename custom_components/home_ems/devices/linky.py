from .device import Device

class Linky(Device):

    def __init__(self, hass, entity):
        super().__init__(hass, 0)
        self.entity = entity

    def get_phases_current(self):
        pass

    def get_phases_current_import(self):
        return [ 
            float(self.get_state('sensor', 'sinst1')),
            float(self.get_state('sensor', 'sinst2')),
            float(self.get_state('sensor', 'sinst3'))
        ]

    def get_phases_current_export(self):
        return [
            float(self.get_state('sensor', 'iinst1')),
            float(self.get_state('sensor', 'iinst2')),
            float(self.get_state('sensor', 'iinst3'))
        ]

    def is_hc(self):
        return int(self.get_state('sensor', 'ntarf')) == 1
