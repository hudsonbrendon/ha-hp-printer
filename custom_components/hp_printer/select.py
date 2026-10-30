"""Selects: sleep timeout, language, print/copy defaults, scan defaults."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from hp_printer import HPPrinter, PrinterData

from . import HPPrinterConfigEntry
from .const import (
    CONF_SCAN_COLOR_MODE,
    CONF_SCAN_FORMAT,
    CONF_SCAN_RESOLUTION,
    CONF_SCAN_SOURCE,
    DEFAULT_SCAN_COLOR_MODE,
    DEFAULT_SCAN_FORMAT,
    DEFAULT_SCAN_RESOLUTION,
    DEFAULT_SCAN_SOURCE,
    SCAN_COLOR_MODES,
    SCAN_FORMATS,
)
from .coordinator import HPPrinterCoordinator
from .entity import HPPrinterEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HPSelectDescription(SelectEntityDescription):
    """Select backed by a printer setting with options from its capabilities."""

    current_fn: Callable[[PrinterData], str | None]
    options_fn: Callable[[PrinterData], list[str]]
    set_fn: Callable[[HPPrinter, str], Awaitable[Any]]
    exists_fn: Callable[[PrinterData], bool] = lambda _: True


def _settings(attr: str) -> Callable[[PrinterData], str | None]:
    return lambda d: getattr(d.settings, attr) if d.settings else None


def _caps(attr: str) -> Callable[[PrinterData], list[str]]:
    return lambda d: (
        list(getattr(d.settings_capabilities, attr)) if d.settings_capabilities else []
    )


def _has_options(attr: str) -> Callable[[PrinterData], bool]:
    return lambda d: bool(
        d.settings_capabilities and len(getattr(d.settings_capabilities, attr)) > 1
    )


SELECTS: tuple[HPSelectDescription, ...] = (
    HPSelectDescription(
        key="power_save_timeout",
        translation_key="power_save_timeout",
        entity_category=EntityCategory.CONFIG,
        current_fn=_settings("power_save_timeout"),
        options_fn=_caps("power_save_timeouts"),
        set_fn=lambda c, v: c.set_power_save_timeout(v),
        exists_fn=lambda d: (
            d.capabilities.has_ledm and _has_options("power_save_timeouts")(d)
        ),
    ),
    HPSelectDescription(
        key="auto_off_time",
        translation_key="auto_off_time",
        entity_category=EntityCategory.CONFIG,
        current_fn=_settings("auto_off_time"),
        options_fn=_caps("auto_off_times"),
        set_fn=lambda c, v: c.set_auto_off_time(v),
        exists_fn=lambda d: (
            d.capabilities.has_ledm and _has_options("auto_off_times")(d)
        ),
    ),
    HPSelectDescription(
        key="device_language",
        translation_key="device_language",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        current_fn=_settings("device_language"),
        options_fn=lambda d: (
            list(d.device.languages)
            if d.device and d.device.languages
            else _caps("languages")(d)
        ),
        set_fn=lambda c, v: c.set_device_language(v),
        exists_fn=lambda d: bool(d.device and len(d.device.languages) > 1),
    ),
    HPSelectDescription(
        key="time_format",
        translation_key="time_format",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        current_fn=_settings("time_format"),
        options_fn=_caps("time_formats"),
        set_fn=lambda c, v: c.set_time_format(v),
        exists_fn=lambda d: d.capabilities.has_ledm and _has_options("time_formats")(d),
    ),
    HPSelectDescription(
        key="date_format",
        translation_key="date_format",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        current_fn=_settings("date_format"),
        options_fn=_caps("date_formats"),
        set_fn=lambda c, v: c.set_date_format(v),
        exists_fn=lambda d: d.capabilities.has_ledm and _has_options("date_formats")(d),
    ),
    HPSelectDescription(
        key="print_quality",
        translation_key="print_quality",
        entity_category=EntityCategory.CONFIG,
        current_fn=lambda d: d.print_config.quality if d.print_config else None,
        options_fn=lambda d: (
            list(d.print_config.quality_options) if d.print_config else []
        ),
        set_fn=lambda c, v: c.set_print_config(quality=v),
        exists_fn=lambda d: bool(
            d.print_config and len(d.print_config.quality_options) > 1
        ),
    ),
    HPSelectDescription(
        key="print_resolution",
        translation_key="print_resolution",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        current_fn=lambda d: d.print_config.resolution if d.print_config else None,
        options_fn=lambda d: (
            list(d.print_config.resolution_options) if d.print_config else []
        ),
        set_fn=lambda c, v: c.set_print_config(resolution=v),
        exists_fn=lambda d: bool(
            d.print_config and len(d.print_config.resolution_options) > 1
        ),
    ),
    HPSelectDescription(
        key="copy_quality",
        translation_key="copy_quality",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        current_fn=lambda d: d.copy_config.quality if d.copy_config else None,
        options_fn=lambda d: (
            list(d.copy_config.quality_options) if d.copy_config else []
        ),
        set_fn=lambda c, v: c.set_copy_config(quality=v),
        exists_fn=lambda d: bool(
            d.copy_config and len(d.copy_config.quality_options) > 1
        ),
    ),
    HPSelectDescription(
        key="copy_output_type",
        translation_key="copy_output_type",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        current_fn=lambda d: d.copy_config.output_type if d.copy_config else None,
        options_fn=lambda d: (
            list(d.copy_config.output_type_options) if d.copy_config else []
        ),
        set_fn=lambda c, v: c.set_copy_config(output_type=v),
        exists_fn=lambda d: bool(
            d.copy_config and len(d.copy_config.output_type_options) > 1
        ),
    ),
    HPSelectDescription(
        key="copy_media_size",
        translation_key="copy_media_size",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        current_fn=lambda d: d.copy_config.media_size if d.copy_config else None,
        options_fn=lambda d: (
            list(d.copy_config.media_size_options) if d.copy_config else []
        ),
        set_fn=lambda c, v: c.set_copy_config(media_size=v),
        exists_fn=lambda d: bool(
            d.copy_config and len(d.copy_config.media_size_options) > 1
        ),
    ),
)


@dataclass(frozen=True, kw_only=True)
class HPScanOptionDescription(SelectEntityDescription):
    """Select that stores a scan default in the config entry options."""

    option_key: str
    default: str
    options_fn: Callable[[PrinterData], list[str]]


def _scan_resolutions(d: PrinterData) -> list[str]:
    caps = d.scanner_capabilities
    if caps and caps.platen and caps.platen.resolutions:
        return [str(r) for r in caps.platen.resolutions]
    return ["75", "100", "200", "300", "600"]


def _scan_sources(d: PrinterData) -> list[str]:
    caps = d.scanner_capabilities
    return list(caps.sources) if caps and caps.sources else ["Platen"]


SCAN_SELECTS: tuple[HPScanOptionDescription, ...] = (
    HPScanOptionDescription(
        key="scan_resolution",
        translation_key="scan_resolution",
        entity_category=EntityCategory.CONFIG,
        option_key=CONF_SCAN_RESOLUTION,
        default=str(DEFAULT_SCAN_RESOLUTION),
        options_fn=_scan_resolutions,
    ),
    HPScanOptionDescription(
        key="scan_color_mode",
        translation_key="scan_color_mode",
        entity_category=EntityCategory.CONFIG,
        option_key=CONF_SCAN_COLOR_MODE,
        default=DEFAULT_SCAN_COLOR_MODE,
        options_fn=lambda d: list(
            d.scanner_capabilities.platen.color_modes
            if d.scanner_capabilities
            and d.scanner_capabilities.platen
            and d.scanner_capabilities.platen.color_modes
            else SCAN_COLOR_MODES
        ),
    ),
    HPScanOptionDescription(
        key="scan_format",
        translation_key="scan_format",
        entity_category=EntityCategory.CONFIG,
        option_key=CONF_SCAN_FORMAT,
        default=DEFAULT_SCAN_FORMAT,
        options_fn=lambda d: (
            [
                f
                for f in SCAN_FORMATS
                if not d.scanner_capabilities
                or not d.scanner_capabilities.platen
                or not d.scanner_capabilities.platen.document_formats
                or f in d.scanner_capabilities.platen.document_formats
            ]
            or list(SCAN_FORMATS)
        ),
    ),
    HPScanOptionDescription(
        key="scan_source",
        translation_key="scan_source",
        entity_category=EntityCategory.CONFIG,
        option_key=CONF_SCAN_SOURCE,
        default=DEFAULT_SCAN_SOURCE,
        options_fn=_scan_sources,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HPPrinterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the selects."""
    coordinator = entry.runtime_data
    data = coordinator.data
    entities: list[SelectEntity] = [
        HPSelect(coordinator, description)
        for description in SELECTS
        if description.exists_fn(data)
    ]
    if data.capabilities.has_escl:
        entities.extend(
            HPScanOptionSelect(coordinator, description)
            for description in SCAN_SELECTS
            if len(description.options_fn(data)) > 1
        )
    async_add_entities(entities)


