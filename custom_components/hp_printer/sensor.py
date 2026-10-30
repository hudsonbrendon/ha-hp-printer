"""Sensors: status, supplies, counters, network, scanner, jobs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from hp_printer import Consumable, PrinterData, PrinterState

from . import HPPrinterConfigEntry
from .coordinator import HPPrinterCoordinator
from .entity import HPPrinterEntity

PARALLEL_UPDATES = 0

PAGES = "pages"


@dataclass(frozen=True, kw_only=True)
class HPSensorDescription(SensorEntityDescription):
    """Sensor fed from PrinterData."""

    value_fn: Callable[[PrinterData], StateType | datetime]
    attributes_fn: Callable[[PrinterData], dict[str, Any]] | None = None
    exists_fn: Callable[[PrinterData], bool] = lambda _: True


def _usage(attr: str) -> Callable[[PrinterData], StateType]:
    return lambda d: getattr(d.usage, attr) if d.usage else None


def _usage_exists(attr: str) -> Callable[[PrinterData], bool]:
    return lambda d: d.usage is not None and getattr(d.usage, attr) is not None


def _wifi(attr: str) -> Callable[[PrinterData], StateType]:
    def value(d: PrinterData) -> StateType:
        wifi = d.network.wifi if d.network else None
        return getattr(wifi, attr) if wifi else None

    return value


def _uptime(d: PrinterData) -> datetime | None:
    if d.ipp is None or d.ipp.uptime_seconds is None:
        return None
    return dt_util.utcnow() - timedelta(seconds=d.ipp.uptime_seconds)


def _status_attributes(d: PrinterData) -> dict[str, Any]:
    status = d.status
    return {
        "categories": status.categories if status else [],
        "problems": status.problems if status else [],
        "alerts": [
            {"id": a.id, "severity": a.severity, "priority": a.priority}
            for a in (status.alerts if status else [])
        ],
        "ipp_state": d.ipp.state if d.ipp else None,
        "ipp_state_reasons": d.ipp.state_reasons if d.ipp else [],
        "scanner_state": d.scanner.state if d.scanner else None,
    }


def _current_job_attributes(d: PrinterData) -> dict[str, Any]:
    job = d.current_job
    if job is None:
        return {"job_id": None, "state": None}
    return {
        "job_id": job.id,
        "state": job.state,
        "state_reasons": job.state_reasons,
        "user": job.user,
        "impressions": job.impressions,
        "impressions_completed": job.impressions_completed,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


def _last_job_attributes(d: PrinterData) -> dict[str, Any]:
    done = [j for j in d.jobs if not j.is_active]
    if not done:
        return {}
    job = done[0]
    return {
        "job_id": job.id,
        "state": job.state,
        "user": job.user,
        "impressions_completed": job.impressions_completed,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


SENSORS: tuple[HPSensorDescription, ...] = (
    HPSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[state.value for state in PrinterState],
        value_fn=lambda d: d.state.value,
        attributes_fn=_status_attributes,
    ),
    HPSensorDescription(
        key="total_pages",
        translation_key="total_pages",
        native_unit_of_measurement=PAGES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_usage("total_impressions"),
        exists_fn=_usage_exists("total_impressions"),
    ),
    HPSensorDescription(
        key="monochrome_pages",
        translation_key="monochrome_pages",
        native_unit_of_measurement=PAGES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_usage("monochrome_impressions"),
        exists_fn=_usage_exists("monochrome_impressions"),
    ),
    HPSensorDescription(
        key="color_pages",
        translation_key="color_pages",
        native_unit_of_measurement=PAGES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_usage("color_impressions"),
        exists_fn=_usage_exists("color_impressions"),
    ),
    HPSensorDescription(
        key="duplex_sheets",
        translation_key="duplex_sheets",
        native_unit_of_measurement=PAGES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_usage("duplex_sheets"),
        exists_fn=_usage_exists("duplex_sheets"),
    ),
    HPSensorDescription(
        key="scan_pages",
        translation_key="scan_pages",
        native_unit_of_measurement=PAGES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_usage("scan_images"),
        exists_fn=_usage_exists("scan_images"),
    ),
    HPSensorDescription(
        key="copy_pages",
        translation_key="copy_pages",
        native_unit_of_measurement=PAGES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_usage("copy_impressions"),
        exists_fn=_usage_exists("copy_impressions"),
    ),
    HPSensorDescription(
        key="fax_pages",
        translation_key="fax_pages",
        native_unit_of_measurement=PAGES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_usage("fax_impressions"),
        exists_fn=_usage_exists("fax_impressions"),
    ),
    HPSensorDescription(
        key="jam_events",
        translation_key="jam_events",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_usage("jam_events"),
        exists_fn=_usage_exists("jam_events"),
    ),
    HPSensorDescription(
        key="mispick_events",
        translation_key="mispick_events",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_usage("mispick_events"),
        exists_fn=_usage_exists("mispick_events"),
    ),
    HPSensorDescription(
        key="cancel_presses",
        translation_key="cancel_presses",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_usage("front_panel_cancel_presses"),
        exists_fn=_usage_exists("front_panel_cancel_presses"),
    ),
    HPSensorDescription(
        key="ink_used",
        translation_key="ink_used",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=_usage("ink_used_ml"),
        exists_fn=_usage_exists("ink_used_ml"),
    ),
    HPSensorDescription(
        key="quiet_mode_pages",
        translation_key="quiet_mode_pages",
        native_unit_of_measurement=PAGES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_usage("quiet_mode_impressions"),
        exists_fn=_usage_exists("quiet_mode_impressions"),
    ),
    HPSensorDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_wifi("rssi_dbm"),
        exists_fn=lambda d: bool(
            d.network and d.network.wifi and d.network.wifi.rssi_dbm is not None
        ),
    ),
    HPSensorDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_wifi("signal_strength"),
        exists_fn=lambda d: bool(
            d.network and d.network.wifi and d.network.wifi.signal_strength is not None
        ),
    ),
    HPSensorDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_wifi("ssid"),
        exists_fn=lambda d: bool(d.network and d.network.wifi and d.network.wifi.ssid),
    ),
    HPSensorDescription(
        key="ip_address",
        translation_key="ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (
            d.network.active.ipv4_address if d.network and d.network.active else None
        ),
        exists_fn=lambda d: bool(
            d.network and d.network.active and d.network.active.ipv4_address
        ),
    ),
    HPSensorDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_uptime,
        exists_fn=lambda d: d.ipp is not None and d.ipp.uptime_seconds is not None,
    ),
    HPSensorDescription(
        key="firmware_update_status",
        translation_key="firmware_update_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.firmware.status if d.firmware else None,
        exists_fn=lambda d: d.firmware is not None,
    ),
    HPSensorDescription(
        key="paper_size",
        translation_key="paper_size",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.media.current_media_size if d.media else None,
        exists_fn=lambda d: bool(d.media and d.media.current_media_size),
    ),
    HPSensorDescription(
        key="paper_type",
        translation_key="paper_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.media.current_media_type if d.media else None,
        exists_fn=lambda d: bool(d.media and d.media.current_media_type),
    ),
    HPSensorDescription(
        key="scanner_state",
        translation_key="scanner_state",
        device_class=SensorDeviceClass.ENUM,
        options=["idle", "processing", "testing", "stopped", "down"],
        value_fn=lambda d: (
            (d.scanner.state or "").lower() or None if d.scanner else None
        ),
        exists_fn=lambda d: d.scanner is not None,
    ),
    HPSensorDescription(
        key="current_job",
        translation_key="current_job",
        value_fn=lambda d: d.current_job.name if d.current_job else None,
        attributes_fn=_current_job_attributes,
        exists_fn=lambda d: d.capabilities.has_ipp,
    ),
    HPSensorDescription(
        key="last_job",
        translation_key="last_job",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: next((j.name for j in d.jobs if not j.is_active), None),
        attributes_fn=_last_job_attributes,
        exists_fn=lambda d: d.capabilities.has_ipp,
    ),
    HPSensorDescription(
        key="queued_jobs",
        translation_key="queued_jobs",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.ipp.queued_jobs if d.ipp else None,
        exists_fn=lambda d: d.ipp is not None and d.ipp.queued_jobs is not None,
    ),
    HPSensorDescription(
        key="calibration_state",
        translation_key="calibration_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.calibration_state,
        exists_fn=lambda d: d.calibration_state is not None,
    ),
    HPSensorDescription(
        key="eprint_status",
        translation_key="eprint_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.eprint.registration_state if d.eprint else None,
        exists_fn=lambda d: d.eprint is not None,
    ),
    HPSensorDescription(
        key="last_error_code",
        translation_key="last_error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.logs.events[0].code if d.logs and d.logs.events else None,
        attributes_fn=lambda d: {
            "events": [
                {"code": e.code, "occurrences": e.occurrences, "sequence": e.sequence}
                for e in (d.logs.events if d.logs else [])
            ]
        },
        exists_fn=lambda d: d.logs is not None,
    ),
    HPSensorDescription(
        key="last_scan",
        translation_key="last_scan",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: None,  # replaced by the entity (coordinator state)
        exists_fn=lambda d: d.capabilities.has_escl,
    ),
)


@dataclass(frozen=True, kw_only=True)
class HPConsumableSensorDescription(SensorEntityDescription):
    """Per-cartridge sensor."""

    value_fn: Callable[[Consumable], StateType]


CONSUMABLE_SENSORS: tuple[HPConsumableSensorDescription, ...] = (
    HPConsumableSensorDescription(
        key="level",
        translation_key="consumable_level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.level,
    ),
    HPConsumableSensorDescription(
        key="raw_level",
        translation_key="consumable_raw_level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.raw_level,
    ),
    HPConsumableSensorDescription(
        key="state",
        translation_key="consumable_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.state,
    ),
    HPConsumableSensorDescription(
        key="pages_remaining",
        translation_key="consumable_pages_remaining",
        native_unit_of_measurement=PAGES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.estimated_pages_remaining,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HPPrinterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create sensors for everything the printer reports."""
    coordinator = entry.runtime_data
    data = coordinator.data
    entities: list[SensorEntity] = []
    for description in SENSORS:
        if not description.exists_fn(data):
            continue
        if description.key == "last_scan":
            entities.append(HPLastScanSensor(coordinator, description))
        else:
            entities.append(HPSensor(coordinator, description))
    if data.consumables:
        for consumable in data.consumables.consumables:
            for description in CONSUMABLE_SENSORS:
                if (
                    description.key == "pages_remaining"
                    and consumable.estimated_pages_remaining is None
                ):
                    continue
                if description.key == "raw_level" and consumable.raw_level is None:
                    continue
                entities.append(
                    HPConsumableSensor(coordinator, description, consumable)
                )
    async_add_entities(entities)


