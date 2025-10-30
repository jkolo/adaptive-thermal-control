"""Constants for the Adaptive Thermal Control integration."""

from typing import Final

# Integration domain
DOMAIN: Final = "adaptive_thermal_control"

# Platforms
PLATFORMS: Final = ["climate", "sensor"]

# Configuration keys - Global
CONF_OUTDOOR_TEMP_ENTITY: Final = "outdoor_temp_entity"
CONF_HEATING_SWITCH_ENTITY: Final = "heating_switch_entity"
CONF_ENERGY_PRICE_ENTITY: Final = "energy_price_entity"
CONF_WEATHER_ENTITY: Final = "weather_entity"
CONF_SOLAR_IRRADIANCE_ENTITY: Final = "solar_irradiance_entity"
CONF_ENERGY_CONSUMPTION_ENTITY: Final = "energy_consumption_entity"
CONF_MAX_BOILER_POWER: Final = "max_boiler_power"

# Configuration keys - Thermostat
CONF_ROOM_NAME: Final = "room_name"
CONF_ROOM_TEMP_ENTITY: Final = "room_temp_entity"
CONF_VALVE_ENTITIES: Final = "valve_entities"
CONF_WATER_TEMP_IN_ENTITY: Final = "water_temp_in_entity"
CONF_WATER_TEMP_OUT_ENTITY: Final = "water_temp_out_entity"
CONF_VALVE_OPEN_TIME: Final = "valve_open_time"
CONF_VALVE_CLOSE_TIME: Final = "valve_close_time"
CONF_NEIGHBORING_ROOMS: Final = "neighboring_rooms"
CONF_WINDOW_ORIENTATIONS: Final = "window_orientations"
CONF_ROOM_AREA: Final = "room_area"
CONF_MIN_TEMP: Final = "min_temp"
CONF_MAX_TEMP: Final = "max_temp"

# Default values - PI Controller
DEFAULT_KP: Final = 10.0  # Proportional gain
DEFAULT_TI: Final = 1500.0  # Integral time constant [seconds] (25 minutes)
DEFAULT_DT: Final = 600.0  # Control update interval [seconds] (10 minutes)
DEFAULT_ANTI_WINDUP_LIMIT: Final = 100.0  # Anti-windup limit [%]

# Default values - Thermostat
DEFAULT_MIN_TEMP: Final = 15.0  # Minimum temperature [°C]
DEFAULT_MAX_TEMP: Final = 28.0  # Maximum temperature [°C]
DEFAULT_TARGET_TEMP: Final = 21.0  # Default target temperature [°C]
DEFAULT_VALVE_OPEN_TIME: Final = 45.0  # Default valve opening time [seconds]
DEFAULT_VALVE_CLOSE_TIME: Final = 45.0  # Default valve closing time [seconds]

# Timeouts and intervals
SENSOR_TIMEOUT: Final = 3600  # Sensor data timeout [seconds] (1 hour)
UPDATE_INTERVAL: Final = 600  # Data update interval [seconds] (10 minutes)
MIN_TRAINING_DAYS: Final = 7  # Minimum days of historical data for MPC
OPTIMAL_TRAINING_DAYS: Final = 30  # Optimal days of historical data

# MPC parameters (placeholders for Phase 3)
MPC_PREDICTION_HORIZON: Final = 24  # Np - prediction steps (4 hours with dt=10min)
MPC_CONTROL_HORIZON: Final = 12  # Nc - control steps (2 hours with dt=10min)
MPC_WEIGHT_COMFORT: Final = 1.0  # Weight for comfort in cost function
MPC_WEIGHT_ENERGY: Final = 0.1  # Weight for energy in cost function

# Failsafe parameters (T3.6.1)
MPC_MAX_FAILURES: Final = 3  # Maximum consecutive MPC failures before permanent fallback
MPC_TIMEOUT: Final = 10.0  # Maximum MPC computation time [seconds]
MPC_RETRY_INTERVAL: Final = 3600  # Time to wait before retrying MPC after failures [seconds]
MPC_SUCCESS_COUNT_TO_RECOVER: Final = 5  # Consecutive successes needed to consider MPC stable

# Thermal model parameters (placeholders for Phase 2)
THERMAL_MODEL_R_DEFAULT: Final = 0.01  # Default thermal resistance [K/W]
THERMAL_MODEL_C_DEFAULT: Final = 1e6  # Default thermal capacity [J/K]

# Window orientations
ORIENTATIONS: Final = [
    "N",
    "NE",
    "E",
    "SE",
    "S",
    "SW",
    "W",
    "NW",
]

# Preset modes
PRESET_HOME: Final = "home"
PRESET_AWAY: Final = "away"
PRESET_SLEEP: Final = "sleep"
PRESET_MANUAL: Final = "manual"

# Controller types
CONTROLLER_TYPE_PI: Final = "PI"
CONTROLLER_TYPE_MPC: Final = "MPC"

# State attributes
ATTR_VALVE_POSITION: Final = "valve_position"
ATTR_HEATING_DEMAND: Final = "heating_demand"
ATTR_CONTROLLER_TYPE: Final = "controller_type"
ATTR_TOTAL_POWER_USAGE: Final = "total_power_usage"
ATTR_PREDICTION_HORIZON: Final = "prediction_horizon"
ATTR_MODEL_PARAMETERS: Final = "model_parameters"
ATTR_MPC_STATUS: Final = "mpc_status"  # "active", "degraded", "disabled"
ATTR_MPC_FAILURE_COUNT: Final = "mpc_failure_count"
ATTR_MPC_LAST_FAILURE_REASON: Final = "mpc_last_failure_reason"
