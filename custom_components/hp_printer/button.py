"""Buttons: identify, scan, cancel, reports, cleaning, alignment, restart."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from hp_printer import PrinterData

from . import HPPrinterConfigEntry
from .const import DOMAIN, REPORT_BUTTONS
from .coordinator import HPPrinterCoordinator
from .entity import HPPrinterEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HPButtonDescription(ButtonEntityDescription):
    """Button running a printer action."""

    press_fn: Callable[[HPPrinterCoordinator], Awaitable[Any]]
    exists_fn: Callable[[PrinterData], bool] = lambda _: True


async def _cancel_current_job(coordinator: HPPrinterCoordinator) -> None:
    job = coordinator.data.current_job
    if job is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="no_active_job"
        )
    await coordinator.async_write(lambda: coordinator.client.cancel_job(job.id))


BUTTONS: tuple[HPButtonDescription, ...] = (
    HPButtonDescription(
        key="identify",
        translation_key="identify",
        device_class=ButtonDeviceClass.IDENTIFY,
        press_fn=lambda c: c.async_write(lambda: c.client.identify()),
        exists_fn=lambda d: d.capabilities.has_ipp,
    ),
    HPButtonDescription(
        key="scan",
        translation_key="scan",
        press_fn=lambda c: c.async_scan(),
        exists_fn=lambda d: d.capabilities.has_escl,
    ),
    HPButtonDescription(
        key="cancel_job",
        translation_key="cancel_job",
        press_fn=_cancel_current_job,
        exists_fn=lambda d: d.capabilities.has_ipp,
    ),
    HPButtonDescription(
        key="check_firmware",
        translation_key="check_firmware",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda c: c.async_write(lambda: c.client.firmware_action("check")),
        exists_fn=lambda d: d.firmware is not None,
    ),
    HPButtonDescription(
        key="clean_cartridges",
        translation_key="clean_cartridges",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda c: c.async_write(lambda: c.client.clean_cartridges(1)),
        exists_fn=lambda d: d.capabilities.has_internal_print or d.capabilities.has_cdm,
    ),
    HPButtonDescription(
        key="align_cartridges",
        translation_key="align_cartridges",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda c: c.async_write(lambda: c.client.align_cartridges()),
        exists_fn=lambda d: d.capabilities.has_calibration or d.capabilities.has_cdm,
    ),
    HPButtonDescription(
        key="check_internet",
        translation_key="check_internet",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        press_fn=lambda c: c.async_write(lambda: c.client.check_internet_connection()),
        exists_fn=lambda d: d.internet_connection_state is not None,
    ),
    HPButtonDescription(
        key="restart",
        translation_key="restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        press_fn=lambda c: c.async_write(lambda: c.client.restart()),
        exists_fn=lambda d: (
            d.capabilities.has_product_actions or d.capabilities.has_cdm
        ),
    ),
    *(
        HPButtonDescription(
            key=f"report_{job_type}",
            translation_key=translation_key,
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=job_type
            in ("configurationPage", "pqDiagnosticsPage"),
            press_fn=(
                lambda jt: (
                    lambda c: c.async_write(lambda: c.client.print_internal_page(jt))
                )
            )(job_type),
            exists_fn=lambda d: (
                d.capabilities.has_internal_print or d.capabilities.has_cdm
            ),
        )
        for job_type, translation_key in REPORT_BUTTONS.items()
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HPPrinterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        HPButton(coordinator, description)
        for description in BUTTONS
        if description.exists_fn(coordinator.data)
    )


class HPButton(HPPrinterEntity, ButtonEntity):
    """Button running a printer action."""

    entity_description: HPButtonDescription

    async def async_press(self) -> None:
        """Run the action."""
        await self.entity_description.press_fn(self.coordinator)
