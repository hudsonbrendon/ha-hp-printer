"""Binary sensors: problem, printing, scanning, sleeping, connectivity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from hp_printer import PrinterData, PrinterState

from . import HPPrinterConfigEntry
from .entity import HPPrinterEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HPBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor fed from PrinterData."""

    is_on_fn: Callable[[PrinterData], bool | None]
    attributes_fn: Callable[[PrinterData], dict[str, Any]] | None = None
    exists_fn: Callable[[PrinterData], bool] = lambda _: True


def _any_low(d: PrinterData) -> bool:
    if not d.consumables:
        return False
    return any(c.is_low or c.is_empty for c in d.consumables.consumables)


BINARY_SENSORS: tuple[HPBinarySensorDescription, ...] = (
    HPBinarySensorDescription(
        key="problem",
        translation_key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda d: bool(d.status and d.status.has_error),
        attributes_fn=lambda d: {"problems": d.status.problems if d.status else []},
        exists_fn=lambda d: d.status is not None,
    ),
    HPBinarySensorDescription(
        key="attention",
        translation_key="attention",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_registry_enabled_default=False,
        is_on_fn=lambda d: bool(
            d.status and (d.status.has_error or d.status.has_warning)
        ),
        exists_fn=lambda d: d.status is not None,
    ),
    HPBinarySensorDescription(
        key="printing",
        translation_key="printing",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda d: d.state is PrinterState.PRINTING,
    ),
    HPBinarySensorDescription(
        key="scanning",
        translation_key="scanning",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda d: d.state is PrinterState.SCANNING,
        exists_fn=lambda d: d.capabilities.has_scanner,
    ),
    HPBinarySensorDescription(
        key="sleeping",
        translation_key="sleeping",
        is_on_fn=lambda d: d.state is PrinterState.SLEEPING,
        exists_fn=lambda d: d.status is not None,
    ),
    HPBinarySensorDescription(
        key="low_ink",
        translation_key="low_ink",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_any_low,
        exists_fn=lambda d: d.consumables is not None,
    ),
    HPBinarySensorDescription(
        key="paper_loaded",
        translation_key="paper_loaded",
        entity_registry_enabled_default=False,
        is_on_fn=lambda d: (
            not (
                d.status
                and any(
                    c in ("trayEmptyOrOpen", "trayOpen", "removeMedia")
                    for c in d.status.problems
                )
            )
        ),
        exists_fn=lambda d: d.status is not None,
    ),
    HPBinarySensorDescription(
        key="firmware_update_available",
        translation_key="firmware_update_available",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda d: bool(d.firmware and d.firmware.update_available),
        exists_fn=lambda d: d.firmware is not None,
    ),
    HPBinarySensorDescription(
        key="wifi_connected",
        translation_key="wifi_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: bool(
            d.network and d.network.wifi and d.network.wifi.connected
        ),
        exists_fn=lambda d: bool(d.network and d.network.wifi),
    ),
    HPBinarySensorDescription(
        key="eprint_registered",
        translation_key="eprint_registered",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda d: bool(d.eprint and d.eprint.registered),
        attributes_fn=lambda d: {
            "connection_state": d.eprint.connection_state if d.eprint else None,
            "cloud_services_enabled": d.eprint.cloud_services_enabled
            if d.eprint
            else None,
        },
        exists_fn=lambda d: d.eprint is not None,
    ),
    HPBinarySensorDescription(
        key="accepting_jobs",
        translation_key="accepting_jobs",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda d: bool(d.ipp and d.ipp.accepting_jobs),
        exists_fn=lambda d: d.ipp is not None and d.ipp.accepting_jobs is not None,
    ),
    HPBinarySensorDescription(
        key="calibration_required",
        translation_key="calibration_required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: (d.calibration_state or "").lower() == "calibrationrequired",
        exists_fn=lambda d: d.calibration_state is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HPPrinterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        HPBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if description.exists_fn(coordinator.data)
    )


class HPBinarySensor(HPPrinterEntity, BinarySensorEntity):
    """Binary sensor bound to the printer."""

    entity_description: HPBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        """Current state."""
        return self.entity_description.is_on_fn(self.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Extra attributes."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.data)
