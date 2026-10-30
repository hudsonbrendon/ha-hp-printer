"""Base entity for the HP Printer integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from hp_printer import PrinterData

from .const import DOMAIN, MANUFACTURER
from .coordinator import HPPrinterCoordinator


def device_info(coordinator: HPPrinterCoordinator) -> DeviceInfo:
    """Describe the printer device."""
    entry = coordinator.config_entry
    data = coordinator.data
    device = data.device if data else None
    network = data.network if data else None
    kwargs: dict[str, Any] = {
        "identifiers": {(DOMAIN, entry.unique_id or entry.entry_id)},
        "manufacturer": MANUFACTURER,
        "name": entry.title,
        "configuration_url": f"http://{coordinator.client.host}/",
    }
    if device:
        kwargs["model"] = device.model_family or device.make_and_model
        if device.product_number:
            kwargs["model_id"] = device.product_number
        if device.serial_number:
            kwargs["serial_number"] = device.serial_number
        if device.firmware_version:
            kwargs["sw_version"] = device.firmware_version
        if device.sku:
            kwargs["hw_version"] = device.sku
    if network and network.mac:
        kwargs["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(network.mac))}
    return DeviceInfo(**kwargs)


class HPPrinterEntity(CoordinatorEntity[HPPrinterCoordinator]):
    """Entity bound to the printer device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HPPrinterCoordinator,
        description: EntityDescription,
        unique_suffix: str | None = None,
    ) -> None:
        """Initialise with a description; ``unique_suffix`` for per-cartridge ids."""
        super().__init__(coordinator)
        self.entity_description = description
        base = coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        key = (
            description.key
            if unique_suffix is None
            else f"{description.key}_{unique_suffix}"
        )
        self._attr_unique_id = f"{base}_{key}"
        self._attr_device_info = device_info(coordinator)

    @property
    def data(self) -> PrinterData:
        """Shortcut to the latest printer data."""
        return self.coordinator.data
