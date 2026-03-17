"""Constants for the CamillaDSP integration."""

# Integration domain
DOMAIN = "camilladsp"

# Configuration keys
CONF_BASE_URL = "base_url"

# Legacy keys kept for config-entry migration from v1 → v2
CONF_HOST = "host"
CONF_PORT = "port"

# Defaults
DEFAULT_BASE_URL = "http://localhost:5005"

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
