import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .const import *


_LOGGER = logging.getLogger(__name__)

def loadbalancer_instance(hass):
    return hass.data[DOMAIN]["load_balancer"]

def get_phase(phases):
    if phases & 0x1:
        return 0
    if phases & 0x2:
        return 1
    if phases & 0x4:
        return 2
    return 0

def get_entity_id_from_unique_id(hass, domain: str, unique_id: str) -> str | None:
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get_entity_id(domain, DOMAIN, unique_id)
    return entry
    
def get_local_switch(hass, name):
    entity_id = get_entity_id_from_unique_id(hass, "switch", f"{CONF_ENTITY_ID}_{name}")
    value = hass.states.get(entity_id)
    if value is not None:
        return value.state == "on"
    return False

def get_local_select(hass, name):
    entity_id = get_entity_id_from_unique_id(hass, "select", f"{CONF_ENTITY_ID}_{name}")
    value = hass.states.get(entity_id)
    if value is not None:
        return value.state
    else:
        return "Unavailable"

def call_async(hass, kind, method, data):
    hass.async_create_task(
        hass.services.async_call(
            kind,
            method,
            data,
            blocking=True
        )
    )

def set_local_switch(hass, name, value):
    entity_id = get_entity_id_from_unique_id(hass, "switch", f"{CONF_ENTITY_ID}_{name}")
    call_async(
        hass,
        "switch",
        f"turn_{'on' if value else 'off'}",
        { "entity_id": entity_id }
    )

def config_dev(hass):
    return get_local_switch(hass, "dev")

def config_evcharger_is_tri(hass):
    return get_local_switch(hass, "ev_tri")

def config_evcharger_set_tri(hass, value):
    return set_local_switch(hass, "ev_tri", value)

def config_evcharger_hc(hass):
    return get_local_switch(hass, "ev_hc")

def config_evcharger_set_hc(hass, value):
    set_local_switch(hass, "ev_hc", value)

def config_evcharger_requested(hass):
    return get_local_switch(hass, "ev_request")

def config_evcharger_set_requested(hass, value):
    return set_local_switch(hass, "ev_request", value)

def config_evcharger_forced(hass):
    return get_local_switch(hass, "ev_force")

def config_evcharger_set_forced(hass, value):
    set_local_switch(hass, "ev_force", value)

def config_cro_hc(hass):
    return get_local_switch(hass, "cro_hc")

def config_cro_set_hc(hass, value):
    set_local_switch(hass, "cro_hc", value)

def config_cro_requested(hass):
    return get_local_switch(hass, "cro_request")

def config_cro_set_requested(hass, value):
    return set_local_switch(hass, "cro_request", value)

def config_cro_forced(hass):
    return get_local_switch(hass, "cro_force")

def config_cro_set_forced(hass, value):
    set_local_switch(hass, "cro_force", value)

def config_loadbalancer_enabled(hass):
    return get_local_switch(hass, 'loadbalancer')

def config_loadbalancer_mode(hass):
    return get_local_select(hass, 'mode')

def config_loadbalancer_mode_is_hc_hp(hass):
    return config_loadbalancer_mode(hass) == "HC/HP"

def config_water_heater_boost(hass):
    return get_local_switch(hass, "water_heater_boost")

def config_water_heater_set_boost(hass, value):
    return set_local_switch(hass, "water_heater_boost", value)

def config_water_heater_forced(hass):
    return get_local_switch(hass, "water_heater_force")

def config_water_heater_set_forced(hass, value):
    set_local_switch(hass, "water_heater_force", value)

