"""Constants for the CamillaDSP integration."""

# Integration domain
DOMAIN = "camilladsp"

# Configuration keys
CONF_HOST = "host"
CONF_PORT = "port"

# Defaults
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5005  # CamillaDSP default GUI port

# Polling / debounce
UPDATE_INTERVAL = 5  # seconds between coordinator polls
DEBOUNCE_DELAY = 0.5  # seconds for slider debounce

# Platforms to set up
PLATFORMS: list[str] = ["number", "switch", "select", "sensor"]

# ---- Service name constants (Phase 1+) ----
SERVICE_RELOAD_CONFIG = "reload_config"
SERVICE_SET_CONFIG_FILE = "set_config_file"

# ---- Config-entry runtime data keys ----
DATA_CLIENT = "client"
DATA_COORDINATOR = "coordinator"
