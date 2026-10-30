"""Event entity for printer events (alerts, jobs, scans, power)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HPPrinterConfigEntry
from .const import EVENT_TYPES, SIGNAL_EVENT
from .entity import HPPrinterEntity

PARALLEL_UPDATES = 0

DESCRIPTION = EventEntityDescription(
    key="events", translation_key="events", event_types=list(EVENT_TYPES)
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HPPrinterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the event entity."""
    async_add_entities([HPPrinterEventEntity(entry.runtime_data, DESCRIPTION)])


class HPPrinterEventEntity(HPPrinterEntity, EventEntity):
    """Fires when the printer reports an event or a job/scan transitions."""

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_EVENT, self._handle_event)
        )

    @callback
    def _handle_event(
        self, entry_id: str, event_type: str, attributes: dict[str, Any]
    ) -> None:
        if entry_id != self.coordinator.config_entry.entry_id:
            return
        if event_type not in EVENT_TYPES:
            return
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Events are pushed through the dispatcher; only track availability."""
        self.async_write_ha_state()
