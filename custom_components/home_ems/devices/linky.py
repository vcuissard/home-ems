from .power_info import PowerInfo

class Linky(PowerInfo):

    def __init__(self, hass, entity):
        super().__init__(hass, entity)
        self.last_ntarf = 2

    def logger_name(self):
        return "[linky]"

    def is_hc(self):
        ntarf = 2
        try:
            ntarf = int(self.get_state('sensor', 'ntarf'))
            self.last_ntarf = ntarf
        except ValueError:
            ntarf = self.last_ntarf
        return ntarf == 1
