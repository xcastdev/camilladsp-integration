"""Config flow for CamillaDSP."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class CamillaDSPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CamillaDSP."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial user configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Abort if this host:port is already configured.
            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})

            # Attempt a connection test against the CamillaDSP GUI backend.
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"http://{host}:{port}/api/guiconfig"
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        resp.raise_for_status()
            except (aiohttp.ClientConnectionError, OSError):
                errors["base"] = "cannot_connect"
            except TimeoutError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during CamillaDSP connection test")
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=f"CamillaDSP ({host})",
                    data={CONF_HOST: host, CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
