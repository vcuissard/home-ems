from .device import Device
from ..utils import *

class EVCharger(Device):

    def __init__(self, hass, entity, phases):
        super().__init__(hass, phases)
        self.entity = entity
        self.phases = phases
        self.max_current = 0
        self.min_current = CONF_EV_CHARGER_MIN_CURRENT
        self.can_auto_request = True

    def late_init(self):
        super().late_init()
        call_async(self.hass, "ocpp", "clear_profile", { })
        self.stop_transaction()
        self.update_max_current()

    #
    # Charger management
    #

    def connector_status(self):
        return self.hass.states.get(f"sensor.{CONF_EV_CHARGER_ID}_status_connector").state

    def cable_plugged(self):
        return self.hass.states.get(f"switch.{CONF_EV_CHARGER_ID}_availability").state == 'off'

    def start_transaction(self):
        domain = "switch" if CONF_PROD == True else "input_boolean"
        call_async(
            self.hass,
            domain,
            "turn_on",
            { "entity_id": f"{domain}.{CONF_EV_CHARGER_ID}_charge_control" }
        )

    def stop_transaction(self):
        domain = "switch" if CONF_PROD == True else "input_boolean"
        call_async(
            self.hass,
            domain,
            "turn_off",
            { "entity_id": f"{domain}.{CONF_EV_CHARGER_ID}_charge_control" }
        )

    def update_max_current(self):
        self.info(f"[evcharger][update_max_current] {self.max_current}A")
        if False:
            # Prepare the data for the OCPP set_charge_rate service
            charging_profile = {
                "chargingProfileId": 8,
                "stackLevel": 200,
                "chargingProfileKind": "Relative",
                "chargingProfilePurpose": "TxDefaultProfile",
                "chargingSchedule": {
                    "chargingRateUnit": "A",
                    "chargingSchedulePeriod": [
                        {
                            "startPeriod": 0,
                            "limit": self.max_current
                        }
                    ]
                }
            }
            # Log the data being sent
            self.debug(f"[evcharger] sending set_charge_rate with data: {charging_profile}")
            # Call the OCPP set_charge_rate service
            call_async(self.hass, "ocpp", "set_charge_rate",
                {
                    "custom_profile": charging_profile
                }
            )
        else:
            domain = "number" if CONF_PROD == True else "input_number"
            call_async(
                self.hass,
                domain,
                "set_value",
                {
                    "entity_id": f"{domain}.{CONF_EV_CHARGER_ID}_maximum_current",
                    "value": self.max_current,
                }
            )

    def set_max_current(self, max_current):
        if max_current == 0:
            self.info(f"[evcharger] max below min current => suspend")
        if self.max_current != max_current:
            self.max_current = max_current
            self.update_max_current()
        else:
            self.max_current = max_current

    #
    # Logic
    #

    def get_phases(self):
        if config_evcharger_is_tri(self.hass):
            self.phases = 7
        else:
            self.phases = CONF_EV_CHARGER_PHASE_MONO
        return super().get_phases()

    def activate(self):
        super().activate()
        self.info("[evcharger][activate]")
        self.can_auto_request = False
        self.start_transaction()

    def deactivate(self):
        super().deactivate()
        config_evcharger_set_forced(self.hass, False)
        config_evcharger_set_tri(self.hass, False)
        config_evcharger_set_hc(self.hass, False)
        config_evcharger_set_requested(self.hass, False)
        self.stop_transaction()
        self.max_current = 0
        self.update_max_current()

    def still_needed(self):
        status = self.connector_status()
        if status == "SuspendedEV":
            self.info("[evcharger] car stopped the charge, most likely full")
#            self.can_auto_request = False
#            return False
        if status == "Faulted":
            self.info("[evcharger] fault, need to reset")
            # TODO
            return False
        if not self.cable_plugged():
            self.info("[evcharger] cable disconnected")
            self.can_auto_request = True
            return False
        if self.is_forced():
            return True
        if self.is_hc_hp or config_evcharger_hc(self.hass):
            if not loadbalancer_instance(self.hass).linky.is_hc():
                self.info(f"[evcharger] HP => deactivate")
                self.can_auto_request = False
                return False
        return config_evcharger_requested(self.hass)

    def should_activate(self):
        return config_evcharger_requested(self.hass) and self.cable_plugged()

    def is_forced(self):
        return config_evcharger_forced(self.hass) and self.cable_plugged()

    #
    # Interface with LoadBalancer
    #

    def activate_if(self, current_export):
        if not self.is_active():
            # First, check if cable is unplugged, means we can auto request next one
            if not self.cable_plugged() and not self.can_auto_request:
                self.can_auto_request = True
            if not self.cable_plugged() and config_evcharger_requested(self.hass):
                config_evcharger_set_requested(self.hass, False)
            # First, check if we need to force the request
            # This is needed to avoid the need of clicking the button
            if self.cable_plugged() and not config_evcharger_requested(self.hass) and self.connector_status() == "Preparing" and self.can_auto_request:
                self.info("[evcharger] cable connected, automatically request charge")
                config_evcharger_set_requested(self.hass, True)
            if not self.should_activate():
                return False
            if self.is_forced():
                self.set_max_current(CONF_MAX_CURRENT_PER_PHASE)
                self.activate()
                self.info(f"[evchager] start charging (forced) @ {CONF_MAX_CURRENT_PER_PHASE}A")
                return True
            elif self.is_hc_hp or config_evcharger_hc(self.hass):
                # If mode is HP/HC or requested to do HC, force it if HC
                if loadbalancer_instance(self.hass).linky.is_hc():
                    self.info("[evcharger] activate due to HC")
                    self.set_max_current(CONF_MAX_CURRENT_PER_PHASE)
                    self.activate()
                    return True
            else:
                # Need to check if we have enough
                phases = self.get_phases()
                if phases == 0x7:
                    # Tri
                    max_export = min(CONF_MAX_CURRENT_PER_PHASE, 
                                    current_export[0], 
                                    current_export[1], 
                                    current_export[2])
                else:
                    # Mono
                    max_export = min(CONF_MAX_CURRENT_PER_PHASE, current_export[get_phase(phases)])
                if max_export >= self.get_min_current():
                    self.set_max_current(max_export)
                    self.activate()
                    self.info(f"[evcharger] start charging @ {max_export}A")
                    return True
                else:
                    self.info(f"[evcharger] cannot charge because available current is below {self.get_min_current()}A")
        return False

    def update(self, current_export, current_import):
        if not self.still_needed():
            self.info(f"[evcharger] no longer needed, deactivate")
            self.deactivate()
            return True

        # Nothing to be done if HC/HP or is_forced        
        if self.is_hc_hp or config_evcharger_hc(self.hass) or self.is_forced():
            return False

        # Need to check if we have enough
        phases = self.get_phases()
        if phases == 0x7:
            # Tri
            max_export = min(CONF_MAX_CURRENT_PER_PHASE, 
                            current_export[0],
                            current_export[1],
                            current_export[2])
        else:
            # Mono
            max_export = min(CONF_MAX_CURRENT_PER_PHASE, current_export[get_phase(phases)])
        if max_export < self.get_min_current():
            max_export = 0
        if max_export != self.get_max_current():
            self.set_max_current(max_export)
            return True
        return False
