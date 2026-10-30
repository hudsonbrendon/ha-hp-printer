"""Text entities: device location and description (shown in the EWS)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from hp_printer import HPPrinter, PrinterData

from . import HPPrinterConfigEntry
from .entity import HPPrinterEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HPTextDescription(TextEntityDescription):
    """Text backed by a printer setting."""

    value_fn: Callable[[PrinterData], str | None]
    set_fn: Callable[[HPPrinter, str], Awaitable[Any]]


TEXTS: tuple[HPTextDescription, ...] = (
    HPTextDescription(
        key="location",
        translation_key="location",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_max=32,
        value_fn=lambda d: d.settings.location if d.settings else None,
        set_fn=lambda c, v: c.set_device_location(v),
    ),
    HPTextDescription(
        key="description",
        translation_key="description",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_max=127,
        value_fn=lambda d: d.settings.description if d.settings else None,
        set_fn=lambda c, v: c.set_device_description(v),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HPPrinterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the text entities (LEDM only)."""
    coordinator = entry.runtime_data
    if coordinator.data.capabilities.has_ledm and coordinator.data.settings:
        async_add_entities(HPText(coordinator, description) for description in TEXTS)


class HPText(HPPrinterEntity, TextEntity):
    """Text writing a printer setting."""

    entity_description: HPTextDescription

    @property
    def native_value(self) -> str | None:
        """Current value (empty string when unset)."""
        return self.entity_description.value_fn(self.data) or ""

    async def async_set_value(self, value: str) -> None:
        """Write the new value."""
        await self.coordinator.async_write(
            lambda: self.entity_description.set_fn(self.coordinator.client, value)
        )