class HPSelect(HPPrinterEntity, SelectEntity):
    """Select writing a printer setting."""

    entity_description: HPSelectDescription

    @property
    def options(self) -> list[str]:
        """Allowed values from the printer capabilities."""
        return self.entity_description.options_fn(self.data)

    @property
    def current_option(self) -> str | None:
        """Current value."""
        current = self.entity_description.current_fn(self.data)
        return current if current in self.options else None

    async def async_select_option(self, option: str) -> None:
        """Write the new value."""
        await self.coordinator.async_write(
            lambda: self.entity_description.set_fn(self.coordinator.client, option)
        )


class HPScanOptionSelect(HPPrinterEntity, SelectEntity):
    """Scan default stored in the config entry options (no printer write)."""

    entity_description: HPScanOptionDescription

    def __init__(
        self, coordinator: HPPrinterCoordinator, description: HPScanOptionDescription
    ) -> None:
        """Initialise."""
        super().__init__(coordinator, description)

    @property
    def options(self) -> list[str]:
        """Allowed values from the scanner capabilities."""
        return self.entity_description.options_fn(self.data)

    @property
    def current_option(self) -> str | None:
        """Stored default."""
        value = self.coordinator.config_entry.options.get(
            self.entity_description.option_key, self.entity_description.default
        )
        value = str(value)
        return value if value in self.options else None

    async def async_select_option(self, option: str) -> None:
        """Persist the default without reloading the entry."""
        entry = self.coordinator.config_entry
        key = self.entity_description.option_key
        value: str | int = int(option) if key == CONF_SCAN_RESOLUTION else option
        self.hass.config_entries.async_update_entry(
            entry, options={**entry.options, key: value}
        )
        self.async_write_ha_state()
