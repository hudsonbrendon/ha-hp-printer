"""Switches: quiet mode, firmware auto update, network services."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from hp_printer import HPPrinter, PrinterData

from . import HPPrinterConfigEntry
from .entity import HPPrinterEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HPSwitchDescription(SwitchEntityDescription):
    """Switch backed by a printer setting."""

    is_on_fn: Callable[[PrinterData], bool | None]
    set_fn: Callable[[HPPrinter, bool], Awaitable[Any]]
    exists_fn: Callable[[PrinterData], bool]


def _net(attr: str) -> Callable[[PrinterData], bool | None]:
    return lambda d: getattr(d.network, attr) if d.network else None


def _net_exists(attr: str) -> Callable[[PrinterData], bool]:
    return lambda d: d.network is not None and getattr(d.network, attr) is not None


SWITCHES: tuple[HPSwitchDescription, ...] = (
    HPSwitchDescription(
        key="quiet_mode",
        translation_key="quiet_mode",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda d: d.settings.quiet_mode if d.settings else None,
        set_fn=lambda c, on: c.set_quiet_mode(on),
        exists_fn=lambda d: (
            d.settings is not None and d.settings.quiet_mode is not None
        ),
    ),
    HPSwitchDescription(
        key="firmware_auto_check",
        translation_key="firmware_auto_check",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda d: d.firmware.auto_check if d.firmware else None,
        set_fn=lambda c, on: c.set_firmware_auto(check=on),
        exists_fn=lambda d: (
            d.firmware is not None and d.firmware.auto_check is not None
        ),
    ),
    HPSwitchDescription(
        key="firmware_auto_update",
        translation_key="firmware_auto_update",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda d: d.firmware.auto_update if d.firmware else None,
        set_fn=lambda c, on: c.set_firmware_auto(update=on),
        exists_fn=lambda d: (
            d.firmware is not None and d.firmware.auto_update is not None
        ),
    ),
    HPSwitchDescription(
        key="power_save",
        translation_key="power_save",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=lambda d: d.settings.power_save_enabled if d.settings else None,
        set_fn=lambda c, on: c.set_product_settings(PowerSave="on" if on else "off"),
        exists_fn=lambda d: (
            d.capabilities.has_ledm
            and d.settings is not None
            and d.settings.power_save_enabled is not None
        ),
    ),
    HPSwitchDescription(
        key="ews",
        translation_key="ews",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=lambda d: d.settings.ews_enabled if d.settings else None,
        set_fn=lambda c, on: c.set_ews_enabled(on),
        exists_fn=lambda d: (
            d.capabilities.has_ledm
            and d.settings is not None
            and d.settings.ews_enabled is not None
        ),
    ),
    HPSwitchDescription(
        key="airprint",
        translation_key="airprint",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("airprint_enabled"),
        set_fn=lambda c, on: c.set_secure_network_services(airprint=on),
        exists_fn=lambda d: (
            d.capabilities.has_ledm and _net_exists("airprint_enabled")(d)
        ),
    ),
    HPSwitchDescription(
        key="ipps",
        translation_key="ipps",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("ipps_enabled"),
        set_fn=lambda c, on: c.set_secure_network_services(ipps=on),
        exists_fn=lambda d: d.capabilities.has_ledm and _net_exists("ipps_enabled")(d),
    ),
    HPSwitchDescription(
        key="bluetooth",
        translation_key="bluetooth",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("bluetooth_enabled"),
        set_fn=lambda c, on: c.set_secure_network_services(bluetooth=on),
        exists_fn=lambda d: (
            d.capabilities.has_ledm and _net_exists("bluetooth_enabled")(d)
        ),
    ),
    HPSwitchDescription(
        key="remote_scans",
        translation_key="remote_scans",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("remote_scans_enabled"),
        set_fn=lambda c, on: c.set_secure_network_services(remote_scans=on),
        exists_fn=lambda d: (
            d.capabilities.has_ledm and _net_exists("remote_scans_enabled")(d)
        ),
    ),
    HPSwitchDescription(
        key="wifi_direct_show_passphrase",
        translation_key="wifi_direct_show_passphrase",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("wifi_direct_show_passphrase"),
        set_fn=lambda c, on: c.set_secure_network_services(
            wifi_direct_show_passphrase=on
        ),
        exists_fn=lambda d: (
            d.capabilities.has_ledm and _net_exists("wifi_direct_show_passphrase")(d)
        ),
    ),
    HPSwitchDescription(
        key="wifi_direct_hide_ssid",
        translation_key="wifi_direct_hide_ssid",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("wifi_direct_hide_ssid"),
        set_fn=lambda c, on: c.set_secure_network_services(wifi_direct_hide_ssid=on),
        exists_fn=lambda d: (
            d.capabilities.has_ledm and _net_exists("wifi_direct_hide_ssid")(d)
        ),
    ),
    HPSwitchDescription(
        key="ipp",
        translation_key="ipp",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("ipp_enabled"),
        set_fn=lambda c, on: c.set_network_services(ipp=on),
        exists_fn=lambda d: d.capabilities.has_ledm and _net_exists("ipp_enabled")(d),
    ),
    HPSwitchDescription(
        key="port9100",
        translation_key="port9100",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("port9100_enabled"),
        set_fn=lambda c, on: c.set_network_services(port9100=on),
        exists_fn=lambda d: (
            d.capabilities.has_ledm and _net_exists("port9100_enabled")(d)
        ),
    ),
    HPSwitchDescription(
        key="snmp",
        translation_key="snmp",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("snmp_enabled"),
        set_fn=lambda c, on: c.set_network_services(snmp=on),
        exists_fn=lambda d: d.capabilities.has_ledm and _net_exists("snmp_enabled")(d),
    ),
    HPSwitchDescription(
        key="mdns",
        translation_key="mdns",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("mdns_enabled"),
        set_fn=lambda c, on: c.set_network_services(mdns=on),
        exists_fn=lambda d: d.capabilities.has_ledm and _net_exists("mdns_enabled")(d),
    ),
    HPSwitchDescription(
        key="ws_discovery",
        translation_key="ws_discovery",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("ws_discovery_enabled"),
        set_fn=lambda c, on: c.set_network_services(ws_discovery=on),
        exists_fn=lambda d: (
            d.capabilities.has_ledm and _net_exists("ws_discovery_enabled")(d)
        ),
    ),
    HPSwitchDescription(
        key="ws_print",
        translation_key="ws_print",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("ws_print_enabled"),
        set_fn=lambda c, on: c.set_network_services(ws_print=on),
        exists_fn=lambda d: (
            d.capabilities.has_ledm and _net_exists("ws_print_enabled")(d)
        ),
    ),
    HPSwitchDescription(
        key="ws_scan",
        translation_key="ws_scan",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("ws_scan_enabled"),
        set_fn=lambda c, on: c.set_network_services(ws_scan=on),
        exists_fn=lambda d: (
            d.capabilities.has_ledm and _net_exists("ws_scan_enabled")(d)
        ),
    ),
    HPSwitchDescription(
        key="llmnr",
        translation_key="llmnr",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("llmnr_enabled"),
        set_fn=lambda c, on: c.set_network_services(llmnr=on),
        exists_fn=lambda d: d.capabilities.has_ledm and _net_exists("llmnr_enabled")(d),
    ),
    HPSwitchDescription(
        key="webscan",
        translation_key="webscan",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_net("webscan_enabled"),
        set_fn=lambda c, on: c.set_network_services(webscan=on),
        exists_fn=lambda d: (
            d.capabilities.has_ledm and _net_exists("webscan_enabled")(d)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HPPrinterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        HPSwitch(coordinator, description)
        for description in SWITCHES
        if description.exists_fn(coordinator.data)
    )


class HPSwitch(HPPrinterEntity, SwitchEntity):
    """Switch writing a printer setting."""

    entity_description: HPSwitchDescription

    @property
    def is_on(self) -> bool | None:
        """Current value."""
        return self.entity_description.is_on_fn(self.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable."""
        await self.coordinator.async_write(
            lambda: self.entity_description.set_fn(self.coordinator.client, True)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable."""
        await self.coordinator.async_write(
            lambda: self.entity_description.set_fn(self.coordinator.client, False)
        )
