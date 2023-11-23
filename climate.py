"""Platform for Roth Touchline heat pump controller."""
import logging
import linecache as lc

from typing import List

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature
)
from homeassistant.components.climate.const import (
    PRESET_ECO,
    PRESET_COMFORT,
    PRESET_AWAY,
    PRESET_NONE,
    HVACMode
)
from homeassistant.const import (
    TEMP_CELSIUS,
    CONF_NAME,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_START,
    STATE_UNKNOWN
)
from homeassistant.core import callback

#import homeassistant.components.light as light
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change

from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "GPIO Fil Pilote"

CONF_GPIOX = "gpiox"
CONF_GPIOY = "gpioy"
#CONF_SENSOR = "sensor"
#CONF_ADDITIONAL_MODES = "additional_modes"

#PRESET_COMFORT_1 = "comfort-1"
#PRESET_COMFORT_2 = "comfort-2"

ROOTFS = "/sys/class/gpio/"

VALUE_OFF = [0,1]
VALUE_FROST = [1,0]
VALUE_ECO = [0,0]
#VALUE_COMFORT_2 = 40
#VALUE_COMFORT_1 = 50
VALUE_COMFORT = [1,1]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_GPIOX): cv.string,
        vol.Required(CONF_GPIOY): cv.string,
        #vol.Required(CONF_HEATER): cv.entity_id,
        #vol.Optional(CONF_SENSOR): cv.entity_id,
        #vol.Optional(CONF_ADDITIONAL_MODES, default=False): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the wire pilot climate platform."""
    unique_id = config.get(CONF_UNIQUE_ID)
    name = config.get(CONF_NAME)
    gpiox_id = config.get(CONF_GPIOX)
    gpioy_id = config.get(CONF_GPIOY)
    #sensor_entity_id = config.get(CONF_SENSOR)
    #additional_modes = config.get(CONF_ADDITIONAL_MODES)

    async_add_entities(
        [GPIOWirePilotClimate(
            unique_id, name, gpiox_id, gpioy_id)]
    )


class GPIOWirePilotClimate(ClimateEntity, RestoreEntity):
    """Representation of a GPIO Wire Pilot device."""

    def __init__(self, unique_id, name, gpiox_id, gpioy_id):
        """Initialize the climate device."""

        self.gpiox_id = gpiox_id
        self.gpioy_id = gpioy_id
 
        self._attr_unique_id = unique_id if unique_id else "gpio_wire_pilot_" + gpiox_id + "-" + gpioy_id
        self._attr_name = name

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        async_track_state_change(
            self.hass, self.gpiox_id, self.gpioy_id, self._async_heater_changed
        )

        @callback
        def _async_startup(event):
            """Init on startup."""
            self.async_schedule_update_ha_state()

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, _async_startup)

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return ClimateEntityFeature.PRESET_MODE

    def update(self):
        """Update unit attributes."""

    # Temperature
    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the sensor temperature."""
        return None

    @property
    def heater_value(self) -> int | None:
        gpiox = int(lc.getline(ROOTFS+"gpio"+self.gpiox_id+"/value",1).strip())
        gpioy = int(lc.getline(ROOTFS+"gpio"+self.gpiox_id+"/value",1).strip())
        gpio = [gpiox,gpioy]

        return gpio

    # Presets
    @property
    def preset_modes(self) -> list[str] | None:
        """List of available preset modes."""
        return [PRESET_COMFORT, PRESET_ECO, PRESET_AWAY]

    @property
    def preset_mode(self) -> str | None:
        value = self.heater_value

        if value is None:
            return STATE_UNKNOWN
        if value == VALUE_OFF:
            return PRESET_NONE
        elif value == VALUE_FROST:
            return PRESET_AWAY
        elif value == VALUE_ECO:
            return PRESET_ECO
        elif value == VALUE_COMFORT:
            return PRESET_COMFORT
        else:
            return STATE_UNKNOWN

    def async_set_preset_mode(self, preset_mode: str) -> None:
        value = VALUE_OFF

        if preset_mode == PRESET_AWAY:
            value = VALUE_FROST
        elif preset_mode == PRESET_ECO:
            value = VALUE_ECO
        elif preset_mode == PRESET_COMFORT:
            value = VALUE_COMFORT

        self._async_set_heater_value(value)

    # Modes
    @property
    def hvac_modes(self) -> list[HVACMode]:
        """List of available operation modes."""
        return [HVACMode.HEAT, HVACMode.OFF]

    def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        value = VALUE_FROST

        if hvac_mode == HVACMode.HEAT:
            value = VALUE_COMFORT
        elif hvac_mode == HVACMode.OFF:
            value = VALUE_OFF

        self._async_set_heater_value(value)

    @property
    def hvac_mode(self) -> HVACMode | str | None:
        value = self.heater_value

        if value is None:
            return STATE_UNKNOWN
        if value == VALUE_OFF:
            return HVACMode.OFF
        else:
            return HVACMode.HEAT

    @callback
    def _async_heater_changed(self, entity_id, old_state, new_state) -> None:
        if new_state is None:
            return
        self.async_schedule_update_ha_state()

    @callback
    def _async_set_heater_value(self, value):
        """Turn heater toggleable device on."""
        if value is None:
            return
        else:
            with open(ROOTFS+"gpio"+self.gpiox_id+"/value", 'w') as gpiox:
                gpiox.write(str(value[0]))
            with open(ROOTFS+"gpio"+self.gpioy_id+"/value", 'w') as gpioy:
                gpioy.write(str(value[1]))
