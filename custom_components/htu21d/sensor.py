"""Support for HTU21D temperature and humidity sensor."""
from   datetime                            import timedelta
from   functools                           import partial
import logging
import voluptuous                              as vol
from   homeassistant.components.sensor     import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from   homeassistant.const                 import CONF_NAME, TEMP_FAHRENHEIT, CONF_MONITORED_CONDITIONS
from   homeassistant.helpers.entity        import Entity
from   homeassistant.util                  import Throttle
from   homeassistant.util.temperature      import celsius_to_fahrenheit

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME             = 'HTU21D Sensor'
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3)

SENSOR_TEMPERATURE = "temperature"
SENSOR_HUMIDITY    = "humidity"
SENSOR_TYPES       = {
    SENSOR_TEMPERATURE: ["Temperature", None],
    SENSOR_HUMIDITY: ["Humidity", "%"],
}

DEFAULT_MONITORED = [SENSOR_TEMPERATURE, SENSOR_HUMIDITY]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=DEFAULT_MONITORED): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the HTU21D sensor."""

    import board # pylint: disable=import-error
    import busio # pylint: disable=import-error
    from adafruit_htu21d import HTU21D # pylint: disable=import-error

    SENSOR_TYPES[SENSOR_TEMPERATURE][1] = hass.config.units.temperature_unit
    
    name = config.get(CONF_NAME)

    i2cbus = busio.I2C(board.SCL, board.SDA)
    sensor = await hass.async_add_job(partial(HTU21D, i2cbus))

    if sensor is None:
        _LOGGER.error("HTU21D sensor not detected on i2c bus")
        return False

    sensor_handler = await hass.async_add_job(HTU21DHandler, sensor)
    if sensor_handler is None:
        _LOGGER.error("Could not initialize HTU21D handler")
        return False

    # dev = [HTU21DSensor(sensor_handler, name, SENSOR_TEMPERATURE, temp_unit),
    #        HTU21DSensor(sensor_handler, name, SENSOR_HUMIDITY, '%')]
    dev = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        dev.append(HTU21DSensor(sensor_handler, variable, SENSOR_TYPES[variable][1], name) )

    async_add_entities(dev)
    return

class HTU21DHandler:
    """Implement HTU21D hardware communication."""

    def __init__(self, sensor):
        """Initialize the sensor handler."""
        self.sensor = sensor
        # update
        self.sensor_data.temperature = None
        self.sensor_data.humidity    = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Read sensor data."""
        self.sensor_data.temperature = self.sensor.temperature
        self.sensor_data.humidity    = self.sensor.relative_humidity

class HTU21DSensor(Entity):
    """Implementation of the HTU21D sensor."""

    def __init__(self, htu21d_client, sensor_type, temp_unit, name):
        """Initialize the sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.htu21d_client = htu21d_client
        self.temp_unit = temp_unit
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    async def async_update(self):
        """Get the latest data from the HTU21D sensor handler and update the state."""
        await self.hass.async_add_job(self.htu21d_client.update)
        if self.type == SENSOR_TEMPERATURE:
            value = round(self.htu21d_client.sensor_data.temperature, 1)
            if self.temp_unit == TEMP_FAHRENHEIT:
                value = round(celsius_to_fahrenheit(value), 1)
        else:
            value = round(self.htu21d_client.sensor_data.humidity, 1)
        self._state = value
