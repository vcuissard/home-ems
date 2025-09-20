from datetime import datetime, timedelta
from .device import Device
from ..utils import *

class EVCharger(Device):

    def __init__(self, hass, entity, phases):
        super().__init__(hass, phases)
        self.entity = entity
        self.phases = phases
        self.max_power = 0
        self.min_power = CONF_EV_CHARGER_MIN_POWER
        self.can_auto_request = True
        # Wait at least 10min after activation before deactivating it
        self.delay_min_after_activation = 10
        # Wait at least 10min after deactivation before activating it
        self.delay_min_after_deactivation = 10
        self.last_connector_status = ""
        self.activate_first = False
        self.suspend_ev_stop_timer = None

    def logger_name(self):
        return "[evcharger]"

    def late_init(self):
        super().late_init()
        self.stop_transaction()
        self.update_max_power()
        config_evcharger_set_tri(self.hass, True)

    #
    # Charger management
    #

    def connector_status(self):
        return self.hass.states.get(f"sensor.{self.entity}_status_connector").state

    def cable_plugged(self):
        return self.connector_status() != "Available"

    def start_transaction(self):
        if self.connector_status() != "Preparing" and self.connector_status() != "Finishing":
            self.info(f"no need to start transation in state {self.connector_status()}")
            return
        domain = "switch" if not config_dev(self.hass) == True else "input_boolean"
        call_async(
            self.hass,
            domain,
            "turn_on",
            { "entity_id": f"{domain}.{self.entity}_charge_control" }
        )

    def stop_transaction(self):
        domain = "switch" if not config_dev(self.hass) == True else "input_boolean"
        call_async(
            self.hass,
            domain,
            "turn_off",
            { "entity_id": f"{domain}.{self.entity}_charge_control" }
        )

    def update_max_power(self):
        limit = self.max_power
        if not config_evcharger_is_tri(self.hass):
            limit *= 3
        self.info(f"update_max_power {limit}W")
        if not config_dev(self.hass):
            # Prepare the data for the OCPP set_charge_rate service
            charging_profile = {
                "chargingProfileId": 8,
                "stackLevel": 200,
                "chargingProfileKind": "Relative",
                "chargingProfilePurpose": "TxDefaultProfile",
                "chargingSchedule": {
                    "chargingRateUnit": "W",
                    "chargingSchedulePeriod": [
                        {
                            "startPeriod": 0,
                            "limit": limit
                        }
                    ]
                }
            }
            # Log the data being sent
            self.debug(f"sending set_charge_rate with data: {charging_profile}")
            # Call the OCPP set_charge_rate service
            call_async(self.hass, "ocpp", "set_charge_rate",
                {
                    "custom_profile": charging_profile
                }
            )
        else:
            call_async(
                self.hass,
                "input_number",
                "set_value",
                {
                    "entity_id": f"input_number.{self.entity}_maximum_power",
                    "value": limit,
                }
            )

    def set_max_power(self, max_power):
        if max_power == 0:
            self.info(f"max below min power => suspend")
        if self.max_power != max_power:
            self.max_power = max_power
            self.update_max_power()
        else:
            self.max_power = max_power

    def compute_max_available_power(self, power_max, power):

        # if is_forced
        if self.is_forced():
            return CONF_MAX_POWER_PER_PHASE

        # HP/HC: disable if HP
        if self.is_hc_hp:
            if loadbalancer_instance(self.hass).linky.is_hc():
                return CONF_MAX_POWER_PER_PHASE
            else:
                return 0

        # Force HC in solar mode
        if config_evcharger_hc(self.hass) and loadbalancer_instance(self.hass).linky.is_hc():
            return CONF_MAX_POWER_PER_PHASE

        #
        # Check power import / export and max
        #

        new_power = power_max - power

        #
        # Here we check for update which means we need to include current power
        # and check if we import energy from grids
        #
        if power > 0:
            # So we import from grid, let's reduce current offered power
            if self.get_max_power() != 0:
                self.debug(f"importing {power}W -> may need to reduce offered power")

        if new_power < self.get_min_power():
            if self.get_max_power() != 0:
                # Need to check the 5min power to not stop the charge due to a short
                # import. If this is the case let's reduce to min power
                power_5min = loadbalancer_instance(self.hass).enphase.get_power_5min()
                if power_max - power_5min < self.get_min_power():
                    self.info("new power based on 5min stat is too low => suspend charge")
                    new_power = 0
                else:
                    new_power = CONF_EV_CHARGER_MIN_POWER
            else:
                new_power = 0
            return min(new_power, CONF_MAX_POWER_PER_PHASE)

        # We do not want to update if delta is too small to avoid
        # bouncing
        delta = abs(power_max - new_power)
        if delta <= CONF_EV_CHARGER_MIN_DELTA:
            if power_max > 0:
                self.debug(f"delta({delta}W) current({power_max}W) avail({power}W) is too small => do not react")
            return power_max


        return min(new_power, CONF_MAX_POWER_PER_PHASE)

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
        self.can_auto_request = False
        self.activate_first = True
        self.start_transaction()

    def deactivate(self):
        super().deactivate()
        config_evcharger_set_forced(self.hass, False)
        config_evcharger_set_tri(self.hass, True)
        config_evcharger_set_hc(self.hass, False)
        config_evcharger_set_requested(self.hass, False)
        self.stop_transaction()
        self.max_power = 0
        self.update_max_power()
        self.activate_first = False
        self.suspend_ev_stop_timer = None

    def still_needed(self):
        status = self.connector_status()
        if status != self.last_connector_status:
            self.last_connector_status = status
        if status == "SuspendedEV":
            if self.suspend_ev_stop_timer == None:
                self.info("car stopped the charge, most likely full")
                self.suspend_ev_stop_timer = datetime.now() + timedelta(minutes=30)
            elif datetime.now() >= self.suspend_ev_stop_timer:
                self.info("car stopped the charge 30min ago, most likely full (deactivate)")
                self.no_delay = True
                return False
        else:
            self.suspend_ev_stop_timer = None
        if status == "Faulted":
            self.info("fault, need to reset")
            self.no_delay = True            
            # TODO
            return False
        if not self.cable_plugged():
            self.info("cable disconnected")
            self.can_auto_request = True
            self.no_delay = True
            return False
        if self.is_forced():
            return True
        return config_evcharger_requested(self.hass)

    def should_activate(self):
        return self.can_activate() and config_evcharger_requested(self.hass) and self.cable_plugged()

    def is_forced(self):
        return config_evcharger_forced(self.hass) and self.cable_plugged()

    #
    # Interface with LoadBalancer
    #

    def activate_if(self, power):
        # First, check if cable is unplugged, means we can auto request next one
        if not self.cable_plugged() and not self.can_auto_request:
            self.can_auto_request = True
        if not self.cable_plugged() and config_evcharger_requested(self.hass):
            config_evcharger_set_requested(self.hass, False)
        # First, check if we need to force the request
        # This is needed to avoid the need of clicking the button
        if self.cable_plugged() and not config_evcharger_requested(self.hass) and (self.connector_status() == "Preparing" or self.connector_status() == "SuspendedEVSE") and self.can_auto_request:
            self.info("cable connected, automatically request charge")
            config_evcharger_set_requested(self.hass, True)
        if not self.should_activate():
            return 0
        if self.is_forced():
            self.set_max_power(CONF_MAX_POWER_PER_PHASE)
            self.activate()
            self.info(f"start charging (forced) @ {CONF_MAX_POWER_PER_PHASE}W")
            return CONF_EV_CHARGER_WAITING_TIME
        else:
            self.set_max_power(self.compute_max_available_power(0, power))
            self.info(f"start charging @ {self.max_power}W")
            self.activate()
            return CONF_EV_CHARGER_WAITING_TIME
        return 0

    def update(self, power):
        if not self.still_needed() and self.can_deactivate():
            self.info(f"no longer needed, deactivate")
            self.deactivate()
            return CONF_EV_CHARGER_WAITING_TIME

        # Ensure power was sent
        if self.activate_first and self.get_max_power() != 0:
            self.info(f"charger is in {self.connector_status()} state after activation => set power")
            self.update_max_power()
            self.activate_first = False
            return CONF_EV_CHARGER_WAITING_TIME

        # Need to check if we have enough
        new_power = self.compute_max_available_power(self.get_max_power(), power)
        if new_power != self.get_max_power():
            self.set_max_power(new_power)
            return CONF_EV_CHARGER_WAITING_TIME

        return 0