class HPSensor(HPPrinterEntity, SensorEntity):
    """Printer-level sensor."""

    entity_description: HPSensorDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Current value."""
        return self.entity_description.value_fn(self.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Extra attributes."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.data)


class HPLastScanSensor(HPPrinterEntity, SensorEntity):
    """Timestamp of the last scan started from Home Assistant."""

    entity_description: HPSensorDescription

    @property
    def native_value(self) -> datetime | None:
        """When the last scan finished."""
        scan = self.coordinator.last_scan
        return scan.when if scan else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Where the scan was saved."""
        scan = self.coordinator.last_scan
        return scan.as_dict() if scan else {}


def consumable_slug(consumable: Consumable) -> str:
    """Stable per-cartridge suffix (label code, then station)."""
    if consumable.label_code:
        return consumable.label_code.lower()
    return f"station_{consumable.station}"


class HPConsumableSensor(HPPrinterEntity, SensorEntity):
    """Sensor bound to one cartridge / toner / tank."""

    entity_description: HPConsumableSensorDescription

    def __init__(
        self,
        coordinator: HPPrinterCoordinator,
        description: HPConsumableSensorDescription,
        consumable: Consumable,
    ) -> None:
        """Bind to the cartridge by label code / station."""
        super().__init__(coordinator, description, consumable_slug(consumable))
        self._slug = consumable_slug(consumable)
        color = (consumable.color or self._slug).replace("_", " ")
        self._attr_translation_placeholders = {"color": color}

    def _consumable(self) -> Consumable | None:
        if not self.data.consumables:
            return None
        for consumable in self.data.consumables.consumables:
            if consumable_slug(consumable) == self._slug:
                return consumable
        return None

    @property
    def available(self) -> bool:
        """Unavailable when the cartridge disappeared."""
        return super().available and self._consumable() is not None

    @property
    def native_value(self) -> StateType:
        """Current value."""
        consumable = self._consumable()
        return self.entity_description.value_fn(consumable) if consumable else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Cartridge details on the level sensor."""
        consumable = self._consumable()
        if consumable is None or self.entity_description.key != "level":
            return None
        return {
            "color": consumable.color,
            "css_color": consumable.css_color,
            "type": consumable.type,
            "state": consumable.state,
            "cartridge_number": consumable.selectability_number,
            "compatible_numbers": consumable.supported_numbers,
            "genuine_hp": consumable.is_genuine_hp,
            "refilled": consumable.is_refilled,
            "setup_cartridge": consumable.is_setup,
            "unique_id": consumable.unique_id,
            "insertions": consumable.insertions,
            "low": consumable.is_low,
            "empty": consumable.is_empty,
        }
