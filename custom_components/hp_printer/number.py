"""Numbers: default copies, copy darkness, job timeout."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from hp_printer import HPPrinter, PrinterData

from . import HPPrinterConfigEntry
from .entity import HPPrinterEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HPNumberDescription(NumberEntityDescription):
    """Number backed by a printer setting."""

    value_fn: Callable[[PrinterData], float | None]
    max_fn: Callable[[PrinterData], float | None] = lambda _: None
    set_fn: Callable[[HPPrinter, int], Awaitable[Any]]
    exists_fn: Callable[[PrinterData], bool]


NUMBERS: tuple[HPNumberDescription, ...] = (
    HPNumberDescription(
        key="print_copies",
        translation_key="print_copies",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=1,
        native_max_value=99,
        native_step=1,
        value_fn=lambda d: d.print_config.default_copies if d.print_config else None,
        max_fn=lambda d: d.print_config.copies_max if d.print_config else None,
        set_fn=lambda c, v: c.set_print_config(copies=v),
        exists_fn=lambda d: bool(
            d.print_config and d.print_config.default_copies is not None
        ),
    ),
    HPNumberDescription(
        key="job_timeout",
        translation_key="job_timeout",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        mode=NumberMode.BOX,
        native_min_value=5,
        native_max_value=300,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda d: (
            d.print_config.job_timeout_seconds if d.print_config else None
        ),
        set_fn=lambda c, v: c.set_print_config(job_timeout_seconds=v),
        exists_fn=lambda d: bool(
            d.print_config and d.print_config.job_timeout_seconds is not None
        ),
    ),
    HPNumberDescription(
        key="copy_copies",
        translation_key="copy_copies",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        mode=NumberMode.BOX,
        native_min_value=1,
        native_max_value=9,
        native_step=1,
        value_fn=lambda d: d.copy_config.copies if d.copy_config else None,
        max_fn=lambda d: d.copy_config.copies_max if d.copy_config else None,
        set_fn=lambda c, v: c.set_copy_config(copies=v),
        exists_fn=lambda d: bool(d.copy_config and d.copy_config.copies is not None),
    ),
    HPNumberDescription(
        key="copy_lighter_darker",
        translation_key="copy_lighter_darker",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        mode=NumberMode.SLIDER,
        native_min_value=0,
        native_max_value=8,
        native_step=1,
        value_fn=lambda d: d.copy_config.lighter_darker if d.copy_config else None,
        max_fn=lambda d: d.copy_config.lighter_darker_max if d.copy_config else None,
        set_fn=lambda c, v: c.set_copy_config(lighter_darker=v),
        exists_fn=lambda d: bool(
            d.copy_config and d.copy_config.lighter_darker is not None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HPPrinterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the numbers."""
    coordinator = entry.runtime_data
    async_add_entities(
        HPNumber(coordinator, description)
        for description in NUMBERS
        if coordinator.data.capabilities.has_ledm
        and description.exists_fn(coordinator.data)
    )


class HPNumber(HPPrinterEntity, NumberEntity):
    """Number writing a printer setting."""

    entity_description: HPNumberDescription

    @property
    def native_value(self) -> float | None:
        """Current value."""
        return self.entity_description.value_fn(self.data)

    @property
    def native_max_value(self) -> float:
        """Maximum from the printer capabilities when known."""
        maximum = self.entity_description.max_fn(self.data)
        if maximum is not None:
            return maximum
        return super().native_max_value

    async def async_set_native_value(self, value: float) -> None:
        """Write the new value."""
        await self.coordinator.async_write(
            lambda: self.entity_description.set_fn(self.coordinator.client, int(value))
        )
