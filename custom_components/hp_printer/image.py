"""Image entity showing the last scan."""

from __future__ import annotations

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HPPrinterConfigEntry
from .const import SIGNAL_SCAN_DONE
from .coordinator import HPPrinterCoordinator
from .entity import HPPrinterEntity

PARALLEL_UPDATES = 0

DESCRIPTION = ImageEntityDescription(key="last_scan", translation_key="last_scan")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HPPrinterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the image entity for printers with a scanner."""
    coordinator = entry.runtime_data
    if coordinator.data.capabilities.has_escl:
        async_add_entities([HPLastScanImage(hass, coordinator)])


class HPLastScanImage(HPPrinterEntity, ImageEntity):
    """The most recent scan started from Home Assistant."""

    def __init__(self, hass: HomeAssistant, coordinator: HPPrinterCoordinator) -> None:
        """Initialise both bases."""
        HPPrinterEntity.__init__(self, coordinator, DESCRIPTION)
        ImageEntity.__init__(self, hass)
        self._attr_content_type = "image/jpeg"

    async def async_added_to_hass(self) -> None:
        """Refresh when a scan completes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_SCAN_DONE, self._scan_done)
        )
        if self.coordinator.last_scan:
            self._apply_scan()

    @callback
    def _scan_done(self, entry_id: str) -> None:
        if entry_id != self.coordinator.config_entry.entry_id:
            return
        self._apply_scan()
        self.async_write_ha_state()

    def _apply_scan(self) -> None:
        scan = self.coordinator.last_scan
        if scan is None:
            return
        self._attr_content_type = scan.content_type
        self._attr_image_last_updated = scan.when
        self._cached_image = None

    async def async_image(self) -> bytes | None:
        """Return the scanned document (JPEG or PDF)."""
        scan = self.coordinator.last_scan
        return scan.first_page if scan else None
