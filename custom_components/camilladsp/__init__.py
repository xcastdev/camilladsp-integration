"""The CamillaDSP integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api.client import CamillaDSPClient
from .const import (
    CONF_BASE_URL,
    CONF_HOST,
    CONF_PORT,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import CamillaDSPCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the CamillaDSP integration (YAML-less)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries from v1 (host+port) to v2 (base_url)."""
    if entry.version == 1:
        _LOGGER.info(
            "Migrating CamillaDSP config entry %s from v1 to v2", entry.entry_id
        )
        host = entry.data.get(CONF_HOST, "localhost")
        port = entry.data.get(CONF_PORT, 5005)
        base_url = f"http://{host}:{port}"

        hass.config_entries.async_update_entry(
            entry,
            data={CONF_BASE_URL: base_url},
            version=2,
        )
        _LOGGER.info("Migration to v2 successful: %s", base_url)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CamillaDSP from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    base_url = entry.data[CONF_BASE_URL]

    # Create the API client using HA's shared aiohttp session
    session = async_get_clientsession(hass)
    client = CamillaDSPClient(base_url, session=session)

    # Create and initialise the coordinator
    coordinator = CamillaDSPCoordinator(hass, entry, client)
    await coordinator.async_initial_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (idempotent – only registers on first entry)
    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a CamillaDSP config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

        # If no more entries remain, unload services and clean up.
        if not hass.data[DOMAIN]:
            await async_unload_services(hass)
            hass.data.pop(DOMAIN, None)

    return unload_ok
