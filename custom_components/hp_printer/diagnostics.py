"""Diagnostics support."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import HPPrinterConfigEntry

TO_REDACT = {
    CONF_PASSWORD,
    "serial_number",
    "uuid",
    "unique_id",
    "mac",
    "bssid",
    "ssid",
    "wifi_ssid",
    "consumable_id",
    "ews_urls",
    "ipv4_address",
    "ipv6_addresses",
    "gateway",
    "dns_server",
    "secondary_dns_server",
    "dhcp_server",
    "mdns_domain",
    "hostname",
    "user",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HPPrinterConfigEntry
) -> dict[str, Any]:
    """Return the entry data and the last printer snapshot, redacted."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": async_redact_data(
            {"data": dict(entry.data), "options": dict(entry.options)},
            {CONF_PASSWORD, CONF_HOST},
        ),
        "capabilities": coordinator.capabilities.as_dict()
        if coordinator.capabilities
        else None,
        "data": async_redact_data(data.as_dict(), TO_REDACT) if data else None,
        "last_scan": coordinator.last_scan.as_dict() if coordinator.last_scan else None,
    }
