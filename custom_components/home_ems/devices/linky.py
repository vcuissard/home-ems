from .power_info import PowerInfo

class Linky(PowerInfo):

    def __init__(self, hass, entity):
        super().__init__(hass, entity)

    def logger_name(self):
        return "[linky]"

    def is_hc(self):
        return int(self.get_state('sensor', 'ntarf')) == 1
