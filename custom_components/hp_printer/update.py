"""Firmware update entity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HPPrinterConfigEntry
from .entity import HPPrinterEntity

PARALLEL_UPDATES = 1

DESCRIPTION = UpdateEntityDescription(
    key="firmware",
    translation_key="firmware",
    device_class=UpdateDeviceClass.FIRMWARE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HPPrinterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the firmware update entity when the printer reports firmware."""
    coordinator = entry.runtime_data
    data = coordinator.data
    if data.device and data.device.firmware_version:
        async_add_entities([HPFirmwareUpdate(coordinator, DESCRIPTION)])


class HPFirmwareUpdate(HPPrinterEntity, UpdateEntity):
    """Installed/available firmware with install via the printer's web update."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )
    _attr_title = "HP printer firmware"

    @property
    def installed_version(self) -> str | None:
        """Running firmware."""
        return self.data.device.firmware_version if self.data.device else None

    @property
    def latest_version(self) -> str | None:
        """Firmware the printer found online, else the installed one."""
        firmware = self.data.firmware
        if firmware and firmware.target_version:
            return firmware.target_version
        return self.installed_version

    @property
    def in_progress(self) -> bool:
        """True while downloading/installing."""
        return bool(self.data.firmware and self.data.firmware.in_progress)

    @property
    def update_percentage(self) -> int | None:
        """Download/install progress."""
        firmware = self.data.firmware
        if firmware and firmware.in_progress:
            return firmware.progress
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Update state details."""
        firmware = self.data.firmware
        if not firmware:
            return {}
        return {
            "status": firmware.status,
            "auto_check": firmware.auto_check,
            "auto_update": firmware.auto_update,
            "error": firmware.error,
            "update_type": firmware.update_type,
        }

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Ask the printer to download and install the update it found."""
        await self.coordinator.async_write(
            lambda: self.coordinator.client.firmware_action("start")
        )
