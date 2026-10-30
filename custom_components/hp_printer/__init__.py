"""HP Printer integration: LEDM, CDM, eSCL and IPP over the local network."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from hp_printer import HPPrinter

from .const import DOMAIN, PLATFORMS
from .coordinator import HPPrinterCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type HPPrinterConfigEntry = ConfigEntry[HPPrinterCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration-level actions."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HPPrinterConfigEntry) -> bool:
    """Set up an HP printer from a config entry."""
    client = HPPrinter(
        entry.data[CONF_HOST],
        password=entry.data.get(CONF_PASSWORD) or None,
        session=async_get_clientsession(hass),
    )
    coordinator = HPPrinterCoordinator(hass, entry, client)
    entry.async_on_unload(client.close)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HPPrinterConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: HPPrinterConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow removing the device only when it is no longer the configured printer."""
    return not any(
        identifier[0] == DOMAIN and identifier[1] == entry.unique_id
        for identifier in device_entry.identifiers
    )
