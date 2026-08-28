"""Constants for the Midea Boiler integration."""

DOMAIN = "midea_boiler"

# Cloud API constants
APP_ID = "1010"
APP_KEY = "ac21b9f9cbfe4ca5a88562ef25e2b768"
IOT_KEY = "meicloud"
HMAC_KEY = "PROD_VnoClJI9aikS8dyy"
API_URL = "https://mp-ru-prod.appsmb.com/mas/v5/app/proxy?alias="

# Config fields
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_APPLIANCE_CODE = "appliance_code"

# Stored session fields (persisted in config entry data)
CONF_UID = "uid"
CONF_ACCESS_TOKEN = "access_token"
CONF_TOKEN_PWD = "token_pwd"
CONF_TOKEN_EXPIRY = "token_expiry"

# Default update interval (seconds)
DEFAULT_SCAN_INTERVAL = 30

# Status field names from the API
STATUS_POWER = "power"
STATUS_HEATING_MODE = "heating_mode"
STATUS_HEATING_TARGET_TEMPERATURE = "heating_target_temperature"
STATUS_IN_TEMPERATURE = "in_temperature"
STATUS_OUT_TEMPERATURE = "out_temperature"
STATUS_HEATING_MODE = "heating_mode"
STATUS_THREE_WAY_MODE = "three_way_mode"
STATUS_PUMP = "pump"
STATUS_ERROR_CODE = "error_code"
STATUS_BUZZER = "buzzer"

# Control command field names
CMD_POWER = "power"
CMD_HEATING_TARGET_TEMPERATURE = "heating_target_temperature"

# Control channel
CONTROL_CHANNEL = "COMMON_LUA"
